"""Tests for the ArcHub Platform SDK release artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from archub_cms.application.sdk_release import sdk_release_manifest
from archub_cms.tools.sdk_release import main as sdk_release_main

SDK_ROOT = Path(__file__).resolve().parents[1] / "sdk" / "python"
sys.path.insert(0, str(SDK_ROOT))

from archub_platform_sdk import ArcHubClient, ArcHubResponse, PluginManifest  # noqa: E402


def test_sdk_release_manifest_matches_static_artifact():
    root = Path(__file__).resolve().parents[1]
    artifact = json.loads((root / "sdk" / "release" / "archub-sdk-1.0.0.json").read_text())
    manifest = sdk_release_manifest()

    assert manifest["name"] == artifact["name"] == "ArcHub Platform SDK"
    assert manifest["version"] == artifact["version"] == "1.0.0"
    assert "plugin_management" in manifest["api_groups"]
    assert "sdk/openapi/archub-platform-sdk.openapi.yaml" in manifest["artifacts"]


def test_sdk_client_builds_expected_requests_with_injected_transport():
    calls: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def transport(spec, url, headers, body, timeout):
        calls.append((spec.method, url, headers, body))
        return ArcHubResponse(status=200, headers={}, data={"ok": True, "path": spec.path})

    client = ArcHubClient("http://archub.test", token="token", transport=transport)

    result = client.knowledge_search("cms", space_key="ARCH", limit=3)

    assert result["ok"] is True
    method, url, headers, body = calls[0]
    assert method == "GET"
    assert url == "http://archub.test/api/platform/knowledge/search?q=cms&space_key=ARCH&limit=3"
    assert headers["Authorization"] == "Bearer token"
    assert body is None

    client.delivery_tree(start_item="/cms/demo")
    _, tree_url, tree_headers, _ = calls[1]
    assert tree_url == "http://archub.test/cms/api/tree"
    assert tree_headers["Start-Item"] == "/cms/demo"


def test_sdk_plugin_manifest_builder_validates_external_plugins():
    manifest = PluginManifest(
        plugin_id="acme.wiki.bridge",
        name="Acme Wiki Bridge",
        version="1.0.0",
        capability="connector",
        runtime="external",
        entrypoint="https://wiki.example.test/api/arc-tool",
        provides=("wiki.bridge",),
    )

    payload = json.loads(manifest.to_json())

    assert payload["id"] == "acme.wiki.bridge"
    assert payload["runtime"] == "external"
    assert payload["provides"] == ["wiki.bridge"]


def test_sdk_openapi_contract_lists_core_groups():
    root = Path(__file__).resolve().parents[1]
    text = (root / "sdk" / "openapi" / "archub-platform-sdk.openapi.yaml").read_text()

    assert "/api/platform/capabilities:" in text
    assert "/api/platform/core-plugins/rust-workspace:" in text
    assert "/api/platform/modules/marketplace/install:" in text
    assert "/api/platform/knowledge/answer:" in text


def test_sdk_release_cli_outputs_summary_and_json(capsys):
    assert sdk_release_main([]) == 0
    summary = capsys.readouterr().out
    assert "ArcHub Platform SDK 1.0.0" in summary

    assert sdk_release_main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["package"] == "archub-platform-sdk"
