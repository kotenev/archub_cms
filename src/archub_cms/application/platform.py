"""ArcHubPlatform — the composition root / facade over all bounded contexts.

A single ergonomic entry point that wires every context service onto shared
infrastructure (one CMS persistence engine, one in-process event bus, one plugin
host) and exposes a self-describing :meth:`capabilities` surface. This is the
Composition Root pattern: dependencies are assembled here, once, instead of
scattered across per-call factories.
"""

from __future__ import annotations

__all__ = ["ArcHubPlatform", "get_archub_platform"]

from functools import cached_property
from typing import Any

from archub_cms.application.analytics_service import AnalyticsService, get_archub_analytics_service
from archub_cms.application.blueprint_service import (
    BlueprintQueryService,
    get_archub_blueprint_query_service,
)
from archub_cms.application.collaboration_service import (
    CollaborationService,
    get_archub_collaboration_service,
)
from archub_cms.application.content_service import ContentService, get_archub_content_service
from archub_cms.application.delivery_read_service import (
    DeliveryReadService,
    get_archub_delivery_read_service,
)
from archub_cms.application.governance_service import (
    GovernanceQueryService,
    get_archub_governance_query_service,
)
from archub_cms.application.graph_service import GraphService, get_archub_graph_service
from archub_cms.application.knowledge import (
    ArcHubKnowledgeBaseService,
    get_archub_knowledge_base_service,
)
from archub_cms.application.localization_service import (
    LocalizationQueryService,
    get_archub_localization_query_service,
)
from archub_cms.application.lock_service import LockQueryService, get_archub_lock_query_service
from archub_cms.application.media_service import MediaQueryService, get_archub_media_query_service
from archub_cms.application.modeling_service import (
    ModelingQueryService,
    get_archub_modeling_query_service,
)
from archub_cms.application.packaging_service import PackagingService, get_archub_packaging_service
from archub_cms.application.plugin_management_service import (
    PluginManagementService,
    get_archub_plugin_management_service,
)
from archub_cms.application.runtime_service import (
    RuntimeQueryService,
    get_archub_runtime_query_service,
)
from archub_cms.application.search_service import SearchService, get_archub_search_service
from archub_cms.application.subscription_service import (
    SubscriptionQueryService,
    get_archub_subscription_query_service,
)
from archub_cms.application.trash_service import (
    TrashQueryService,
    get_archub_trash_query_service,
)
from archub_cms.application.versioning_service import (
    VersioningQueryService,
    get_archub_versioning_query_service,
)
from archub_cms.application.webhooks_service import (
    WebhooksQueryService,
    get_archub_webhooks_query_service,
)
from archub_cms.application.workflow_service import (
    WorkflowQueryService,
    get_archub_workflow_query_service,
)
from archub_cms.extensibility.host import PluginHost, get_plugin_host
from archub_cms.kernel.events import EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service
from archub_cms.settings import ArcHubSettings

# (context name, one-line description) — the platform's self-description.
_CONTEXTS: tuple[tuple[str, str], ...] = (
    ("content", "Authoring: the content-tree aggregate, drafts, publishing."),
    ("knowledge", "Knowledge base: spaces, documents, hybrid RAG answers."),
    ("collaboration", "Comments, @mentions and reactions."),
    ("modeling", "Content types, fields, data types, templates."),
    ("delivery", "Syndication: sitemap, feed, tags, redirects."),
    ("versioning", "History, restore and field-level diff."),
    ("governance", "RBAC permissions and public-access policies."),
    ("workflow", "Review/approval state machine."),
    ("media", "Managed assets + pluggable blob storage."),
    ("packaging", "Portable content bundles (export/import)."),
    ("graph", "Backlinks, metrics and canvas (Obsidian-style)."),
    ("runtime", "RAG export snapshot and index rebuild."),
    ("localization", "Per-culture variants and translatable dictionary."),
    ("analytics", "Content health, audit, activity dashboard."),
    ("webhooks", "Outbound delivery (Outbox) + notification channels."),
    ("search", "Federated, faceted search across the knowledge base."),
    ("subscriptions", "Watchers + derived activity inbox."),
    ("blueprints", "Reusable content templates (instantiate from blueprint)."),
    ("trash", "Recycle bin: list, restore and purge deleted content."),
    ("locks", "Edit locks: who is editing, acquire/release with conflict rules."),
)

_PATTERNS: tuple[str, ...] = (
    "Repository",
    "Unit of Work",
    "Domain Events + in-process Event Bus",
    "Hexagonal Ports & Adapters",
    "CQRS-lite (command/query split)",
    "Specification",
    "Strategy (LLM/embedding/storage providers)",
    "Plugin / SPI",
    "Result type",
    "State Machine (workflow)",
    "Outbox (webhooks)",
    "Circuit Breaker (online LLM resilience)",
    "Composition Root (this facade)",
)


class ArcHubPlatform:
    """Facade exposing every bounded-context service on shared infrastructure."""

    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        plugin_host: PluginHost | None = None,
        event_bus: EventBus | None = None,
        settings: ArcHubSettings | None = None,
    ) -> None:
        self._settings = settings or ArcHubSettings.from_env()
        self._cms = cms or get_archub_cms_service()
        self._host = plugin_host or get_plugin_host(settings=self._settings)
        self._bus = event_bus or get_event_bus()

    # -- shared infrastructure --------------------------------------------

    @property
    def cms(self) -> ArcHubCMSService:
        return self._cms

    @property
    def plugin_host(self) -> PluginHost:
        return self._host

    @property
    def event_bus(self) -> EventBus:
        return self._bus

    # -- bounded-context services (lazily built, shared deps) -------------

    @cached_property
    def knowledge(self) -> ArcHubKnowledgeBaseService:
        return get_archub_knowledge_base_service(self._cms, plugin_host=self._host)

    @cached_property
    def content(self) -> ContentService:
        return get_archub_content_service(cms=self._cms, event_bus=self._bus)

    @cached_property
    def collaboration(self) -> CollaborationService:
        return get_archub_collaboration_service(db_path=self._cms.db_path, event_bus=self._bus)

    @cached_property
    def modeling(self) -> ModelingQueryService:
        return get_archub_modeling_query_service(cms=self._cms)

    @cached_property
    def delivery(self) -> DeliveryReadService:
        return get_archub_delivery_read_service(cms=self._cms)

    @cached_property
    def versioning(self) -> VersioningQueryService:
        return get_archub_versioning_query_service(cms=self._cms)

    @cached_property
    def governance(self) -> GovernanceQueryService:
        return get_archub_governance_query_service(cms=self._cms)

    @cached_property
    def workflow(self) -> WorkflowQueryService:
        return get_archub_workflow_query_service(cms=self._cms)

    @cached_property
    def media(self) -> MediaQueryService:
        return get_archub_media_query_service(cms=self._cms)

    @cached_property
    def packaging(self) -> PackagingService:
        return get_archub_packaging_service(cms=self._cms)

    @cached_property
    def graph(self) -> GraphService:
        return get_archub_graph_service(self.knowledge)

    @cached_property
    def runtime(self) -> RuntimeQueryService:
        return get_archub_runtime_query_service(cms=self._cms)

    @cached_property
    def localization(self) -> LocalizationQueryService:
        return get_archub_localization_query_service(cms=self._cms)

    @cached_property
    def analytics(self) -> AnalyticsService:
        return get_archub_analytics_service(cms=self._cms)

    @cached_property
    def webhooks(self) -> WebhooksQueryService:
        return get_archub_webhooks_query_service(cms=self._cms)

    @cached_property
    def search(self) -> SearchService:
        return get_archub_search_service(self.knowledge)

    @cached_property
    def subscriptions(self) -> SubscriptionQueryService:
        return get_archub_subscription_query_service(cms=self._cms)

    @cached_property
    def blueprints(self) -> BlueprintQueryService:
        return get_archub_blueprint_query_service(cms=self._cms)

    @cached_property
    def trash(self) -> TrashQueryService:
        return get_archub_trash_query_service(cms=self._cms)

    @cached_property
    def locks(self) -> LockQueryService:
        return get_archub_lock_query_service(cms=self._cms)

    @cached_property
    def plugins(self) -> PluginManagementService:
        return get_archub_plugin_management_service(settings=self._settings)

    # -- self-description --------------------------------------------------

    def capabilities(self) -> dict[str, Any]:
        report = self._host.report()
        return {
            "product": "ArcHub knowledge platform",
            "bounded_contexts": [{"name": name, "description": desc} for name, desc in _CONTEXTS],
            "context_count": len(_CONTEXTS),
            "architectural_patterns": list(_PATTERNS),
            "plugins": {
                "loaded": report["loaded_total"],
                "extension_points": {
                    "event_hooks": report["event_hooks"],
                    "search": report["search_extensions"],
                    "renderers": report["renderers"],
                    "macros": len(report["macros"]),
                    "importers": len(report["importers"]),
                    "exporters": len(report["exporters"]),
                    "llm_tools": len(report["llm_tools"]),
                    "auth_providers": report["auth_providers"],
                    "storage_backends": len(report["storage_backends"]),
                    "notification_channels": len(report["notification_channels"]),
                },
                "capability_counts": report["capability_counts"],
            },
            "llm": {
                "provider": self._settings.llm_provider,
                "online_configured": bool(self._settings.llm_base_url),
                "offline_default": "hashing-embedder + extractive-llm",
            },
        }


def get_archub_platform(
    *,
    cms: ArcHubCMSService | None = None,
    plugin_host: PluginHost | None = None,
    settings: ArcHubSettings | None = None,
) -> ArcHubPlatform:
    """Build a platform facade bound to the current CMS/host.

    The facade is cheap — context services are lazy ``cached_property`` — so a
    fresh instance per call is fine; hold the returned object to reuse it.
    """
    return ArcHubPlatform(cms=cms, plugin_host=plugin_host, settings=settings)
