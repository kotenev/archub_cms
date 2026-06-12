"""Plugin loaders: trusted in-process Python and sandboxed HTTP tools.

The loader is chosen per-manifest by its ``runtime`` field, so a single host can
mix fully-trusted local plugins with isolated remote tools (the "host chooses
per-plugin" model).
"""

from __future__ import annotations

__all__ = ["HttpToolLoader", "InProcessLoader", "PluginLoadError", "select_loader"]

import importlib
import json
import urllib.error
import urllib.request
from typing import Any

from archub_cms.domain.plugins import KnowledgePluginManifest


class PluginLoadError(Exception):
    """Raised when a plugin cannot be instantiated from its manifest."""


class InProcessLoader:
    """Load a trusted plugin object from a ``module:attribute`` entrypoint."""

    runtime = "python"

    def load(self, manifest: KnowledgePluginManifest) -> Any:
        entrypoint = manifest.entrypoint.strip()
        if ":" not in entrypoint:
            raise PluginLoadError(
                f"{manifest.plugin_id}: python entrypoint must be 'module:attribute', "
                f"got {entrypoint!r}"
            )
        module_name, _, attribute = entrypoint.partition(":")
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise PluginLoadError(
                f"{manifest.plugin_id}: cannot import {module_name!r}: {exc}"
            ) from exc
        target = getattr(module, attribute, None)
        if target is None:
            raise PluginLoadError(
                f"{manifest.plugin_id}: {attribute!r} not found in {module_name!r}"
            )
        try:
            return target() if isinstance(target, type) else target
        except Exception as exc:  # surface any constructor failure uniformly
            raise PluginLoadError(f"{manifest.plugin_id}: instantiation failed: {exc}") from exc


class HttpTool:
    """Adapter exposing a remote HTTP endpoint as an :class:`LLMToolExt`."""

    def __init__(self, *, name: str, url: str, api_key: str = "", timeout: float = 15.0) -> None:
        self.name = name
        self._url = url
        self._api_key = api_key
        self._timeout = timeout

    def run(self, arguments: dict[str, Any]) -> str:
        body = json.dumps({"tool": self.name, "arguments": arguments}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(self._url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise PluginLoadError(f"http tool {self.name} failed: {exc}") from exc
        return str(data.get("result") or data.get("text") or "")


class HttpToolLoader:
    """Load a sandboxed plugin reachable over HTTP (Forge-style isolation)."""

    runtimes = ("http", "external")

    def load(self, manifest: KnowledgePluginManifest) -> Any:
        url = manifest.entrypoint.strip()
        if not url.startswith(("http://", "https://")):
            raise PluginLoadError(
                f"{manifest.plugin_id}: http runtime needs an http(s) entrypoint URL"
            )
        api_key = str(manifest.settings_schema.get("api_key") or "")
        return HttpTool(name=manifest.plugin_id, url=url, api_key=api_key)


def select_loader(manifest: KnowledgePluginManifest) -> InProcessLoader | HttpToolLoader:
    if manifest.runtime == "python":
        return InProcessLoader()
    if manifest.runtime in HttpToolLoader.runtimes:
        return HttpToolLoader()
    raise PluginLoadError(
        f"{manifest.plugin_id}: runtime {manifest.runtime!r} is not executable "
        "(only 'python' and 'http'/'external' run code)"
    )
