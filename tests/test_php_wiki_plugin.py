"""Tests for the ArcHub.ru PHP wiki demonstration plugin."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from archub_cms.application.module_distribution_service import ModuleDistributionBuilder
from archub_cms.domain.plugins import KnowledgePluginManifest


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[1] / "plugins" / "archub_ru_wiki_php"


def test_php_wiki_plugin_manifest_is_valid_external_knowledge_module():
    root = _plugin_root()
    payload = json.loads((root / "plugin.json").read_text(encoding="utf-8"))

    manifest = KnowledgePluginManifest.from_dict(payload, source=str(root / "plugin.json"))

    assert manifest.valid
    assert manifest.plugin_id == "archub.ru.wiki.php"
    assert manifest.capability == "knowledge"
    assert manifest.runtime == "external"
    assert manifest.language == "php"
    assert manifest.enabled_by_default is False
    assert "wiki.drawio" in manifest.provides


def test_php_wiki_plugin_uses_php_84_and_symfony_8_contract():
    composer = json.loads((_plugin_root() / "composer.json").read_text(encoding="utf-8"))

    assert composer["require"]["php"] == ">=8.4"
    assert composer["require"]["symfony/framework-bundle"] == "^8.0"
    assert composer["autoload"]["psr-4"]["ArcHub\\WikiPlugin\\"] == "src/"
    assert "serve" in composer["scripts"]


def test_php_wiki_plugin_distribution_contains_app_and_drawio_assets(tmp_path):
    root = _plugin_root()
    payload = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    manifest = KnowledgePluginManifest.from_dict(payload, source=str(root / "plugin.json"))

    result = ModuleDistributionBuilder(output_root=tmp_path / "marketplace").build_all((manifest,))

    item = result["modules"][0]
    assert item["id"] == "archub.ru.wiki.php"
    assert item["language"] == "php"
    assert item["package"] == "knowledge/archub.ru.wiki.php/1.0.0/archub.ru.wiki.php-1.0.0.zip"

    with zipfile.ZipFile(tmp_path / "marketplace" / item["package"]) as archive:
        names = set(archive.namelist())
        assert "plugin.json" in names
        assert "composer.json" in names
        assert "public/index.php" in names
        assert "public/assets/wiki.js" in names
        assert "src/ArcHubWikiApplication.php" in names
        assert "src/Renderer/WikiRenderer.php" in names
        assert "openapi.yaml" in names
        assert not any(name.startswith("vendor/") for name in names)
