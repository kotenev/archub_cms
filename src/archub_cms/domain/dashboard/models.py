"""Dashboard domain models."""

from __future__ import annotations

__all__ = ["DashboardLayout", "DashboardWidget", "WidgetType"]

from dataclasses import dataclass
from typing import Any


class WidgetType:
    RECENT_PAGES = "recent_pages"
    ACTIVITY_FEED = "activity_feed"
    BOOKMARKS = "bookmarks"
    SEARCH = "search"
    QUICK_LINKS = "quick_links"
    SPACE_LIST = "space_list"
    TAG_CLOUD = "tag_cloud"
    CUSTOM = "custom"


@dataclass(frozen=True)
class DashboardWidget:
    widget_id: str
    widget_type: str
    title: str
    config: dict[str, Any] | None = None
    position: int = 0
    width: int = 6
    height: int = 4

    def as_dict(self) -> dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_type": self.widget_type,
            "title": self.title,
            "config": self.config or {},
            "position": self.position,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class DashboardLayout:
    layout_id: str
    owner: str
    space_key: str = ""
    name: str = "default"
    widgets: tuple[DashboardWidget, ...] = ()
    is_default: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "layout_id": self.layout_id,
            "owner": self.owner,
            "space_key": self.space_key,
            "name": self.name,
            "widgets": [w.as_dict() for w in self.widgets],
            "is_default": self.is_default,
        }
