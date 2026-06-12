"""The top-level ITSM facade tying the desk to catalog, SLA, CMDB and the BPMN engine.

:class:`ItsmService` is what the plugin exposes (``plugin.itsm``). It owns the
:class:`ServiceCatalog`, :class:`SlaRegistry` and :class:`Cmdb` registries, persists
and reloads BPMN-defined workflow schemes, and offers :meth:`log_request` — a
catalog/SLA-aware way to raise a request that applies the requested service's SLA and
records which configuration items the request affects (for impact analysis).
"""

from __future__ import annotations

__all__ = ["ItsmService", "SchemeValidationError"]

from time import time
from typing import Any

from archub_cms.extensibility.example_plugins.itsm.bpmn import from_bpmn_xml, to_bpmn_xml
from archub_cms.extensibility.example_plugins.itsm.catalog import ServiceCatalog
from archub_cms.extensibility.example_plugins.itsm.cmdb import Cmdb
from archub_cms.extensibility.example_plugins.itsm.documents import DocumentRepository
from archub_cms.extensibility.example_plugins.itsm.request import Request, SlaPolicy
from archub_cms.extensibility.example_plugins.itsm.service_desk import ServiceDesk
from archub_cms.extensibility.example_plugins.itsm.sla import SlaRegistry
from archub_cms.extensibility.example_plugins.itsm.workflow import WorkflowScheme

# Workflow schemes that ship in code and must not be silently replaced wholesale.
_BUILTIN_SCHEME_KEYS = frozenset({"incident", "service_request", "change"})


class SchemeValidationError(ValueError):
    """Raised when an imported BPMN scheme is structurally invalid."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems) or "invalid workflow scheme")
        self.problems = problems


class ItsmService:
    """Composition facade over the desk + catalog + SLA + CMDB + BPMN scheme store."""

    def __init__(
        self,
        *,
        desk: ServiceDesk,
        catalog: ServiceCatalog,
        sla: SlaRegistry,
        cmdb: Cmdb,
        scheme_repo: DocumentRepository,
        link_repo: DocumentRepository,
        clock: Any = time,
    ) -> None:
        self.desk = desk
        self.catalog = catalog
        self.sla = sla
        self.cmdb = cmdb
        self._schemes = scheme_repo
        self._links = link_repo
        self._clock = clock
        self.load_persisted_schemes()

    # -- BPMN workflow engine ---------------------------------------------

    def load_persisted_schemes(self) -> int:
        """Overlay any persisted BPMN-defined schemes onto the desk's code defaults."""

        loaded = 0
        for doc in self._schemes.list_all():
            xml = str(doc.get("bpmn") or "")
            if not xml:
                continue
            try:
                scheme = from_bpmn_xml(xml, key=str(doc.get("key") or ""))
            except ValueError:
                continue
            self.desk.register_scheme(scheme)
            loaded += 1
        return loaded

    def import_bpmn_scheme(
        self, xml: str, *, key: str = "", name: str = "", actor: str = ""
    ) -> WorkflowScheme:
        """Parse BPMN into a runnable scheme, register it on the desk and persist it."""

        scheme = from_bpmn_xml(xml, key=key, name=name)
        problems = scheme.validate()
        if problems:
            raise SchemeValidationError(problems)
        self.desk.register_scheme(scheme)
        self._persist_scheme(scheme, actor=actor)
        return scheme

    def save_scheme(self, scheme: WorkflowScheme, *, actor: str = "") -> WorkflowScheme:
        problems = scheme.validate()
        if problems:
            raise SchemeValidationError(problems)
        self.desk.register_scheme(scheme)
        self._persist_scheme(scheme, actor=actor)
        return scheme

    def delete_custom_scheme(self, key: str) -> bool:
        if key in _BUILTIN_SCHEME_KEYS:
            raise ValueError(f"cannot delete built-in workflow scheme {key!r}")
        return self._schemes.delete(key)

    def custom_scheme_keys(self) -> list[str]:
        return sorted(str(doc.get("key") or "") for doc in self._schemes.list_all())

    def _persist_scheme(self, scheme: WorkflowScheme, *, actor: str) -> None:
        now = self._clock()
        existing = self._schemes.get(scheme.key) or {}
        self._schemes.upsert(
            scheme.key,
            {
                "key": scheme.key,
                "name": scheme.name,
                "bpmn": to_bpmn_xml(scheme),
                "updated_by": actor,
                "created_at": existing.get("created_at", now),
                "updated_at": now,
            },
        )

    # -- catalog / SLA aware request logging ------------------------------

    def sla_policy_for(self, *, service_id: str = "", sla_id: str = "") -> SlaPolicy | None:
        """Resolve the SLA policy from an explicit SLA id or the service's linked SLA."""

        if sla_id:
            return self.sla.policy_for(sla_id)
        if service_id:
            service = self.catalog.find(service_id)
            if service is not None and service.sla_id:
                return self.sla.policy_for(service.sla_id)
        return None

    def log_request(
        self,
        *,
        service_id: str = "",
        ci_ids: tuple[str, ...] = (),
        sla_id: str = "",
        **fields: Any,
    ) -> Request:
        """Raise a request applying the service/SLA agreement and recording impact."""

        policy = self.sla_policy_for(service_id=service_id, sla_id=sla_id)
        request = self.desk.create_request(sla=policy, **fields)
        if service_id or ci_ids:
            self._links.upsert(
                request.key,
                {
                    "request": request.key,
                    "service_id": service_id,
                    "ci_ids": list(ci_ids),
                    "created_at": self._clock(),
                },
            )
        return request

    def request_impact(self, key: str) -> dict[str, Any]:
        """The service + configuration items a request affects, with downstream impact."""

        # Validate the request exists (raises RequestNotFoundError otherwise).
        request = self.desk.get(key)
        link = self._links.get(key) or {}
        service = self.catalog.find(str(link.get("service_id") or ""))
        cis: list[dict[str, Any]] = []
        impacted: dict[str, dict[str, Any]] = {}
        for ci_id in link.get("ci_ids", []) or []:
            item = self.cmdb.find_item(str(ci_id))
            if item is None:
                continue
            cis.append(item.as_dict())
            for affected in self.cmdb.impact(item.id)["impacted"]:
                impacted[affected["id"]] = affected
        return {
            "request": request.key,
            "status_id": request.status_id,
            "service": service.as_dict() if service is not None else None,
            "configuration_items": cis,
            "impacted": list(impacted.values()),
            "impacted_count": len(impacted),
        }

    def report(self) -> dict[str, Any]:
        return {
            "queue": self.desk.queue_summary(),
            "catalog": self.catalog.report(),
            "sla_definitions": len(self.sla.list()),
            "cmdb": self.cmdb.report(),
            "custom_schemes": self.custom_scheme_keys(),
        }
