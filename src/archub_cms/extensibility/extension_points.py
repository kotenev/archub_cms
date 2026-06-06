"""Service Provider Interface (SPI): the extension points plugins implement.

A plugin is any object with an optional ``setup(context)`` lifecycle hook. During
setup it registers one or more *extensions* with the host via the
:class:`PluginContext`. Each extension implements one of the protocols below.
Phase 1 wires :class:`EventHookExt` and :class:`SearchExt` end-to-end; the rest
define the stable surface that later phases (renderers, importers, auth, etc.)
fill in — mirroring the breadth of Wiki.js/Confluence extension catalogs.
"""

from __future__ import annotations

__all__ = [
    "AnalyticsProviderExt",
    "AuthExt",
    "ContentTransformerExt",
    "EventHookExt",
    "ExporterExt",
    "ImporterExt",
    "LLMToolExt",
    "MacroExt",
    "NotificationExt",
    "Plugin",
    "PluginContext",
    "RendererExt",
    "ScheduledJobExt",
    "SearchExt",
    "SearchHit",
    "SearchIndexerExt",
    "SecurityPolicyExt",
    "StorageExt",
    "ThemeExt",
    "WorkflowActionExt",
]

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from archub_cms.kernel.events import ArcHubDomainEvent, EventBus

if TYPE_CHECKING:
    from archub_cms.domain.plugins import KnowledgePluginManifest


@dataclass(frozen=True)
class SearchHit:
    """A scored search contribution from a SearchExt plugin."""

    route_path: str
    title: str
    excerpt: str
    score: float
    source: str = "plugin"

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_path": self.route_path,
            "title": self.title,
            "excerpt": self.excerpt,
            "score": self.score,
            "source": self.source,
        }


class PluginContext:
    """Handed to each plugin's ``setup``; the only surface a plugin may touch.

    Keeping the context narrow is the capability boundary: a plugin can register
    extensions, read its settings, and subscribe to events, but gets no direct
    handle to the database or the write path.
    """

    def __init__(
        self,
        *,
        manifest: KnowledgePluginManifest,
        settings: dict[str, Any],
        event_bus: EventBus,
    ) -> None:
        self.manifest = manifest
        self.settings = dict(settings)
        self._event_bus = event_bus
        self._extensions: list[Any] = []

    def register(self, extension: Any) -> None:
        self._extensions.append(extension)

    def subscribe(self, event_type: str, handler: Any) -> None:
        self._event_bus.subscribe(event_type, handler)

    @property
    def registered(self) -> tuple[Any, ...]:
        return tuple(self._extensions)


@runtime_checkable
class Plugin(Protocol):
    def setup(self, context: PluginContext) -> None: ...


@runtime_checkable
class EventHookExt(Protocol):
    event_types: tuple[str, ...]

    def handle(self, event: ArcHubDomainEvent) -> None: ...


@runtime_checkable
class SearchExt(Protocol):
    def search(self, query: str, *, limit: int) -> list[SearchHit]: ...


@runtime_checkable
class LLMToolExt(Protocol):
    name: str

    def run(self, arguments: dict[str, Any]) -> str: ...


@runtime_checkable
class RendererExt(Protocol):
    def render(self, body: str, *, context: dict[str, Any]) -> str: ...


@runtime_checkable
class MacroExt(Protocol):
    macro_name: str

    def expand(self, arguments: dict[str, Any]) -> str: ...


@runtime_checkable
class ImporterExt(Protocol):
    def import_documents(self, source: Any) -> list[dict[str, Any]]: ...


@runtime_checkable
class ExporterExt(Protocol):
    def export_documents(self, documents: list[dict[str, Any]]) -> Any: ...


@runtime_checkable
class AuthExt(Protocol):
    def authenticate(self, request: Any) -> Any: ...


@runtime_checkable
class StorageExt(Protocol):
    def read(self, key: str) -> bytes: ...

    def write(self, key: str, data: bytes) -> None: ...


@runtime_checkable
class NotificationExt(Protocol):
    """An outbound notification channel (Slack, email, webhook, …).

    The host subscribes every channel to the event bus, so domain events fan out
    to all channels — the seam Wiki.js/Confluence integrations plug into.
    """

    channel: str

    def notify(self, event: ArcHubDomainEvent) -> None: ...


@runtime_checkable
class ThemeExt(Protocol):
    """Custom theme / layout provider (Wiki.js/Confluence-style).

    Returns CSS, template overrides, or layout descriptors that the admin
    dashboard and public delivery surface apply per-space or globally.
    """

    theme_id: str

    def styles(self) -> str: ...

    def layout_overrides(self) -> dict[str, Any]: ...


@runtime_checkable
class ScheduledJobExt(Protocol):
    """Plugin-defined scheduled job (cron-like).

    The scheduler context discovers these extensions and registers them as
    managed jobs that the maintenance worker fires on schedule.
    """

    job_name: str
    cron_expression: str

    def execute(self, payload: dict[str, Any]) -> str: ...


@runtime_checkable
class AnalyticsProviderExt(Protocol):
    """Custom analytics collector (page views, search analytics, user activity).

    Plugins implement this to feed external analytics services (Google
    Analytics, Matomo, custom dashboards) from ArcHub domain events.
    """

    provider_name: str

    def track(self, event: ArcHubDomainEvent) -> None: ...

    def report(self, *, metric: str, period: str) -> dict[str, Any]: ...


@runtime_checkable
class WorkflowActionExt(Protocol):
    """Custom workflow action / trigger.

    Extends the workflow state machine with plugin-defined transitions,
    automatic actions, or external integrations triggered by workflow state
    changes (e.g. notify Slack on approval, trigger CI on publish).
    """

    action_name: str

    def can_execute(self, context: dict[str, Any]) -> bool: ...

    def execute(self, context: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class ContentTransformerExt(Protocol):
    """Content pipeline transformation (Wiki.js-style rendering pipeline).

    Transforms content payloads during publish or render — e.g. image
    optimization, link rewriting, table-of-contents injection, or
    Obsidian-style callout conversion.
    """

    transformer_name: str
    phase: str  # "pre_publish", "post_publish", "render"

    def transform(self, content: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class SearchIndexerExt(Protocol):
    """Custom search indexer (Elasticsearch, Meilisearch, Algolia, …).

    Plugins implement this to sync ArcHub content to external search engines
    when content is published or updated.
    """

    indexer_name: str

    def index(self, route_path: str, content: dict[str, Any]) -> None: ...

    def remove(self, route_path: str) -> None: ...

    def rebuild(self, documents: list[dict[str, Any]]) -> int: ...


@runtime_checkable
class SecurityPolicyExt(Protocol):
    """Custom security / compliance policy.

    Plugins enforce content security policies (e.g. data classification,
    PII detection, GDPR compliance, content approval rules) that gate
    publishing or access beyond the built-in governance context.
    """

    policy_name: str

    def check_publish(self, content: dict[str, Any]) -> tuple[bool, str]: ...

    def check_access(self, user: Any, content: dict[str, Any]) -> tuple[bool, str]: ...
