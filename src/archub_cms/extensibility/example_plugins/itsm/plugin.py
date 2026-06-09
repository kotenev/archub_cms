"""The ITSM Service Desk plugin entrypoint and the extensions it registers.

``setup`` builds one shared :class:`ServiceDesk` (seeded from plugin settings and
backed by the platform persistence adapter) and registers six extensions against
ArcHub's SPI:

* :class:`ServiceDeskWorkflowAction` (``WorkflowActionExt``) — drive a request through
  its customizable, Jira-style ITIL workflow.
* :class:`BpmnDiagramMacro` (``MacroExt``) — ``{{ bpmn scheme=incident }}`` embeds a
  Mermaid (or BPMN-XML) view of any workflow scheme into a knowledge page.
* :class:`ServiceDeskWidget` (``DashboardWidgetExt``) — the live request queue/SLA tile.
* :class:`LogRequestAction` (``PageActionExt``) — "Log Service Desk Request" from a page.
* :class:`CloudAlertConnector` (``ConnectorExt``) — pull cloud alerts in as incidents,
  push request updates back to the provider.
* :class:`TriageTool` (``LLMToolExt``) — offline heuristic that suggests type/priority.
"""

from __future__ import annotations

__all__ = ["ITSMServiceDeskPlugin"]

from typing import Any

from archub_cms.extensibility.example_plugins.itsm.bpmn import to_bpmn_xml, to_mermaid
from archub_cms.extensibility.example_plugins.itsm.repository import RequestRepository
from archub_cms.extensibility.example_plugins.itsm.request import (
    CloudResource,
    Priority,
    Request,
    RequestType,
)
from archub_cms.extensibility.example_plugins.itsm.service_desk import ServiceDesk
from archub_cms.extensibility.example_plugins.itsm.workflow import WorkflowError

# Keywords that nudge offline triage toward a type/priority (no network needed).
_INCIDENT_WORDS = ("down", "outage", "error", "failed", "broken", "5xx", "crash", "unavailable")
_REQUEST_WORDS = ("request", "access", "provision", "quota", "new ", "please", "need")
_CHANGE_WORDS = ("deploy", "upgrade", "migrate", "release", "change", "rollout")
_CRITICAL_WORDS = ("production", "prod", "outage", "data loss", "critical", "p1", "sev1")
_HIGH_WORDS = ("degraded", "slow", "intermittent", "p2", "sev2")


class ITSMServiceDeskPlugin:
    """In-process ArcHub plugin exposing a cloud Service Desk with custom workflows."""

    plugin_id = "archub.itsm.service_desk"

    def __init__(self) -> None:
        self.desk: ServiceDesk | None = None

    def setup(self, context: Any) -> None:
        settings = getattr(context, "settings", {}) or {}
        platform = getattr(context, "platform", None)
        if platform is None:
            raise RuntimeError("ITSM Service Desk plugin requires PluginPlatformAdapter")
        desk = ServiceDesk(
            project_prefix=str(settings.get("project_prefix") or "REQ"),
            provider=str(settings.get("provider") or "archub-cloud"),
            repository=_build_repository(settings, platform),
        )
        self.desk = desk
        platform.audit(
            "itsm.setup",
            metadata={
                "project_prefix": desk.project_prefix,
                "provider": desk.provider,
                "storage": str(settings.get("storage") or "sqlite"),
            },
        )
        context.register(ServiceDeskWorkflowAction(desk))
        context.register(BpmnDiagramMacro(desk))
        context.register(ServiceDeskWidget(desk))
        context.register(LogRequestAction(desk))
        context.register(CloudAlertConnector(desk))
        context.register(TriageTool(desk))


def _build_repository(settings: dict[str, Any], platform: Any) -> RequestRepository:
    """Ask the platform adapter for the configured persistent repository."""

    repository = platform.service_desk_repository(settings)
    if not isinstance(repository, RequestRepository):
        raise RuntimeError("platform returned an incompatible ITSM request repository")
    return repository


def _resource_from(payload: dict[str, Any], *, default_provider: str) -> CloudResource:
    return CloudResource(
        provider=str(payload.get("provider") or default_provider),
        service=str(payload.get("service") or ""),
        region=str(payload.get("region") or ""),
        resource_id=str(payload.get("resource_id") or payload.get("resource") or ""),
    )


def _request_summary(request: Request) -> dict[str, Any]:
    return {
        "key": request.key,
        "type": request.type.value,
        "status_id": request.status_id,
        "priority": request.priority.value,
        "assignee": request.assignee,
        "summary": request.summary,
    }


class ServiceDeskWorkflowAction:
    """Drive a request through its workflow — the customizable transition action."""

    action_name = "itsm.transition"

    def __init__(self, desk: ServiceDesk) -> None:
        self._desk = desk

    def can_execute(self, context: dict[str, Any]) -> bool:
        key = str(context.get("request") or "")
        transition_id = str(context.get("transition") or "")
        if not key or not transition_id:
            return False
        try:
            available = {
                t["id"]
                for t in self._desk.available_transitions(
                    key, actor_role=str(context.get("actor_role") or "")
                )
            }
        except WorkflowError:
            return False
        return transition_id in available

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        try:
            request = self._desk.transition(
                str(context.get("request") or ""),
                str(context.get("transition") or ""),
                actor=str(context.get("actor") or ""),
                actor_role=str(context.get("actor_role") or ""),
                resolution=str(context.get("resolution") or ""),
                approved=bool(context.get("approved")),
            )
        except WorkflowError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "request": _request_summary(request)}


class BpmnDiagramMacro:
    """Render a workflow scheme as BPMN/Mermaid inside a knowledge page."""

    macro_name = "bpmn"

    def __init__(self, desk: ServiceDesk) -> None:
        self._desk = desk

    def expand(self, arguments: dict[str, Any]) -> str:
        key = str(arguments.get("scheme") or "incident")
        scheme = self._desk.schemes.get(key)
        if scheme is None:
            available = ", ".join(sorted(self._desk.schemes)) or "(none)"
            return f"<!-- unknown workflow scheme '{key}'; available: {available} -->"
        if str(arguments.get("format") or "mermaid").lower() == "bpmn":
            return to_bpmn_xml(scheme)
        return f"```mermaid\n{to_mermaid(scheme)}\n```"


class ServiceDeskWidget:
    """Dashboard tile: request queue counts and SLA breaches."""

    widget_type = "itsm_queue"
    widget_name = "Service Desk Queue"

    def __init__(self, desk: ServiceDesk) -> None:
        self._desk = desk

    def render(self, config: dict[str, Any]) -> dict[str, Any]:
        summary = self._desk.queue_summary()
        return {
            "widget_type": self.widget_type,
            "widget_name": self.widget_name,
            **summary,
        }


class LogRequestAction:
    """Page context-menu action: log a service-desk request about this page."""

    action_id = "itsm.log_request"
    action_label = "Log Service Desk Request"
    icon = "🎫"

    def __init__(self, desk: ServiceDesk) -> None:
        self._desk = desk

    def is_available(self, page_context: dict[str, Any]) -> bool:
        return True

    def execute(self, page_context: dict[str, Any]) -> dict[str, Any]:
        summary = str(
            page_context.get("summary") or page_context.get("title") or "Service desk request"
        )
        type_value = str(page_context.get("type") or "service_request")
        try:
            request_type = RequestType(type_value)
        except ValueError:
            request_type = RequestType.SERVICE_REQUEST
        request = self._desk.create_request(
            type=request_type,
            summary=summary,
            description=str(page_context.get("route_path") or ""),
            reporter=str(page_context.get("actor") or page_context.get("user") or ""),
            cloud=_resource_from(page_context, default_provider=self._desk.provider),
        )
        return {"action": "request_logged", "request": _request_summary(request)}


class CloudAlertConnector:
    """Bi-directional cloud-provider connector (alerts in, request updates out)."""

    connector_id = "itsm.cloud"
    target_system = "cloud-monitoring"

    def __init__(self, desk: ServiceDesk) -> None:
        self._desk = desk

    def sync_pull(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Turn provider monitoring alerts into incident requests."""

        created: list[dict[str, Any]] = []
        for alert in config.get("alerts", ()):
            if not isinstance(alert, dict):
                continue
            severity = str(alert.get("severity") or "medium").lower()
            priority = {
                "critical": Priority.CRITICAL,
                "high": Priority.HIGH,
                "warning": Priority.MEDIUM,
                "low": Priority.LOW,
            }.get(severity, Priority.MEDIUM)
            request = self._desk.create_request(
                type=RequestType.INCIDENT,
                summary=str(alert.get("title") or alert.get("summary") or "Cloud alert"),
                description=str(alert.get("description") or ""),
                priority=priority,
                reporter=str(alert.get("source") or "cloud-monitoring"),
                cloud=_resource_from(alert, default_provider=self._desk.provider),
            )
            created.append(_request_summary(request))
        return created

    def sync_push(self, items: list[dict[str, Any]]) -> int:
        """Acknowledge pushing request updates to the provider (count delivered)."""

        return len([item for item in items if item.get("key")])


class TriageTool:
    """Offline triage: suggest a request type and priority from free text."""

    name = "itsm.triage"

    def __init__(self, desk: ServiceDesk) -> None:
        self._desk = desk

    def run(self, arguments: dict[str, Any]) -> str:
        text = str(arguments.get("text") or arguments.get("description") or "").lower()
        request_type = self._classify_type(text)
        priority = self._classify_priority(text)
        scheme = self._desk.scheme_for(request_type)
        return (
            f"type={request_type.value} priority={priority.value} "
            f"scheme={scheme.key} initial_status={scheme.initial_status_id}"
        )

    @staticmethod
    def _classify_type(text: str) -> RequestType:
        if any(word in text for word in _CHANGE_WORDS):
            return RequestType.CHANGE
        if any(word in text for word in _INCIDENT_WORDS):
            return RequestType.INCIDENT
        if any(word in text for word in _REQUEST_WORDS):
            return RequestType.SERVICE_REQUEST
        return RequestType.INCIDENT

    @staticmethod
    def _classify_priority(text: str) -> Priority:
        if any(word in text for word in _CRITICAL_WORDS):
            return Priority.CRITICAL
        if any(word in text for word in _HIGH_WORDS):
            return Priority.HIGH
        return Priority.MEDIUM
