"""Page template domain models."""

from __future__ import annotations

__all__ = ["PageTemplate", "TemplateCategory"]

from dataclasses import dataclass
from typing import Any


class TemplateCategory:
    BLANK = "blank"
    MEETING_NOTES = "meeting_notes"
    DECISION = "decision"
    HOWTO = "howto"
    KB_ARTICLE = "kb_article"
    CHANGE_LOG = "change_log"
    RETROSPECTIVE = "retrospective"
    CUSTOM = "custom"


@dataclass(frozen=True)
class PageTemplate:
    template_id: str
    name: str
    body: str
    category: str = TemplateCategory.BLANK
    icon: str = "📄"
    description: str = ""
    source_node_id: str = ""
    space_key: str = ""
    created_by: str = ""
    created_at: float = 0.0
    usage_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "body": self.body,
            "category": self.category,
            "icon": self.icon,
            "description": self.description,
            "source_node_id": self.source_node_id,
            "space_key": self.space_key,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "usage_count": self.usage_count,
        }
