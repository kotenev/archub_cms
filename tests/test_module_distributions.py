"""Tests for local marketplace distribution generation utilities."""

from __future__ import annotations

import hashlib
import json
import zipfile

from archub_cms.application.module_distribution_service import (
    ModuleDistributionBuilder,
    ModuleDistributionInstaller,
    ModuleMarketplaceRepository,
)
from archub_cms.application.plugins import ArcHubPluginRegistry
from archub_cms.domain.plugins import KnowledgePluginManifest
from archub_cms.tools.module_distributions import build_marketplace, main


def _write_plugin(root, *, plugin_id: str = "acme.tool.demo"):
    plugin_dir = root / plugin_id
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "id": plugin_id,
                "name": "Demo Tool",
                "version": "1.2.3",
                "capability": "llm_tool",
                "runtime": "python",
                "entrypoint": "acme.tool:Plugin",
                "enabled_by_default": False,
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "tool.py").write_text("class Plugin: ...\n", encoding="utf-8")
    cache = plugin_dir / "__pycache__"
    cache.mkdir()
    (cache / "tool.pyc").write_bytes(b"ignored")
    return plugin_dir


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_distribution_builder_writes_hierarchical_marketplace(tmp_path):
    plugin_root = tmp_path / "plugins"
    _write_plugin(plugin_root)
    builtin = KnowledgePluginManifest(
        plugin_id="archub.rest.demo",
        name="Demo REST API",
        version="2.0.0",
        capability="rest_api",
        runtime="rust",
        description="Built-in REST surface.",
        provider="archub",
        source="builtin",
        core=True,
        language="rust",
        rust_crate="archub-rest-api",
    )
    registry = ArcHubPluginRegistry(plugin_dirs=(plugin_root,), builtins=(builtin,))

    result = ModuleDistributionBuilder(output_root=tmp_path / "marketplace").build_all(
        registry.manifests()
    )

    assert result["total"] == 2
    index = json.loads((tmp_path / "marketplace" / "marketplace.json").read_text())
    packages = {item["id"]: item for item in index["modules"]}
    plugin_package = packages["acme.tool.demo"]
    builtin_package = packages["archub.rest.demo"]
    assert plugin_package["package"] == (
        "llm_tool/acme.tool.demo/1.2.3/acme.tool.demo-1.2.3.zip"
    )
    assert builtin_package["package"] == (
        "rest_api/archub.rest.demo/2.0.0/archub.rest.demo-2.0.0.zip"
    )

    plugin_archive = tmp_path / "marketplace" / plugin_package["package"]
    builtin_archive = tmp_path / "marketplace" / builtin_package["package"]
    assert plugin_package["sha256"] == _sha256(plugin_archive)
    assert builtin_package["sha256"] == _sha256(builtin_archive)

    with zipfile.ZipFile(plugin_archive) as archive:
        names = set(archive.namelist())
        assert {"plugin.json", "tool.py"} <= names
        assert not any("__pycache__" in name for name in names)
    with zipfile.ZipFile(builtin_archive) as archive:
        payload = json.loads(archive.read("plugin.json"))
        assert payload["id"] == "archub.rest.demo"
        assert "README.md" in archive.namelist()

    catalog = ModuleMarketplaceRepository(tmp_path / "marketplace").catalog()
    assert catalog["total"] == 2
    restored_builtin = next(
        item for item in catalog["items"] if item["plugin_id"] == "archub.rest.demo"
    )
    assert restored_builtin["core"] is True
    assert restored_builtin["language"] == "rust"
    assert restored_builtin["rust_crate"] == "archub-rest-api"

    installed = ModuleDistributionInstaller(install_roots=(tmp_path / "installed",)).install(
        plugin_archive
    )
    assert installed["plugin_id"] == "acme.tool.demo"
    assert (tmp_path / "installed" / "acme.tool.demo" / "tool.py").exists()


def test_build_marketplace_utility_filters_builtins(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugins"
    _write_plugin(plugin_root, plugin_id="acme.filter.demo")
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))

    result = build_marketplace(
        output_root=tmp_path / "marketplace",
        plugin_dirs=(plugin_root,),
        include_builtins=False,
    )

    assert result["total"] == 1
    assert result["modules"][0]["id"] == "acme.filter.demo"


def test_module_distribution_cli_outputs_summary(tmp_path, monkeypatch, capsys):
    plugin_root = tmp_path / "plugins"
    _write_plugin(plugin_root, plugin_id="acme.cli.demo")
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))

    code = main(
        [
            "--output",
            str(tmp_path / "marketplace"),
            "--plugin-dir",
            str(plugin_root),
            "--no-builtins",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "Built 1 module distributions" in captured.out
    assert (tmp_path / "marketplace" / "marketplace.json").exists()
