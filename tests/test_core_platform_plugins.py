"""Tests for the ArcHub core-plugin and Rust workspace model."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from archub_cms.application.core_plugins import core_plugin_coverage, rust_workspace_inventory
from archub_cms.application.module_distribution_service import ModuleDistributionBuilder
from archub_cms.application.platform import ArcHubPlatform
from archub_cms.application.plugins import ArcHubPluginRegistry
from archub_cms.domain.plugins import KnowledgePluginManifest
from archub_cms.extensibility.host import PluginHost
from archub_cms.services.cms import get_archub_cms_service
from archub_cms.tools.core_plugins import main as core_plugins_main


def test_manifest_accepts_rust_core_plugin_metadata():
    manifest = KnowledgePluginManifest(
        plugin_id="archub.test.core",
        name="Test Core",
        version="1.0.0",
        capability="platform_module",
        runtime="rust",
        core=True,
        language="rust",
        rust_crate="archub-core",
        provides=("test",),
    )

    assert manifest.valid
    payload = manifest.as_dict()
    assert payload["core"] is True
    assert payload["runtime"] == "rust"
    assert payload["rust_crate"] == "archub-core"


def test_builtin_registry_exposes_cms_as_rust_core_plugin():
    registry = ArcHubPluginRegistry(plugin_dirs=())
    manifests = {manifest.plugin_id: manifest for manifest in registry.manifests()}

    cms = manifests["archub.cms.core"]
    assert cms.core
    assert cms.runtime == "rust"
    assert cms.capability == "cms"
    assert cms.rust_crate == "archub-cms-core"
    assert "content" in cms.provides


def test_platform_capabilities_report_core_plugins(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    platform = ArcHubPlatform(cms=cms, plugin_host=PluginHost().load())

    caps = platform.capabilities()

    assert caps["product"] == "ArcHub platform"
    assert caps["core_plugins"]["total"] >= 24
    assert caps["core_plugins"]["rust_total"] == caps["core_plugins"]["total"]
    assert caps["core_plugins"]["cms"]["plugin_id"] == "archub.cms.core"
    assert caps["core_plugins"]["cms"]["rust_crate"] == "archub-cms-core"
    assert caps["core_plugins"]["rust_workspace"]["missing_total"] == 0
    assert caps["core_plugins"]["rust_workspace"]["coverage_percent"] == 100.0
    assert caps["core_plugins"]["rust_workspace"]["undeclared_total"] == 0
    assert caps["core_plugins"]["rust_workspace"]["contract_percent"] == 100.0


def test_marketplace_builder_packages_cms_core_plugin(tmp_path):
    registry = ArcHubPluginRegistry(plugin_dirs=())

    result = ModuleDistributionBuilder(output_root=tmp_path / "marketplace").build_all(
        registry.manifests()
    )

    packages = {item["id"]: item for item in result["modules"]}
    cms = packages["archub.cms.core"]
    assert cms["core"] is True
    assert cms["language"] == "rust"
    assert cms["rust_crate"] == "archub-cms-core"
    assert cms["package"] == "cms/archub.cms.core/1.0.0/archub.cms.core-1.0.0.zip"
    with zipfile.ZipFile(tmp_path / "marketplace" / cms["package"]) as archive:
        payload = json.loads(archive.read("plugin.json"))
        assert payload["id"] == "archub.cms.core"
        assert payload["core"] is True
        assert payload["runtime"] == "rust"


def test_rust_workspace_scaffolds_core_crates():
    root = Path(__file__).resolve().parents[1]
    for crate in (
        "rust/archub-core/Cargo.toml",
        "rust/archub-cms-core/Cargo.toml",
        "rust/archub-adapters/Cargo.toml",
        "rust/archub-rest-api/Cargo.toml",
        "rust/archub-search-core/Cargo.toml",
        "rust/archub-llm-core/Cargo.toml",
        "rust/archub-workflow-core/Cargo.toml",
        "rust/archub-governance-core/Cargo.toml",
        "rust/archub-automation-core/Cargo.toml",
        "rust/archub-knowledge-core/Cargo.toml",
        "rust/archub-media-core/Cargo.toml",
        "rust/archub-collaboration-core/Cargo.toml",
    ):
        assert (root / crate).exists()


def test_rust_workspace_inventory_covers_builtin_core_plugins():
    registry = ArcHubPluginRegistry(plugin_dirs=())

    inventory = rust_workspace_inventory()
    coverage = core_plugin_coverage(registry.manifests())

    assert inventory["exists"] is True
    assert inventory["members_total"] >= 12
    assert "archub-cms-core" in inventory["crate_names"]
    assert "archub-governance-core" in inventory["crate_names"]
    assert coverage["missing_total"] == 0
    assert coverage["undeclared_total"] == 0
    assert coverage["covered_total"] == coverage["core_plugin_total"]
    assert coverage["declared_total"] == coverage["core_plugin_total"]
    by_crate = {item["rust_crate"]: item for item in coverage["by_crate"]}
    assert "archub.cms.core" in by_crate["archub-cms-core"]["plugins"]
    assert "archub.workflow.publish" in by_crate["archub-workflow-core"]["plugins"]


def test_core_plugin_endpoints_expose_workspace_coverage(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        core_plugins = client.get("/api/platform/core-plugins")
        workspace = client.get("/api/platform/core-plugins/rust-workspace")

    assert core_plugins.status_code == 200
    assert workspace.status_code == 200
    payload = core_plugins.json()
    assert payload["total"] >= 24
    assert payload["rust_workspace"]["missing_total"] == 0
    workspace_payload = workspace.json()
    assert workspace_payload["covered_total"] == workspace_payload["core_plugin_total"]
    assert workspace_payload["declared_total"] == workspace_payload["core_plugin_total"]


def test_core_plugin_cli_reports_contract_coverage(capsys):
    code = core_plugins_main(["--fail-on-missing"])

    captured = capsys.readouterr()
    assert code == 0
    assert "Core plugins:" in captured.out
    assert "Rust-declared" in captured.out
