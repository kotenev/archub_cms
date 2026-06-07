"""Host integration contracts for standalone ArcHub CMS."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "ArcHubUser",
    "AuditEvent",
    "AuditSink",
    "AuthPort",
    "CacheInvalidationPort",
    "ChatPort",
    "EmbeddingPort",
    "ExportPort",
    "ImportPort",
    "LLMRequest",
    "LLMResponse",
    "LLMProviderPort",
    "NoopAuditSink",
    "NoopCacheInvalidationPort",
    "RenderingPort",
    "RuntimeImportSources",
    "RuntimeSourcePort",
    "SearchPort",
    "TemplatePort",
    "WebSocketPort",
]


@dataclass(frozen=True)
class ArcHubUser:
    username: str
    is_admin: bool = False
    groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeImportSources:
    experts: tuple[Any, ...] = ()
    rag_specs: tuple[Any, ...] = ()
    bot_resource_roots: tuple[Any, ...] = ()


@dataclass(frozen=True)
class AuditEvent:
    action: str
    actor: str
    aggregate_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system_prompt: str = ""
    context: tuple[Mapping[str, Any], ...] = ()
    model: str = ""
    temperature: float = 0.1
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str = ""
    mode: str = "offline"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class AuthPort(Protocol):
    def current_user(self, request: Any) -> ArcHubUser | None:
        """Return the current editor/member identity for a host request."""


@runtime_checkable
class TemplatePort(Protocol):
    def render(
        self,
        template_name: str,
        context: Mapping[str, Any],
        *,
        status_code: int = 200,
    ) -> Any:
        """Render a host template and return a framework response object."""


@runtime_checkable
class RuntimeSourcePort(Protocol):
    def load_sources(self) -> RuntimeImportSources:
        """Load host-specific runtime content sources for CMS import."""


@runtime_checkable
class CacheInvalidationPort(Protocol):
    def invalidate(self, *keys: str) -> None:
        """Invalidate host process caches after published-content changes."""


@runtime_checkable
class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> None:
        """Record a CMS audit event."""


@runtime_checkable
class LLMProviderPort(Protocol):
    provider_name: str
    mode: str

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Synthesize an answer from a prompt and supplied knowledge context."""


@runtime_checkable
class EmbeddingPort(Protocol):
    """Turns text into a dense vector for semantic search (offline or online)."""

    model: str
    dim: int

    def embed(self, text: str) -> tuple[float, ...]:
        """Return an L2-normalized embedding vector for ``text``."""


@runtime_checkable
class SearchPort(Protocol):
    """A vector index: store document embeddings and query by similarity."""

    def index(self, route_path: str, text: str) -> None: ...

    def query(self, text: str, *, limit: int) -> list[tuple[str, float]]:
        """Return ``(route_path, similarity)`` pairs ordered by similarity desc."""


class NoopCacheInvalidationPort:
    def invalidate(self, *keys: str) -> None:
        return None


class NoopAuditSink:
    def record(self, event: AuditEvent) -> None:
        return None


@runtime_checkable
class ChatPort(Protocol):
    """Conversational AI interface over the knowledge base (ChatGPT-over-docs)."""

    def chat(
        self,
        conversation_id: str,
        message: str,
        *,
        context: tuple[Mapping[str, Any], ...] = (),
        model: str = "",
    ) -> dict[str, Any]:
        """Send a message and receive an AI response with sources."""

    def chat_stream(
        self,
        conversation_id: str,
        message: str,
        *,
        context: tuple[Mapping[str, Any], ...] = (),
        model: str = "",
    ):
        """Yield streaming chat response chunks."""


@runtime_checkable
class RenderingPort(Protocol):
    """Host rendering engine for HTML/PDF output."""

    def render_html(self, content: str, *, template: str = "", css: str = "") -> str:
        """Render content to HTML with optional template."""

    def render_pdf(self, html: str, *, options: Mapping[str, Any] | None = None) -> bytes:
        """Render HTML to PDF bytes."""


@runtime_checkable
class ExportPort(Protocol):
    """Content export to various formats (PDF, DOCX, EPUB, etc.)."""

    def export(self, content: Mapping[str, Any], *, format: str = "pdf") -> bytes:
        """Export content to the specified format."""

    def supported_formats(self) -> tuple[str, ...]:
        """Return supported export format identifiers."""


@runtime_checkable
class ImportPort(Protocol):
    """Content import from external sources (Confluence, Notion, Word, etc.)."""

    def import_data(
        self, data: bytes, *, format: str = "", options: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Import content from raw data in the specified format."""

    def supported_formats(self) -> tuple[str, ...]:
        """Return supported import format identifiers."""


@runtime_checkable
class WebSocketPort(Protocol):
    """WebSocket interface for live collaboration and real-time updates."""

    def broadcast(self, channel: str, event: Mapping[str, Any]) -> None:
        """Broadcast an event to all subscribers of a channel."""

    def subscribe(self, channel: str, handler: Any) -> None:
        """Register a handler for events on a channel."""
