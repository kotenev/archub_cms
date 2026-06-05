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
    "AuthExt",
    "EventHookExt",
    "ExporterExt",
    "ImporterExt",
    "LLMToolExt",
    "MacroExt",
    "Plugin",
    "PluginContext",
    "RendererExt",
    "SearchExt",
    "SearchHit",
    "StorageExt",
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
