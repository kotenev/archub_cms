"""Example theme plugin demonstrating ThemeExt."""

from __future__ import annotations

from typing import Any

from archub_cms.extensibility.extension_points import ThemeExt


class DarkModeTheme:
    """A dark-mode theme plugin (Wiki.js/Confluence-style theming)."""

    theme_id = "dark-mode"

    def setup(self, context: Any) -> None:
        context.register(DarkTheme())
        context.register(LightTheme())


class DarkTheme(ThemeExt):
    theme_id = "dark"

    def styles(self) -> str:
        return """
        :root { --bg: #1a1a2e; --fg: #e0e0e0; --accent: #0f3460; --card: #16213e; }
        body { background: var(--bg); color: var(--fg); }
        .card { background: var(--card); border: 1px solid var(--accent); }
        """

    def layout_overrides(self) -> dict[str, Any]:
        return {"sidebar_position": "left", "header_style": "compact"}


class LightTheme(ThemeExt):
    theme_id = "light"

    def styles(self) -> str:
        return """
        :root { --bg: #ffffff; --fg: #1a1a2e; --accent: #0B7285; --card: #f8f9fa; }
        body { background: var(--bg); color: var(--fg); }
        .card { background: var(--card); border: 1px solid #dee2e6; }
        """

    def layout_overrides(self) -> dict[str, Any]:
        return {"sidebar_position": "left", "header_style": "expanded"}
