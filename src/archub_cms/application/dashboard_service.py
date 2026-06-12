"""Dashboard service: customizable dashboard widgets."""

from __future__ import annotations

__all__ = ["DashboardService", "get_archub_dashboard_service"]

from typing import Any

from archub_cms.domain.dashboard.models import DashboardLayout, DashboardWidget
from archub_cms.extensibility.host import PluginHost, get_plugin_host


class DashboardService:
    def __init__(self, plugin_host: PluginHost | None = None) -> None:
        self._host = plugin_host or get_plugin_host()

    def get_layout(self, owner: str, space_key: str = "") -> dict[str, Any]:
        return {"layout": None, "widgets": []}

    def create_layout(
        self, owner: str, name: str = "default", space_key: str = ""
    ) -> DashboardLayout:
        from archub_cms.kernel.value_objects import Identity

        return DashboardLayout(
            layout_id=Identity.generate("layout-").value,
            owner=owner,
            space_key=space_key,
            name=name,
        )

    def add_widget(
        self, layout_id: str, widget_type: str, title: str, config: dict[str, Any]
    ) -> DashboardWidget:
        from archub_cms.kernel.value_objects import Identity

        return DashboardWidget(
            widget_id=Identity.generate("widget-").value,
            widget_type=widget_type,
            title=title,
            config=config,
        )

    def render_widget(self, widget_type: str, config: dict[str, Any]) -> dict[str, Any]:
        widgets = self._host.dashboard_widgets
        if widget_type in widgets:
            return widgets[widget_type].render(config)
        return {"error": f"Unknown widget type: {widget_type}"}


def get_archub_dashboard_service(
    plugin_host: PluginHost | None = None,
) -> DashboardService:
    return DashboardService(plugin_host=plugin_host)
