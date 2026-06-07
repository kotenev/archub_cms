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

from archub_cms.application.activity_feed_service import (
    ActivityFeedService,
    get_archub_activity_feed_service,
)
from archub_cms.application.ai_chat_service import AIChatService, get_archub_ai_chat_service
from archub_cms.application.analytics_service import AnalyticsService, get_archub_analytics_service
from archub_cms.application.audit_trail_service import (
    AuditTrailService,
    get_archub_audit_trail_service,
)
from archub_cms.application.blueprint_service import (
    BlueprintQueryService,
    get_archub_blueprint_query_service,
)
from archub_cms.application.bookmark_service import BookmarkService, get_archub_bookmark_service
from archub_cms.application.collaboration_service import (
    CollaborationService,
    get_archub_collaboration_service,
)
from archub_cms.application.comments_thread_service import (
    CommentsThreadService,
    get_archub_comments_thread_service,
)
from archub_cms.application.content_service import ContentService, get_archub_content_service
from archub_cms.application.custom_field_service import (
    CustomFieldService,
    get_archub_custom_field_service,
)
from archub_cms.application.dashboard_service import DashboardService, get_archub_dashboard_service
from archub_cms.application.delivery_read_service import (
    DeliveryReadService,
    get_archub_delivery_read_service,
)
from archub_cms.application.embedding_store_service import (
    EmbeddingStoreService,
    get_archub_embedding_store_service,
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
from archub_cms.application.live_edit_service import LiveEditService, get_archub_live_edit_service
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
from archub_cms.application.notification_hub_service import (
    NotificationHubService,
    get_archub_notification_hub_service,
)
from archub_cms.application.packaging_service import PackagingService, get_archub_packaging_service
from archub_cms.application.page_cloning_service import (
    PageCloningService,
    get_archub_page_cloning_service,
)
from archub_cms.application.pdf_export_service import (
    PDFExportService,
    get_archub_pdf_export_service,
)
from archub_cms.application.permission_service import (
    PermissionService,
    get_archub_permission_service,
)
from archub_cms.application.plugin_management_service import (
    PluginManagementService,
    get_archub_plugin_management_service,
)
from archub_cms.application.revisions_diff_service import (
    RevisionsDiffService,
    get_archub_revisions_diff_service,
)
from archub_cms.application.runtime_service import (
    RuntimeQueryService,
    get_archub_runtime_query_service,
)
from archub_cms.application.scheduler_service import (
    SchedulerService,
    get_archub_scheduler_service,
)
from archub_cms.application.search_service import SearchService, get_archub_search_service
from archub_cms.application.space_service import SpaceService, get_archub_space_service
from archub_cms.application.subscription_service import (
    SubscriptionQueryService,
    get_archub_subscription_query_service,
)
from archub_cms.application.tag_service import TagService, get_archub_tag_service
from archub_cms.application.template_service import TemplateService, get_archub_template_service
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

_CONTEXTS: tuple[tuple[str, str], ...] = (
    ("content", "Authoring: the content-tree aggregate, drafts, publishing."),
    ("knowledge", "Knowledge base: spaces, documents, hybrid RAG answers."),
    ("collaboration", "Comments, @mentions and reactions."),
    ("comments_thread", "Threaded comment discussions with replies and resolutions."),
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
    ("scheduler", "Cron-like scheduled jobs and maintenance tasks."),
    ("audit_trail", "Immutable audit log with query and compliance support."),
    ("notifications", "Notification hub with per-user preferences and channels."),
    ("tags", "Hierarchical tag taxonomy (Confluence/Obsidian-style)."),
    ("bookmarks", "User bookmarks and folders (favorites/stars)."),
    ("spaces", "Confluence-style knowledge spaces with settings."),
    ("templates", "Reusable page templates with categories and extraction."),
    ("permissions", "Fine-grained page/space permission matrix."),
    ("ai_chat", "Conversational AI interface over the knowledge base."),
    ("dashboard", "Customizable dashboard widgets per user/space."),
    ("activity_feed", "Chronological activity stream across the knowledge base."),
    ("custom_fields", "User-defined metadata fields (Jira/Confluence-style)."),
    ("page_cloning", "Deep-copy pages with children and attachments."),
    ("pdf_export", "On-demand PDF and multi-format export."),
    ("embedding_store", "Vector embedding management and similarity search."),
    ("revisions_diff", "Side-by-side and inline diff for page history."),
    ("live_edit", "Real-time collaborative editing with presence tracking."),
)

_PATTERNS: tuple[str, ...] = (
    "Repository",
    "Unit of Work",
    "Domain Events + in-process Event Bus",
    "Hexagonal Ports & Adapters",
    "CQRS-lite (command/query split)",
    "CQRS Mediator (dispatch pipeline)",
    "Specification",
    "Strategy (LLM/embedding/storage providers)",
    "Plugin / SPI (28 extension points)",
    "Result type",
    "State Machine (workflow)",
    "Outbox (webhooks)",
    "Transactional Outbox (integration events)",
    "Circuit Breaker (online LLM resilience)",
    "Composition Root (this facade)",
    "Aggregate Root (event collection)",
    "Saga / Process Manager",
    "Event Store (event sourcing)",
    "Snapshot Store (aggregate optimization)",
    "Projection Store (materialized views)",
    "Domain Registry (cross-context service locator)",
    "Health Check subsystem",
    "Retry Policy (exponential backoff)",
    "Async Command Bus (background processing)",
    "Identity / Timestamp / Pagination value objects",
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

    @property
    def cms(self) -> ArcHubCMSService:
        return self._cms

    @property
    def plugin_host(self) -> PluginHost:
        return self._host

    @property
    def event_bus(self) -> EventBus:
        return self._bus

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
    def comments_thread(self) -> CommentsThreadService:
        return get_archub_comments_thread_service(event_bus=self._bus)

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

    @cached_property
    def scheduler(self) -> SchedulerService:
        return get_archub_scheduler_service(plugin_host=self._host)

    @cached_property
    def audit_trail(self) -> AuditTrailService:
        return get_archub_audit_trail_service()

    @cached_property
    def notification_hub(self) -> NotificationHubService:
        return get_archub_notification_hub_service(plugin_host=self._host)

    @cached_property
    def bookmark_service(self) -> BookmarkService:
        return get_archub_bookmark_service()

    @cached_property
    def tag_service(self) -> TagService:
        return get_archub_tag_service()

    @cached_property
    def space_service(self) -> SpaceService:
        return get_archub_space_service()

    @cached_property
    def template_service(self) -> TemplateService:
        return get_archub_template_service()

    @cached_property
    def permission_service(self) -> PermissionService:
        return get_archub_permission_service()

    @cached_property
    def ai_chat(self) -> AIChatService:
        return get_archub_ai_chat_service(plugin_host=self._host)

    @cached_property
    def dashboard(self) -> DashboardService:
        return get_archub_dashboard_service(plugin_host=self._host)

    @cached_property
    def activity_feed(self) -> ActivityFeedService:
        return get_archub_activity_feed_service(event_bus=self._bus)

    @cached_property
    def custom_field_service(self) -> CustomFieldService:
        return get_archub_custom_field_service()

    @cached_property
    def page_cloning(self) -> PageCloningService:
        return get_archub_page_cloning_service()

    @cached_property
    def pdf_export(self) -> PDFExportService:
        return get_archub_pdf_export_service(plugin_host=self._host)

    @cached_property
    def embedding_store(self) -> EmbeddingStoreService:
        return get_archub_embedding_store_service()

    @cached_property
    def revisions_diff(self) -> RevisionsDiffService:
        return get_archub_revisions_diff_service()

    @cached_property
    def live_edit(self) -> LiveEditService:
        return get_archub_live_edit_service(plugin_host=self._host)

    def capabilities(self) -> dict[str, Any]:
        report = self._host.report()
        return {
            "product": "ArcHub knowledge platform",
            "version": "2.0.0",
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
                    "themes": len(report.get("themes", [])),
                    "scheduled_jobs": len(report.get("scheduled_jobs", [])),
                    "analytics_providers": len(report.get("analytics_providers", [])),
                    "workflow_actions": len(report.get("workflow_actions", [])),
                    "content_transformers": len(report.get("content_transformers", [])),
                    "search_indexers": len(report.get("search_indexers", [])),
                    "security_policies": len(report.get("security_policies", [])),
                    "editors": len(report.get("editors", [])),
                    "connectors": len(report.get("connectors", [])),
                    "chat_handlers": len(report.get("chat_handlers", [])),
                    "dashboard_widgets": len(report.get("dashboard_widgets", [])),
                    "export_formats": len(report.get("export_formats", [])),
                    "import_formats": len(report.get("import_formats", [])),
                    "live_edit_providers": len(report.get("live_edit_providers", [])),
                    "page_actions": len(report.get("page_actions", [])),
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
    return ArcHubPlatform(cms=cms, plugin_host=plugin_host, settings=settings)
