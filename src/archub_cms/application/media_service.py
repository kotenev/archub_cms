"""Application service for the media context + pluggable blob storage.

``MediaQueryService`` lists asset metadata; ``MediaCommandService.register``
validates a :class:`MediaAsset` (content-type allow-list from settings), persists
via the legacy service, and emits ``media.registered``. ``StorageService`` wraps
the plugin host's ``StorageExt`` backends for blob put/get.
"""

from __future__ import annotations

__all__ = [
    "MediaCommandService",
    "MediaQueryService",
    "StorageService",
    "get_archub_media_query_service",
]

from collections.abc import Iterable, Mapping
from typing import Any

from archub_cms.domain.media.asset import MediaAsset
from archub_cms.domain.media.repository import MediaRepository
from archub_cms.infrastructure.sqlite.media_repository import CmsMediaRepository
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service
from archub_cms.settings import ArcHubSettings


class MediaQueryService:
    def __init__(self, repository: MediaRepository) -> None:
        self._repo = repository

    def assets(self, *, folder: str = "", limit: int = 100) -> dict[str, Any]:
        items = self._repo.list_assets(folder=folder, limit=limit)
        return {"items": [a.as_dict() for a in items], "total": len(items)}

    def folders(self) -> dict[str, Any]:
        items = self._repo.list_assets(limit=500)
        folders = sorted({a.folder for a in items if a.folder})
        return {"folders": folders, "total": len(folders)}


class MediaCommandService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        settings: ArcHubSettings | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._settings = settings or ArcHubSettings.from_env()
        self._bus = event_bus or get_event_bus()

    def register(
        self,
        *,
        filename: str,
        content_type: str,
        url: str = "",
        original_name: str = "",
        folder: str = "",
        alt_text: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: str,
    ) -> MediaAsset:
        clean_tags = _tags_tuple(tags)
        clean_metadata = _metadata_dict(metadata)
        candidate = MediaAsset(
            asset_id="",
            filename=filename,
            content_type=content_type,
            url=url,
            original_name=original_name or filename,
            folder=folder,
            alt_text=alt_text,
            tags=clean_tags,
            metadata=clean_metadata,
        )
        errors = candidate.validate(
            allowed_content_types=self._settings.allowed_media_content_types
        )
        if errors:
            raise ValueError("; ".join(errors))

        stored = self._cms.register_media_reference(
            filename=filename,
            original_name=original_name or filename,
            content_type=content_type,
            url=url,
            folder=folder,
            alt_text=alt_text,
            tags=list(clean_tags),
            metadata=dict(clean_metadata),
            created_by=created_by,
        )
        # Distinct from the legacy activity action "media.registered" emitted by
        # cms._record_activity, so subscribers see exactly one domain event.
        self._bus.publish(
            ArcHubDomainEvent(
                event_type="media.asset.registered",
                aggregate_id=stored.asset_id,
                actor=created_by,
                metadata={"content_type": stored.content_type, "folder": stored.folder},
            )
        )
        return MediaAsset(
            asset_id=stored.asset_id,
            filename=stored.filename,
            content_type=stored.content_type,
            url=stored.url,
            original_name=stored.original_name,
            folder=stored.folder,
            alt_text=stored.alt_text,
            tags=_tags_tuple(stored.tags),
            metadata=_metadata_dict(stored.metadata),
            created_at=stored.created_at,
            created_by=stored.created_by,
        )


class StorageService:
    """Blob put/get over the plugin host's StorageExt backends."""

    def __init__(self, *, plugin_host: Any) -> None:
        self._host = plugin_host

    def backends(self) -> list[str]:
        return sorted(self._host.storage_backends)

    def put(self, backend: str, key: str, data: bytes) -> dict[str, Any]:
        store = self._require(backend)
        store.write(key, data)
        return {"backend": backend, "key": key, "bytes": len(data)}

    def get(self, backend: str, key: str) -> bytes:
        return self._require(backend).read(key)

    def _require(self, backend: str) -> Any:
        store = self._host.storage(backend)
        if store is None:
            raise KeyError(f"no storage backend named {backend!r}")
        return store


def get_archub_media_query_service(
    *, cms: ArcHubCMSService | None = None, repository: MediaRepository | None = None
) -> MediaQueryService:
    return MediaQueryService(repository or CmsMediaRepository(cms))


def _tags_tuple(tags: Iterable[str] | None) -> tuple[str, ...]:
    if tags is None:
        return ()
    return tuple(str(tag) for tag in tags if str(tag).strip())


def _metadata_dict(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    return {str(key): value for key, value in metadata.items()}
