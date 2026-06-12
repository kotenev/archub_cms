"""Static SDK release metadata."""

from __future__ import annotations

SDK_RELEASE = {
    "name": "ArcHub Platform SDK",
    "version": "1.0.0",
    "status": "beta",
    "minimum_python": "3.11",
    "transport": "HTTP JSON over urllib.request",
    "api_groups": [
        "platform",
        "core_plugins",
        "plugin_management",
        "module_marketplace",
        "delivery",
        "knowledge",
        "runtime",
    ],
    "languages": ["python"],
    "package": "archub-platform-sdk",
}
