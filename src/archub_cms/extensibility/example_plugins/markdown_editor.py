"""Example editor plugin: Markdown editor with live preview."""

from __future__ import annotations

from archub_cms.extensibility.extension_points import EditorExt


class MarkdownEditorPlugin(EditorExt):
    editor_id = "markdown"
    editor_type = "text/markdown"

    def supported_content_types(self) -> tuple[str, ...]:
        return ("text/markdown", "text/x-markdown", "markdown")

    def initialize(self, config: dict) -> dict:
        return {
            "editor_id": self.editor_id,
            "editor_type": self.editor_type,
            "features": ["live-preview", "syntax-highlighting", "emoji-autocomplete"],
            "toolbar": ["bold", "italic", "link", "code", "heading", "list", "quote"],
        }
