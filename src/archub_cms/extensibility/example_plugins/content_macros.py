"""Example plugin: content macros + a callout renderer (Confluence/Obsidian style).

Registers three extensions in one plugin:

* the plugin itself as a :class:`RendererExt` that turns Obsidian-style callout
  blocks (``> [!note] Title``) into HTML;
* a ``{{badge}}`` :class:`MacroExt` (Confluence-style badge/label);
* a ``{{status}}`` :class:`MacroExt` (Confluence-style status lozenge).

Whole-body renderers run first, then ``{{macro}}`` tokens are expanded by the
host's render pipeline.
"""

from __future__ import annotations

__all__ = ["ContentMacrosPlugin"]

import html
import re
from typing import Any

from archub_cms.extensibility.extension_points import PluginContext

_CALLOUT_RE = re.compile(
    r"(?:^>\s*\[!(?P<type>[a-zA-Z]+)\]\s*(?P<title>.*)\n?(?P<body>(?:^>.*\n?)*))",
    re.MULTILINE,
)


class BadgeMacro:
    macro_name = "badge"

    def expand(self, arguments: dict[str, Any]) -> str:
        label = html.escape(str(arguments.get("label") or "badge"))
        color = html.escape(str(arguments.get("color") or "blue"))
        return f'<span class="archub-badge archub-badge-{color}">{label}</span>'


class StatusMacro:
    macro_name = "status"

    def expand(self, arguments: dict[str, Any]) -> str:
        text = html.escape(str(arguments.get("text") or "todo")).upper()
        return f'<span class="archub-status">{text}</span>'


class ContentMacrosPlugin:
    def setup(self, context: PluginContext) -> None:
        context.register(self)
        context.register(BadgeMacro())
        context.register(StatusMacro())

    def render(self, body: str, *, context: dict[str, Any]) -> str:
        def _replace(match: re.Match[str]) -> str:
            kind = match.group("type").lower()
            title = match.group("title").strip() or kind.capitalize()
            raw_body = match.group("body") or ""
            lines = [line.lstrip("> ").rstrip() for line in raw_body.splitlines()]
            inner = " ".join(line for line in lines if line)
            return (
                f'<div class="archub-callout archub-callout-{kind}">'
                f"<strong>{html.escape(title)}</strong> {html.escape(inner)}</div>"
            )

        return _CALLOUT_RE.sub(_replace, body)
