"""Offline BPMN workflow editor — a self-contained ArcHub editor plugin.

Unlike the bpmn-js (CDN) editor, this plugin ships a dependency-free, vanilla-JS
SVG editor as static assets served by the host itself, so workflow editing works
with **no internet access**. It registers an :class:`EditorExt` so the platform's
editor registry discovers it, and exposes its bundled assets for the ITSM workflow
page to load.
"""

from __future__ import annotations

from archub_cms.extensibility.example_plugins.bpmn_editor.plugin import (
    BpmnEditorPlugin,
    OfflineBpmnEditor,
)

__all__ = ["BpmnEditorPlugin", "OfflineBpmnEditor"]
