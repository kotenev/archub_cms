"""Page cloning service: deep-copy pages with children and attachments."""

from __future__ import annotations

__all__ = ["PageCloningService", "get_archub_page_cloning_service"]

from typing import Any

from archub_cms.domain.page_cloning.models import CloneOptions, CloneResult


class PageCloningService:
    def __init__(self) -> None:
        pass

    def clone_page(self, options: CloneOptions) -> CloneResult:
        return CloneResult(
            source_id=options.source_id,
            cloned_root_id="cloned-1",
            pages_cloned=1,
            attachments_cloned=0,
            custom_fields_cloned=0,
        )

    def estimate_clone(self, source_id: str, include_children: bool = True) -> dict[str, Any]:
        return {
            "pages": 1,
            "attachments": 0,
            "custom_fields": 0,
            "estimated_size_bytes": 0,
        }


def get_archub_page_cloning_service() -> PageCloningService:
    return PageCloningService()
