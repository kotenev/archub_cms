"""The ArcHub extensibility runtime — the executable plugin platform.

Unlike the manifest-only registry in ``application/plugins.py`` (which discovers
but never runs code), this package *loads and runs* plugins, the defining
capability of Wiki.js / Obsidian / Confluence. Plugins declare a manifest
(``domain/plugins.py``) and are instantiated by a loader chosen from the
manifest ``runtime``:

* ``python`` → :class:`InProcessLoader` (trusted importlib entrypoint)
* ``http`` / ``external`` → :class:`HttpToolLoader` (sandboxed Forge-style tool)

Declared ``permissions`` are checked by :class:`PermissionGate`; per-plugin
enable/settings live in :class:`PluginConfigStore`. Event-hook plugins subscribe
to the kernel :class:`EventBus`, so a ``content.published`` event fans out to
every enabled plugin.
"""

from __future__ import annotations

from archub_cms.extensibility.config_store import PluginConfigStore
from archub_cms.extensibility.extension_points import (
    EventHookExt,
    LLMToolExt,
    Plugin,
    PluginContext,
    SearchExt,
    SearchHit,
)
from archub_cms.extensibility.host import PluginHost, get_plugin_host
from archub_cms.extensibility.loaders import HttpToolLoader, InProcessLoader, PluginLoadError
from archub_cms.extensibility.permissions import PermissionGate

__all__ = [
    "EventHookExt",
    "HttpToolLoader",
    "InProcessLoader",
    "LLMToolExt",
    "PermissionGate",
    "Plugin",
    "PluginConfigStore",
    "PluginContext",
    "PluginHost",
    "PluginLoadError",
    "SearchExt",
    "SearchHit",
    "get_plugin_host",
]
