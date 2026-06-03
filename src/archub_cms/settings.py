"""Configuration model for standalone ArcHub CMS."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

__all__ = ["ArcHubSettings"]


@dataclass(frozen=True)
class ArcHubSettings:
    cms_db_path: Path = Path("data/archub_cms.db")
    runtime_export_dir: Path = Path("data/archub_runtime")
    public_root: str = "/cms"
    delivery_cache_max_age_seconds: int = 60
    delivery_cache_stale_revalidate_seconds: int = 300
    background_jobs_enabled: bool = False
    background_job_interval_seconds: int = 60
    webhook_dispatch_limit: int = 50
    allowed_media_content_types: tuple[str, ...] = (
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

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ArcHubSettings:
        source = os.environ if env is None else env
        return cls(
            cms_db_path=Path(source.get("ARCHUB_CMS_DB", "data/archub_cms.db")),
            runtime_export_dir=Path(source.get("ARCHUB_RUNTIME_EXPORT_DIR", "data/archub_runtime")),
            public_root=_public_root(source.get("ARCHUB_PUBLIC_ROOT", "/cms")),
            delivery_cache_max_age_seconds=_positive_int(
                source.get("ARCHUB_DELIVERY_CACHE_MAX_AGE"),
                60,
            ),
            delivery_cache_stale_revalidate_seconds=_positive_int(
                source.get("ARCHUB_DELIVERY_CACHE_STALE_REVALIDATE"),
                300,
            ),
            background_jobs_enabled=_truthy(source.get("ARCHUB_BACKGROUND_JOBS")),
            background_job_interval_seconds=_positive_int(
                source.get("ARCHUB_BACKGROUND_JOB_INTERVAL"),
                60,
            ),
            webhook_dispatch_limit=_positive_int(source.get("ARCHUB_WEBHOOK_DISPATCH_LIMIT"), 50),
            allowed_media_content_types=_csv_tuple(
                source.get("ARCHUB_ALLOWED_MEDIA_CONTENT_TYPES"),
                cls.allowed_media_content_types,
            ),
        )


def _positive_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_tuple(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


def _public_root(value: str) -> str:
    clean = value.strip() or "/cms"
    if not clean.startswith("/"):
        clean = f"/{clean}"
    return clean.rstrip("/") or "/cms"
