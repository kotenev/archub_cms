"""ITIL Service Catalog: the published list of services the provider offers.

A :class:`CatalogService` is a request-able / supportable service (e.g. "Managed
PostgreSQL", "Object Storage") with an owner, a lifecycle stage and an optional
linked :class:`~archub_cms.extensibility.example_plugins.itsm.sla.SlaDefinition`.
Requests can be raised *against* a catalog service, which is how the desk knows
which SLA to apply. :class:`ServiceCatalog` is the application facade over a
:class:`DocumentRepository` collection.
"""

from __future__ import annotations

__all__ = ["CatalogService", "ServiceCatalog", "ServiceLifecycle"]

from dataclasses import dataclass
from enum import StrEnum
from time import time
from typing import Any

from archub_cms.extensibility.example_plugins.itsm.documents import DocumentRepository, new_id


class ServiceLifecycle(StrEnum):
    """ITIL service lifecycle stages."""

    PLANNED = "planned"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass
class CatalogService:
    """A request-able / supportable service in the provider's catalog."""

    id: str
    name: str
    category: str = "general"
    description: str = ""
    owner: str = ""
    sla_id: str = ""
    lifecycle: ServiceLifecycle = ServiceLifecycle.ACTIVE
    provider: str = ""
    tags: tuple[str, ...] = ()
    created_at: float = 0.0
    updated_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "owner": self.owner,
            "sla_id": self.sla_id,
            "lifecycle": self.lifecycle.value,
            "provider": self.provider,
            "tags": list(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CatalogService:
        try:
            lifecycle = ServiceLifecycle(str(payload.get("lifecycle") or "active"))
        except ValueError:
            lifecycle = ServiceLifecycle.ACTIVE
        return cls(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            category=str(payload.get("category") or "general"),
            description=str(payload.get("description") or ""),
            owner=str(payload.get("owner") or ""),
            sla_id=str(payload.get("sla_id") or ""),
            lifecycle=lifecycle,
            provider=str(payload.get("provider") or ""),
            tags=tuple(str(tag) for tag in payload.get("tags", ()) if str(tag)),
            created_at=float(payload.get("created_at") or 0.0),
            updated_at=float(payload.get("updated_at") or 0.0),
        )


class ServiceCatalogError(ValueError):
    """Raised on catalog lookups that fail (mapped to HTTP 404 by the API)."""


class ServiceCatalog:
    """CRUD facade over a catalog-service :class:`DocumentRepository` collection."""

    def __init__(self, repository: DocumentRepository, *, clock: Any = time) -> None:
        self._repo = repository
        self._clock = clock

    def create(self, **fields: Any) -> CatalogService:
        now = self._clock()
        service = CatalogService(
            id=str(fields.get("id") or new_id("svc")),
            name=str(fields.get("name") or "").strip(),
            category=str(fields.get("category") or "general"),
            description=str(fields.get("description") or ""),
            owner=str(fields.get("owner") or ""),
            sla_id=str(fields.get("sla_id") or ""),
            lifecycle=_lifecycle(fields.get("lifecycle")),
            provider=str(fields.get("provider") or ""),
            tags=tuple(str(tag) for tag in fields.get("tags", ()) if str(tag)),
            created_at=now,
            updated_at=now,
        )
        if not service.name:
            raise ServiceCatalogError("catalog service name is required")
        self._repo.upsert(service.id, service.as_dict())
        return service

    def get(self, service_id: str) -> CatalogService:
        payload = self._repo.get(service_id)
        if payload is None:
            raise ServiceCatalogError(f"unknown catalog service {service_id!r}")
        return CatalogService.from_dict(payload)

    def find(self, service_id: str) -> CatalogService | None:
        payload = self._repo.get(service_id)
        return CatalogService.from_dict(payload) if payload is not None else None

    def update(self, service_id: str, **changes: Any) -> CatalogService:
        service = self.get(service_id)
        for key in ("name", "category", "description", "owner", "sla_id", "provider"):
            if key in changes and changes[key] is not None:
                setattr(service, key, str(changes[key]))
        if changes.get("lifecycle"):
            service.lifecycle = _lifecycle(changes["lifecycle"])
        if "tags" in changes and changes["tags"] is not None:
            service.tags = tuple(str(tag) for tag in changes["tags"] if str(tag))
        service.updated_at = self._clock()
        self._repo.upsert(service.id, service.as_dict())
        return service

    def delete(self, service_id: str) -> bool:
        return self._repo.delete(service_id)

    def list(self, *, category: str = "") -> list[CatalogService]:
        services = [CatalogService.from_dict(row) for row in self._repo.list_all()]
        if category:
            services = [s for s in services if s.category == category]
        return sorted(services, key=lambda s: (s.category, s.name.casefold(), s.id))

    def report(self) -> dict[str, Any]:
        services = self.list()
        by_category: dict[str, int] = {}
        by_lifecycle: dict[str, int] = {}
        for service in services:
            by_category[service.category] = by_category.get(service.category, 0) + 1
            by_lifecycle[service.lifecycle.value] = by_lifecycle.get(service.lifecycle.value, 0) + 1
        return {
            "total": len(services),
            "by_category": by_category,
            "by_lifecycle": by_lifecycle,
        }


def _lifecycle(value: Any) -> ServiceLifecycle:
    try:
        return ServiceLifecycle(str(value or "active"))
    except ValueError:
        return ServiceLifecycle.ACTIVE
