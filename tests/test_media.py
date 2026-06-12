"""Tests for the media context + pluggable storage (Phase 9)."""

from __future__ import annotations

import pytest

from archub_cms.application.media_service import (
    MediaCommandService,
    StorageService,
    get_archub_media_query_service,
)
from archub_cms.domain.media.asset import MediaAsset
from archub_cms.extensibility.example_plugins.storage_backends import (
    FilesystemStorage,
    MemoryStorage,
)
from archub_cms.extensibility.host import PluginHost
from archub_cms.kernel.events import get_event_bus
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture(autouse=True)
def _clean_bus():
    get_event_bus().clear()
    yield
    get_event_bus().clear()


@pytest.fixture
def cms(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    return get_archub_cms_service()


# --- domain ---------------------------------------------------------------


def test_media_asset_kind_and_validation():
    img = MediaAsset(asset_id="", filename="logo.png", content_type="image/png")
    assert img.kind == "image"
    assert img.is_allowed(["image/png"]) and not img.is_allowed(["image/jpeg"])
    assert (
        MediaAsset(asset_id="", filename="a.pdf", content_type="application/pdf").kind == "document"
    )

    errors = MediaAsset(asset_id="", filename="", content_type="").validate()
    assert any("filename" in e for e in errors) and any("content_type" in e for e in errors)
    disallowed = MediaAsset(asset_id="", filename="x.exe", content_type="application/x-msdownload")
    assert disallowed.validate(allowed_content_types=["image/png"])


# --- command + query ------------------------------------------------------


def test_register_emits_event_and_lists(cms):
    fired: list[str] = []
    get_event_bus().subscribe("media.asset.registered", lambda e: fired.append(e.aggregate_id))
    cmd = MediaCommandService(cms=cms)
    asset = cmd.register(
        filename="logo.png", content_type="image/png", folder="brand", created_by="u"
    )
    assert asset.asset_id and fired == [asset.asset_id]

    q = get_archub_media_query_service(cms=cms)
    assert q.assets()["total"] == 1
    assert q.assets(folder="brand")["total"] == 1
    assert q.folders()["folders"] == ["brand"]


def test_register_rejects_disallowed_content_type(cms):
    cmd = MediaCommandService(cms=cms)
    with pytest.raises(ValueError):
        cmd.register(filename="x.exe", content_type="application/x-msdownload", created_by="u")


# --- storage backends -----------------------------------------------------


def test_memory_storage_backend():
    store = MemoryStorage()
    store.write("a/b.txt", b"hello")
    assert store.read("a/b.txt") == b"hello"
    assert store.exists("a/b.txt") and store.keys() == ["a/b.txt"]
    with pytest.raises(KeyError):
        store.read("missing")


def test_filesystem_storage_backend(tmp_path):
    store = FilesystemStorage(tmp_path / "blobs")
    store.write("docs/readme.md", b"# Hi")
    assert store.read("docs/readme.md") == b"# Hi"
    assert store.exists("docs/readme.md")
    with pytest.raises(ValueError):
        store.write("../escape.txt", b"nope")


def test_storage_service_over_host(cms):
    host = PluginHost().load()
    assert "example.storage_backends" in {p["plugin_id"] for p in host.report()["loaded"]}
    svc = StorageService(plugin_host=host)
    assert "memory" in svc.backends()
    assert svc.put("memory", "k", b"v")["bytes"] == 1
    assert svc.get("memory", "k") == b"v"
    with pytest.raises(KeyError):
        svc.get("does-not-exist", "k")


# --- endpoints ------------------------------------------------------------


def test_media_and_storage_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        reg = client.post(
            "/api/platform/media/register",
            json={"filename": "a.png", "content_type": "image/png", "created_by": "u"},
        )
        assert reg.status_code == 200 and reg.json()["kind"] == "image"

        bad = client.post(
            "/api/platform/media/register",
            json={
                "filename": "a.exe",
                "content_type": "application/x-msdownload",
                "created_by": "u",
            },
        )
        assert bad.status_code == 422

        assert client.get("/api/platform/media").json()["total"] >= 1

        backends = client.get("/api/platform/storage").json()
        assert "memory" in backends["backends"]

        put = client.post(
            "/api/platform/storage/memory/put", json={"key": "f.txt", "content": "data"}
        )
        assert put.status_code == 200
        got = client.get("/api/platform/storage/memory/get", params={"key": "f.txt"})
        assert got.json()["content"] == "data"

        assert (
            client.post(
                "/api/platform/storage/nope/put", json={"key": "k", "content": "x"}
            ).status_code
            == 404
        )
