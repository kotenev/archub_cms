"""Tests for the localization / i18n bounded context (Phase 14)."""

from __future__ import annotations

import pytest

from archub_cms.application.localization_service import (
    LocalizationCommandService,
    get_archub_localization_query_service,
)
from archub_cms.domain.content.value_objects import Culture
from archub_cms.domain.localization.dictionary import DictionaryEntry
from archub_cms.domain.localization.variant import LocalizedVariant
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def node(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    created = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="Doc",
        slug="doc",
        payload={"title": "Doc EN"},
        created_by="t",
    )
    return cms, created.node_id


# --- domain ---------------------------------------------------------------


def test_dictionary_entry_locale_fallback():
    entry = DictionaryEntry(
        key="Welcome",
        group="site",
        values={"en": "Welcome", "fr-FR": "Bienvenue", "default": "Hello"},
    )
    assert entry.resolve("fr-FR") == "Bienvenue"
    assert entry.resolve("en-US") == "Welcome"  # language fallback
    assert entry.resolve("de") == "Hello"  # default fallback
    assert entry.resolve("FR-fr") == "Bienvenue"  # case-insensitive
    assert DictionaryEntry(key="x", values={}).resolve("en", default="fb") == "fb"
    assert entry.locales == ("default", "en", "fr-FR")


def test_localized_variant_model():
    v = LocalizedVariant(
        node_id="n",
        culture=Culture("fr-FR"),
        status="published",
        published={"title": "Bonjour"},
    )
    assert v.is_published and v.title() == "Bonjour"
    assert v.as_dict()["culture"] == "fr-FR"


# --- command + query services ---------------------------------------------


def test_variant_lifecycle_and_events(node):
    cms, node_id = node
    fired: list[str] = []
    get_event_bus().subscribe(
        "localization.variant.upserted", lambda e: fired.append("upserted:" + e.metadata["culture"])
    )
    get_event_bus().subscribe("localization.variant.published", lambda e: fired.append("published"))

    cmd = LocalizationCommandService(cms=cms)
    cmd.upsert_variant(node_id, culture="fr-FR", payload={"title": "Doc FR"}, actor="ed")
    cmd.publish_variant(node_id, culture="fr-FR", actor="ed")

    q = get_archub_localization_query_service(cms=cms)
    variants = q.variants(node_id)
    assert variants["total"] == 1
    cultures = q.cultures(node_id)
    assert cultures["cultures"] and cultures["published_cultures"]
    assert any("upserted" in f for f in fired) and "published" in fired


def test_invalid_culture_rejected(node):
    cms, node_id = node
    cmd = LocalizationCommandService(cms=cms)
    with pytest.raises(ValueError):
        cmd.upsert_variant(node_id, culture="not-a-locale", payload={}, actor="e")


def test_dictionary_upsert_and_translate(node):
    cms, _node_id = node
    fired: list[str] = []
    get_event_bus().subscribe(
        "localization.dictionary.upserted", lambda e: fired.append(e.aggregate_id)
    )
    cmd = LocalizationCommandService(cms=cms)
    cmd.upsert_dictionary(
        key="Welcome",
        group="site",
        values={"en": "Welcome", "fr-FR": "Bienvenue", "default": "Hi"},
        actor="ed",
    )
    assert fired == ["Welcome"]

    q = get_archub_localization_query_service(cms=cms)
    assert q.translate("Welcome", culture="fr-FR", group="site")["value"] == "Bienvenue"
    assert q.translate("Welcome", culture="es", group="site")["value"] == "Hi"  # default
    missing = q.translate("Missing", culture="en", default="fb")
    assert missing["found"] is False and missing["value"] == "fb"


def test_dictionary_upsert_validation(node):
    cms, _ = node
    cmd = LocalizationCommandService(cms=cms)
    with pytest.raises(ValueError):
        cmd.upsert_dictionary(key="", group="g", values={"en": "x"}, actor="a")
    with pytest.raises(ValueError):
        cmd.upsert_dictionary(key="K", group="g", values={}, actor="a")


# --- endpoints ------------------------------------------------------------


def test_localization_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    created = cms.create_node(
        parent_id="root",
        content_type_alias="page",
        name="P",
        slug="p",
        payload={"title": "P EN"},
        created_by="t",
    )
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        upserted = client.post(
            f"/api/platform/localization/{created.node_id}/variants",
            json={"culture": "fr-FR", "payload": {"title": "P FR"}, "actor": "ed"},
        )
        assert upserted.status_code == 200

        published = client.post(
            f"/api/platform/localization/{created.node_id}/variants/fr-FR/publish",
            json={"actor": "ed"},
        )
        assert published.status_code == 200

        variants = client.get(f"/api/platform/localization/{created.node_id}/variants")
        assert variants.json()["total"] == 1

        client.post(
            "/api/platform/localization/dictionary",
            json={"key": "Hi", "group": "ui", "values": {"en": "Hi", "fr": "Salut"}, "actor": "ed"},
        )
        translated = client.get(
            "/api/platform/localization/translate",
            params={"key": "Hi", "culture": "fr", "group": "ui"},
        )
        assert translated.json()["value"] == "Salut"

        bad = client.post(
            f"/api/platform/localization/{created.node_id}/variants",
            json={"culture": "bogus", "payload": {}, "actor": "e"},
        )
        assert bad.status_code == 422
