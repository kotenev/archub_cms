"""Media/DAM application service for ArcHub CMS."""

from __future__ import annotations

__all__ = [
    "MediaLibraryReport",
    "MediaPolicy",
    "ArcHubMediaService",
    "get_archub_media_service",
]

import json
import re
from dataclasses import dataclass
from typing import Any

from archub_cms.services.cms import ArcHubCMSService, MediaAsset, get_archub_cms_service
from archub_cms.settings import ArcHubSettings

_DEFAULT_ALLOWED_TYPES = (
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "video/mp4",
    "audio/mpeg",
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/json",
)


@dataclass(frozen=True)
class MediaPolicy:
    """Upload/reference policy inspired by modern CMS media libraries."""

    allowed_content_types: tuple[str, ...] = _DEFAULT_ALLOWED_TYPES
    require_alt_text_for_images: bool = True

    @classmethod
    def from_settings(cls, settings: ArcHubSettings | None = None) -> MediaPolicy:
        source = settings or ArcHubSettings.from_env()
        return cls(allowed_content_types=source.allowed_media_content_types)

    def allows(self, content_type: str) -> bool:
        clean = content_type.strip().lower()
        if not clean:
            return False
        for allowed in self.allowed_content_types:
            allowed_clean = allowed.strip().lower()
            if allowed_clean.endswith("/*") and clean.startswith(allowed_clean[:-1]):
                return True
            if clean == allowed_clean:
                return True
        return False

    def validate(self, *, content_type: str, alt_text: str = "") -> list[str]:
        errors: list[str] = []
        if not self.allows(content_type):
            errors.append(f"Media content type is not allowed: {content_type}")
        if (
            self.require_alt_text_for_images
            and content_type.strip().lower().startswith("image/")
            and not alt_text.strip()
        ):
            errors.append("Image media requires alt text.")
        return errors


@dataclass(frozen=True)
class MediaLibraryReport:
    assets: tuple[MediaAsset, ...]
    folders: tuple[dict[str, Any], ...]
    duplicates: tuple[dict[str, Any], ...]
    orphaned_assets: tuple[dict[str, Any], ...]
    usage: dict[str, list[dict[str, Any]]]
    policy: MediaPolicy

    def as_dict(self) -> dict[str, Any]:
        orphaned_ids = {item["asset_id"] for item in self.orphaned_assets}
        return {
            "assets": [
                {
                    **_asset_payload(asset),
                    "usage": self.usage.get(asset.asset_id, []),
                    "usage_count": len(self.usage.get(asset.asset_id, [])),
                    "orphaned": asset.asset_id in orphaned_ids,
                }
                for asset in self.assets
            ],
            "total": len(self.assets),
            "folders": list(self.folders),
            "duplicates": list(self.duplicates),
            "orphaned_assets": list(self.orphaned_assets),
            "policy": {
                "allowed_content_types": list(self.policy.allowed_content_types),
                "require_alt_text_for_images": self.policy.require_alt_text_for_images,
            },
        }


class ArcHubMediaService:
    """Application boundary for media library policy and reports."""

    def __init__(
        self,
        cms: ArcHubCMSService | None = None,
        policy: MediaPolicy | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._policy = policy or MediaPolicy.from_settings()

    def register_reference(
        self,
        *,
        filename: str,
        original_name: str,
        content_type: str,
        url: str,
        folder: str = "",
        alt_text: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: str,
    ) -> MediaAsset:
        errors = self._policy.validate(content_type=content_type, alt_text=alt_text)
        if errors:
            raise ValueError("; ".join(errors))
        return self._cms.register_media_reference(
            filename=filename,
            original_name=original_name,
            content_type=content_type,
            url=url,
            folder=_clean_folder(folder),
            alt_text=alt_text.strip(),
            tags=tags or [],
            metadata=metadata or {},
            created_by=created_by,
        )

    def library_report(self, *, folder: str = "", limit: int = 100) -> MediaLibraryReport:
        assets = tuple(self._cms.list_media_assets(folder=_clean_folder(folder), limit=limit))
        all_assets = tuple(self._cms.list_media_assets(limit=500))
        usage = self._usage_report(all_assets)
        return MediaLibraryReport(
            assets=assets,
            folders=self._folder_report(all_assets),
            duplicates=self._duplicate_report(all_assets),
            orphaned_assets=tuple(
                _asset_payload(asset) for asset in all_assets if not usage.get(asset.asset_id)
            ),
            usage=usage,
            policy=self._policy,
        )

    def _usage_report(self, assets: tuple[MediaAsset, ...]) -> dict[str, list[dict[str, Any]]]:
        usage: dict[str, list[dict[str, Any]]] = {asset.asset_id: [] for asset in assets}
        nodes = self._cms.list_tree(include_trashed=True)
        for node in nodes:
            haystack = json.dumps(
                {"draft": node.draft, "published": node.published},
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            for asset in assets:
                if _asset_is_referenced(asset, haystack):
                    usage[asset.asset_id].append(
                        {
                            "node_id": node.node_id,
                            "name": node.name,
                            "route_path": node.route_path,
                            "content_type_alias": node.content_type_alias,
                            "status": node.status,
                        }
                    )
        return usage

    @staticmethod
    def _folder_report(assets: tuple[MediaAsset, ...]) -> tuple[dict[str, Any], ...]:
        folders: dict[str, dict[str, Any]] = {}
        for asset in assets:
            key = asset.folder or "/"
            row = folders.setdefault(key, {"folder": key, "count": 0, "content_types": {}})
            row["count"] += 1
            content_types = row["content_types"]
            content_types[asset.content_type] = content_types.get(asset.content_type, 0) + 1
        return tuple(sorted(folders.values(), key=lambda item: str(item["folder"])))

    @staticmethod
    def _duplicate_report(assets: tuple[MediaAsset, ...]) -> tuple[dict[str, Any], ...]:
        groups: dict[str, list[MediaAsset]] = {}
        for asset in assets:
            duplicate_key = _duplicate_key(asset)
            groups.setdefault(duplicate_key, []).append(asset)
        return tuple(
            {
                "key": key,
                "count": len(items),
                "assets": [_asset_payload(item) for item in items],
            }
            for key, items in sorted(groups.items())
            if len(items) > 1
        )


def get_archub_media_service(
    cms: ArcHubCMSService | None = None,
    policy: MediaPolicy | None = None,
) -> ArcHubMediaService:
    return ArcHubMediaService(cms=cms, policy=policy)


def _asset_payload(asset: MediaAsset) -> dict[str, Any]:
    return {
        "asset_id": asset.asset_id,
        "filename": asset.filename,
        "original_name": asset.original_name,
        "content_type": asset.content_type,
        "url": asset.url,
        "folder": asset.folder,
        "alt_text": asset.alt_text,
        "tags": list(asset.tags),
        "metadata": asset.metadata,
        "created_at": asset.created_at,
        "created_by": asset.created_by,
    }


def _asset_is_referenced(asset: MediaAsset, haystack: str) -> bool:
    candidates = {
        asset.asset_id,
        asset.url,
        asset.filename,
    }
    return any(candidate and candidate in haystack for candidate in candidates)


def _duplicate_key(asset: MediaAsset) -> str:
    metadata_hash = str(asset.metadata.get("sha256") or asset.metadata.get("hash") or "").strip()
    if metadata_hash:
        return f"hash:{metadata_hash.casefold()}"
    name = re.sub(r"\s+", " ", asset.original_name.strip().casefold())
    return f"name:{name}|type:{asset.content_type.strip().casefold()}"


def _clean_folder(value: str) -> str:
    return value.strip().strip("/")
