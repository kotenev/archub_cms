"""Example dashboard widget: recent pages."""

from __future__ import annotations

from archub_cms.extensibility.extension_points import DashboardWidgetExt


class RecentPagesWidget(DashboardWidgetExt):
    widget_type = "recent_pages"
    widget_name = "Recent Pages"

    def render(self, config: dict) -> dict:
        limit = config.get("limit", 10)
        return {
            "widget_type": self.widget_type,
            "widget_name": self.widget_name,
            "pages": [],
            "limit": limit,
            "message": "Configure this widget to show recent pages",
        }
