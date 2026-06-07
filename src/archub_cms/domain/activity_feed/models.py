"""Activity feed domain models."""

from __future__ import annotations

__all__ = ["ActivityEntry", "ActivityType"]

from dataclasses import dataclass
from typing import Any


class ActivityType:
    PAGE_CREATED = "page_created"
    PAGE_UPDATED = "page_updated"
    PAGE_DELETED = "page_deleted"
    COMMENT_ADDED = "comment_added"
    COMMENT_RESOLVED = "comment_resolved"
    FILE_UPLOADED = "file_uploaded"
    SPACE_CREATED = "space_created"
    USER_JOINED = "user_joined"
    TEMPLATE_USED = "template_used"
    EXPORT_COMPLETED = "export_completed"
    IMPORT_COMPLETED = "import_completed"


@dataclass(frozen=True)
class ActivityEntry:
    entry_id: str
    activity_type: str
    actor: str
    target_type: str
    target_id: str
    space_key: str = ""
    summary: str = ""
    metadata: dict[str, Any] | None = None
    timestamp: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "activity_type": self.activity_type,
            "actor": self.actor,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "space_key": self.space_key,
            "summary": self.summary,
            "metadata": self.metadata or {},
            "timestamp": self.timestamp,
        }
