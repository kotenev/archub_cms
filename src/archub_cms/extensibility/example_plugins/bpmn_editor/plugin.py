"""The offline BPMN editor plugin and its :class:`EditorExt` extension."""

from __future__ import annotations

__all__ = ["BpmnEditorPlugin", "OfflineBpmnEditor"]

from pathlib import Path
from typing import Any

from archub_cms.extensibility.extension_points import EditorExt

_ASSET_DIR = Path(__file__).resolve().parent / "static"
# Only these files may be served, by name — no arbitrary path access.
_ASSETS = {
    "bpmn_editor.js": "application/javascript",
    "bpmn_editor.css": "text/css",
}


class OfflineBpmnEditor(EditorExt):
    """A self-hosted, no-network BPMN/workflow editor registered with the platform."""

    editor_id = "bpmn-offline"
    editor_type = "application/bpmn+xml"

    def supported_content_types(self) -> tuple[str, ...]:
        return ("application/bpmn+xml", "application/xml", "workflow")

    def initialize(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "editor_id": self.editor_id,
            "editor_type": self.editor_type,
            "offline": True,
            "engine": "archub-svg",
            "assets": sorted(_ASSETS),
            "features": [
                "svg-canvas",
                "add-status",
                "draw-transition",
                "set-initial",
                "category-colors",
                "bpmn-export",
                "no-network",
            ],
        }

    def asset_names(self) -> tuple[str, ...]:
        return tuple(sorted(_ASSETS))

    def asset_media_type(self, name: str) -> str | None:
        return _ASSETS.get(name)

    def asset_path(self, name: str) -> Path | None:
        """Resolve a bundled asset by exact name, guarding against traversal."""

        if name not in _ASSETS:
            return None
        candidate = (_ASSET_DIR / name).resolve()
        if _ASSET_DIR.resolve() not in candidate.parents:
            return None
        return candidate if candidate.is_file() else None


class BpmnEditorPlugin:
    """In-process plugin registering the offline BPMN editor."""

    plugin_id = "archub.bpmn.editor"

    def setup(self, context: Any) -> None:
        context.register(OfflineBpmnEditor())
