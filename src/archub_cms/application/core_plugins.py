"""Core plugin workspace inventory and migration coverage helpers."""

from __future__ import annotations

__all__ = [
    "core_plugin_coverage",
    "rust_crate_path",
    "rust_workspace_inventory",
]

import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

from archub_cms.domain.plugins import KnowledgePluginManifest


def rust_workspace_inventory(root: Path | str | None = None) -> dict[str, Any]:
    """Return a read model of the local Rust workspace.

    The Python app is still the compatibility shell, so this function is the
    bridge that lets APIs verify whether a Rust core-plugin manifest points to
    an actual workspace crate.
    """

    workspace_root = _workspace_root(Path(root) if root is not None else None)
    cargo_toml = workspace_root / "Cargo.toml"
    if not cargo_toml.exists():
        return {
            "root": str(workspace_root),
            "manifest": str(cargo_toml),
            "exists": False,
            "members_total": 0,
            "crate_names": [],
            "crates": [],
            "missing_members": [],
        }

    payload = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
    members = tuple(str(item) for item in payload.get("workspace", {}).get("members", ()))
    crates: list[dict[str, Any]] = []
    missing_members: list[str] = []
    for member in members:
        manifest = workspace_root / member / "Cargo.toml"
        if not manifest.exists():
            missing_members.append(member)
            crates.append(
                {
                    "name": "",
                    "path": member,
                    "manifest": str(manifest),
                    "crate_root": str(manifest.parent),
                    "exists": False,
                }
            )
            continue
        crate_payload = tomllib.loads(manifest.read_text(encoding="utf-8"))
        name = str(crate_payload.get("package", {}).get("name") or "").strip()
        crates.append(
            {
                "name": name,
                "path": member,
                "manifest": str(manifest),
                "crate_root": str(manifest.parent),
                "exists": True,
            }
        )

    crate_names = sorted(item["name"] for item in crates if item.get("name"))
    return {
        "root": str(workspace_root),
        "manifest": str(cargo_toml),
        "exists": True,
        "members_total": len(members),
        "crate_names": crate_names,
        "crates": crates,
        "missing_members": missing_members,
    }


def rust_crate_path(crate_name: str, root: Path | str | None = None) -> Path | None:
    """Resolve a workspace crate name to its local source directory."""

    clean = crate_name.strip()
    if not clean:
        return None
    for item in rust_workspace_inventory(root)["crates"]:
        if item.get("name") == clean and item.get("exists"):
            return Path(str(item["crate_root"]))
    return None


def core_plugin_coverage(
    manifests: tuple[KnowledgePluginManifest, ...] | list[KnowledgePluginManifest],
    *,
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Compare Rust core plugin manifests with the local Rust workspace."""

    inventory = rust_workspace_inventory(root)
    crate_names = set(inventory["crate_names"])
    rust_core = [
        manifest
        for manifest in manifests
        if manifest.core and manifest.runtime == "rust" and manifest.rust_crate
    ]
    by_crate: dict[str, list[str]] = defaultdict(list)
    missing: list[dict[str, str]] = []
    undeclared: list[dict[str, str]] = []
    for manifest in rust_core:
        by_crate[manifest.rust_crate].append(manifest.plugin_id)
        crate_root = rust_crate_path(manifest.rust_crate, root)
        if manifest.rust_crate not in crate_names or crate_root is None:
            missing.append({"plugin_id": manifest.plugin_id, "rust_crate": manifest.rust_crate})
        elif not _crate_declares_plugin(crate_root, manifest.plugin_id):
            undeclared.append({"plugin_id": manifest.plugin_id, "rust_crate": manifest.rust_crate})

    covered_total = len(rust_core) - len(missing)
    coverage_percent = round((covered_total / len(rust_core)) * 100, 2) if rust_core else 100.0
    declared_total = covered_total - len(undeclared)
    contract_percent = round((declared_total / len(rust_core)) * 100, 2) if rust_core else 100.0
    return {
        "workspace": inventory,
        "core_plugin_total": len(rust_core),
        "covered_total": covered_total,
        "missing_total": len(missing),
        "coverage_percent": coverage_percent,
        "missing": missing,
        "declared_total": declared_total,
        "undeclared_total": len(undeclared),
        "contract_percent": contract_percent,
        "undeclared": undeclared,
        "by_crate": [
            {"rust_crate": crate, "total": len(plugin_ids), "plugins": sorted(plugin_ids)}
            for crate, plugin_ids in sorted(by_crate.items())
        ],
    }


def _workspace_root(root: Path | None = None) -> Path:
    if root is not None:
        return root.resolve()
    current = Path(__file__).resolve()
    for candidate in (current.parent, *current.parents):
        if (candidate / "Cargo.toml").exists():
            return candidate
    return Path.cwd().resolve()


def _crate_declares_plugin(crate_root: Path, plugin_id: str) -> bool:
    src_root = crate_root / "src"
    if not src_root.exists():
        return False
    for path in src_root.rglob("*.rs"):
        try:
            if plugin_id in path.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False
