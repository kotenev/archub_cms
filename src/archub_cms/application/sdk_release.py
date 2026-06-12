"""ArcHub Platform SDK release metadata."""

from __future__ import annotations

__all__ = ["sdk_release_manifest"]

from typing import Any


def sdk_release_manifest() -> dict[str, Any]:
    return {
        "name": "ArcHub Platform SDK",
        "version": "1.0.0",
        "status": "beta",
        "package": "archub-platform-sdk",
        "minimum_python": "3.11",
        "languages": ["python"],
        "api_groups": [
            "platform",
            "core_plugins",
            "plugin_management",
            "module_marketplace",
            "delivery",
            "knowledge",
            "runtime",
        ],
        "technology_stack": {
            "platform": "FastAPI, SQLite/PostgreSQL adapters, Rust core plugin workspace",
            "client": "Python 3.11+ stdlib HTTP transport",
            "plugin_model": "Manifest, Python, HTTP/external, Rust core modules",
            "docs": "MkDocs Material",
        },
        "features": [
            "Typed Python client with injectable transport",
            "Plugin manifest builder and validator",
            "Marketplace repository and module installation helpers",
            "Published delivery API helpers",
            "Knowledge search and grounded answer helpers",
            "Core plugin and Rust workspace coverage helpers",
        ],
        "artifacts": [
            "sdk/python",
            "sdk/openapi/archub-platform-sdk.openapi.yaml",
            "docs/sdk/platform-sdk.md",
        ],
    }
