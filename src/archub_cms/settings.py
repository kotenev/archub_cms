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

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ArcHubSettings:
        source = os.environ if env is None else env
        return cls(
            cms_db_path=Path(source.get("ARCHUB_CMS_DB", "data/archub_cms.db")),
            runtime_export_dir=Path(
                source.get("ARCHUB_RUNTIME_EXPORT_DIR", "data/archub_runtime")
            ),
            public_root=_public_root(source.get("ARCHUB_PUBLIC_ROOT", "/cms")),
            delivery_cache_max_age_seconds=_positive_int(
                source.get("ARCHUB_DELIVERY_CACHE_MAX_AGE"),
                60,
            ),
            delivery_cache_stale_revalidate_seconds=_positive_int(
                source.get("ARCHUB_DELIVERY_CACHE_STALE_REVALIDATE"),
                300,
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


def _public_root(value: str) -> str:
    clean = value.strip() or "/cms"
    if not clean.startswith("/"):
        clean = f"/{clean}"
    return clean.rstrip("/") or "/cms"
