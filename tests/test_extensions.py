"""Tests for the executable extension pipeline (Phase 3).

Covers renderers + macros, importer, exporter and LLM-tool plugins wired through
the PluginHost, plus their HTTP endpoints.
"""

from __future__ import annotations

import pytest

from archub_cms.extensibility.host import PluginHost, _parse_macro_args
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def host(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    get_archub_cms_service()
    return PluginHost().load()


def test_all_content_plugins_load(host):
    loaded = {p["plugin_id"] for p in host.report()["loaded"]}
    for plugin_id in (
        "example.content_macros",
        "example.markdown_importer",
        "example.vault_exporter",
        "example.summarize_tool",
    ):
        assert plugin_id in loaded


def test_macro_arg_parser():
    args = _parse_macro_args(' label="Stable Build" color=green count=3 ')
    assert args == {"label": "Stable Build", "color": "green", "count": "3"}


def test_render_callouts_and_macros(host):
    body = "> [!warning] Careful\n> back up first\n\n{{badge label=Stable color=green}} {{status text=done}}"
    rendered = host.render(body)
    assert "archub-callout-warning" in rendered
    assert "Careful" in rendered
    assert "archub-badge-green" in rendered
    assert ">DONE<" in rendered
    assert "{{" not in rendered  # all macros expanded


def test_unknown_macro_is_left_untouched(host):
    assert host.render("keep {{unknownmacro x=1}} me") == "keep {{unknownmacro x=1}} me"


def test_markdown_importer(host):
    docs = host.import_documents(
        "markdown",
        [
            {
                "path": "notes/intro.md",
                "content": "---\ntitle: Intro\ntags: [kb, demo]\n---\n# Intro\nBody.",
            }
        ],
    )
    assert len(docs) == 1
    assert docs[0]["title"] == "Intro"
    assert docs[0]["tags"] == ["kb", "demo"]
    assert docs[0]["body"] == "# Intro\nBody."


def test_vault_exporter_roundtrip_with_importer(host):
    docs = host.import_documents("markdown", "---\ntitle: Roundtrip\n---\n# Roundtrip\nHello.")
    out = host.export_documents("obsidian-vault", docs)
    assert out["format"] == "obsidian-compatible-markdown-vault"
    assert out["total"] == 1
    content = out["files"][0]["content"]
    assert "title: Roundtrip" in content and "# Roundtrip" in content


def test_summarize_tool_offline(host):
    result = host.run_tool(
        "summarize", {"text": "ArcHub is a headless CMS and knowledge platform."}
    )
    assert isinstance(result, str) and result.strip()


def test_unknown_tool_raises(host):
    with pytest.raises(KeyError):
        host.run_tool("does-not-exist", {"text": "x"})


def test_extension_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        ext = client.get("/api/platform/extensions").json()
        assert "badge" in ext["macros"]
        assert "summarize" in ext["llm_tools"]

        rendered = client.post(
            "/api/platform/render", json={"body": "{{badge label=OK color=blue}}"}
        ).json()["rendered"]
        assert "archub-badge-blue" in rendered

        imported = client.post(
            "/api/platform/import/markdown",
            json={"source": "---\ntitle: API\n---\n# API\nbody"},
        ).json()
        assert imported["total"] == 1

        exported = client.post(
            "/api/platform/export/obsidian-vault", json={"documents": imported["documents"]}
        ).json()
        assert exported["total"] == 1

        tool = client.post("/api/platform/tools/summarize/run", json={"arguments": {"text": "hi"}})
        assert tool.status_code == 200
        assert tool.json()["tool"] == "summarize"

        missing = client.post("/api/platform/import/nope", json={"source": "x"})
        assert missing.status_code == 404
