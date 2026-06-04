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
    "LLMRequest",
    "LLMResponse",
    "LLMProviderPort",
    "NoopAuditSink",
    "NoopCacheInvalidationPort",
    "RuntimeImportSources",
    "RuntimeSourcePort",
    "TemplatePort",
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


class NoopCacheInvalidationPort:
    def invalidate(self, *keys: str) -> None:
        return None


class NoopAuditSink:
    def record(self, event: AuditEvent) -> None:
        return None
