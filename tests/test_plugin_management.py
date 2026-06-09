"""Tests for plugin lifecycle management + the HTTP sandboxed loader (Phase 10)."""

from __future__ import annotations

import json
import zipfile

import pytest

from archub_cms.application.plugin_management_service import (
    get_archub_plugin_management_service,
)
from archub_cms.domain.plugins import KnowledgePluginManifest
from archub_cms.extensibility.host import PluginHost, get_plugin_host
from archub_cms.extensibility.loaders import (
    HttpTool,
    HttpToolLoader,
    PluginLoadError,
    select_loader,
)
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service
from archub_cms.settings import ArcHubSettings


def _module_zip(
    root,
    *,
    module_id: str,
    capability: str = "platform_module",
    runtime: str = "manifest",
    version: str = "1.0.0",
):
    package_dir = root / f"{module_id}-src"
    package_dir.mkdir(parents=True)
    (package_dir / "plugin.json").write_text(
        json.dumps(
            {
                "id": module_id,
                "name": module_id,
                "version": version,
                "capability": capability,
                "runtime": runtime,
                "description": "Packaged test module",
                "enabled_by_default": False,
            }
        ),
        encoding="utf-8",
    )
    (package_dir / "README.md").write_text("# Packaged module\n", encoding="utf-8")
    archive = root / f"{module_id}.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in package_dir.rglob("*"):
            zf.write(path, path.relative_to(package_dir.parent))
    return archive


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def managed(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    get_archub_cms_service()
    get_plugin_host(reload=True)
    return get_archub_plugin_management_service()


# --- management catalog + lifecycle --------------------------------------


def test_catalog_merges_manifest_config_and_host(managed):
    catalog = managed.catalog()
    assert catalog["total"] >= 8
    assert catalog["loaded_total"] >= 8
    backlinks = next(i for i in catalog["items"] if i["plugin_id"] == "example.backlinks")
    assert backlinks["enabled"] and backlinks["loaded"] and backlinks["executable"]
    # builtin host-runtime advertisements are listed but not executable/loaded
    builtin = next(i for i in catalog["items"] if i["runtime"] == "host")
    assert not builtin["executable"] and not builtin["loaded"]


def test_enable_disable_round_trip_changes_loading(managed):
    events: list[tuple[str, str]] = []
    get_event_bus().subscribe("plugin.disabled", lambda e: events.append(("off", e.aggregate_id)))
    get_event_bus().subscribe("plugin.enabled", lambda e: events.append(("on", e.aggregate_id)))

    off = managed.disable("example.notifications", actor="admin")
    assert off["enabled"] is False and off["loaded"] is False
    assert "example.notifications" not in {
        p["plugin_id"] for p in get_plugin_host().report()["loaded"]
    }

    on = managed.enable("example.notifications", actor="admin")
    assert on["loaded"] is True
    assert ("off", "example.notifications") in events
    assert ("on", "example.notifications") in events


def test_configure_persists_settings(managed):
    fired: list[str] = []
    get_event_bus().subscribe("plugin.configured", lambda e: fired.append(e.aggregate_id))
    status = managed.configure(
        "example.header_auth", {"tokens": {"t": {"username": "u"}}}, actor="a"
    )
    assert status["settings"]["tokens"] == {"t": {"username": "u"}}
    assert fired == ["example.header_auth"]


def test_unknown_plugin_errors(managed):
    with pytest.raises(KeyError):
        managed.enable("does.not.exist", actor="a")


# --- distribution install + marketplace repository -----------------------


def test_install_module_distribution_from_zip(tmp_path, monkeypatch):
    plugin_root = tmp_path / "installed"
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    monkeypatch.setenv("ARCHUB_PLUGIN_DIRS", str(plugin_root))
    get_archub_cms_service.cache_clear()
    get_archub_cms_service()
    get_plugin_host(reload=True, settings=ArcHubSettings.from_env())
    service = get_archub_plugin_management_service(settings=ArcHubSettings.from_env())
    archive = _module_zip(tmp_path, module_id="acme.rest.helpdesk", capability="rest_api")

    installed = service.install_from_file(archive, actor="admin", enable=True)

    assert installed["plugin_id"] == "acme.rest.helpdesk"
    assert installed["status"]["enabled"] is True
    assert installed["status"]["capability"] == "rest_api"
    assert (plugin_root / "acme.rest.helpdesk" / "plugin.json").exists()


def test_install_module_from_marketplace_repository(tmp_path, monkeypatch):
    plugin_root = tmp_path / "installed"
    marketplace = tmp_path / "marketplace"
    packages = marketplace / "packages"
    packages.mkdir(parents=True)
    archive = _module_zip(packages, module_id="acme.adapter.crm", capability="adapter")
    (marketplace / "marketplace.json").write_text(
        json.dumps(
            {
                "modules": [
                    {
                        "id": "acme.adapter.crm",
                        "name": "CRM Adapter",
                        "version": "1.0.0",
                        "capability": "adapter",
                        "package": f"packages/{archive.name}",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    monkeypatch.setenv("ARCHUB_PLUGIN_DIRS", str(plugin_root))
    get_archub_cms_service.cache_clear()
    get_archub_cms_service()
    get_plugin_host(reload=True, settings=ArcHubSettings.from_env())
    service = get_archub_plugin_management_service(settings=ArcHubSettings.from_env())

    catalog = service.marketplace(marketplace)
    installed = service.install_from_marketplace(marketplace, "acme.adapter.crm", enable=False)

    assert catalog["total"] == 1
    assert catalog["items"][0]["source"].endswith("acme.adapter.crm.zip")
    assert installed["marketplace_item"]["capability"] == "adapter"
    assert installed["status"]["enabled"] is False
    assert (plugin_root / "acme.adapter.crm" / "README.md").exists()


# --- HTTP / sandboxed loader (Forge-style) --------------------------------


def _http_manifest() -> KnowledgePluginManifest:
    return KnowledgePluginManifest(
        plugin_id="remote.summarizer",
        name="Remote Summarizer",
        version="1.0.0",
        capability="llm_tool",
        runtime="http",
        entrypoint="https://tools.example.com/run",
    )


def test_select_loader_picks_http():
    assert isinstance(select_loader(_http_manifest()), HttpToolLoader)


def test_http_tool_runs_with_stubbed_network(monkeypatch):
    tool = HttpToolLoader().load(_http_manifest())
    assert isinstance(tool, HttpTool) and tool.name == "remote.summarizer"

    captured = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"result": "remote summary"}).encode()

    def _fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["body"] = request.data
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    out = tool.run({"text": "hello"})
    assert out == "remote summary"
    assert captured["url"] == "https://tools.example.com/run"
    assert b"hello" in captured["body"]


def test_http_runtime_failure_surfaces_as_plugin_error(monkeypatch):
    tool = HttpToolLoader().load(_http_manifest())

    def _boom(request, timeout=0):
        raise TimeoutError("down")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    with pytest.raises(PluginLoadError):
        tool.run({"text": "x"})


def test_host_loads_http_manifest_as_tool(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "remote"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "id": "remote.tool",
                "name": "Remote Tool",
                "version": "1.0.0",
                "capability": "llm_tool",
                "runtime": "http",
                "entrypoint": "https://tools.example.com/run",
                "enabled_by_default": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("ARCHUB_PLUGIN_DIRS", str(tmp_path / "plugins"))
    get_archub_cms_service.cache_clear()
    get_archub_cms_service()

    host = PluginHost(settings=ArcHubSettings.from_env()).load()
    report = host.report()
    assert "remote.tool" in {p["plugin_id"] for p in report["loaded"]}
    assert "remote.tool" in report["llm_tools"]  # HttpTool classified as an LLM tool


# --- endpoints ------------------------------------------------------------


def test_management_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        catalog = client.get("/api/platform/plugins/manage").json()
        assert catalog["total"] >= 8

        off = client.post("/api/platform/plugins/example.backlinks/disable", json={"actor": "a"})
        assert off.status_code == 200 and off.json()["loaded"] is False

        on = client.post("/api/platform/plugins/example.backlinks/enable", json={"actor": "a"})
        assert on.json()["loaded"] is True

        cfg = client.post(
            "/api/platform/plugins/example.backlinks/settings",
            json={"settings": {"k": "v"}, "actor": "a"},
        )
        assert cfg.json()["settings"] == {"k": "v"}

        assert client.post("/api/platform/plugins/nope/enable", json={}).status_code == 404


def test_module_distribution_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app

    plugin_root = tmp_path / "installed"
    archive = _module_zip(tmp_path, module_id="acme.module.rest", capability="rest_api")
    marketplace = tmp_path / "marketplace"
    marketplace.mkdir()
    (marketplace / "marketplace.json").write_text(
        json.dumps(
            {
                "modules": [
                    {
                        "id": "acme.module.rest",
                        "name": "REST Module",
                        "version": "1.0.0",
                        "capability": "rest_api",
                        "package": str(archive),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    monkeypatch.setenv("ARCHUB_PLUGIN_DIRS", str(plugin_root))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True, settings=ArcHubSettings.from_env())

    with TestClient(create_archub_app()) as client:
        market = client.get("/api/platform/modules/marketplace", params={"repository": marketplace})
        assert market.status_code == 200 and market.json()["total"] == 1

        installed = client.post(
            "/api/platform/modules/install/file",
            json={"path": str(archive), "enable": True},
        )
        assert installed.status_code == 200
        assert installed.json()["status"]["capability"] == "rest_api"

        managed = client.get("/api/platform/modules/manage").json()
        assert "acme.module.rest" in {item["plugin_id"] for item in managed["items"]}
