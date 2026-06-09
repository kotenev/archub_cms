"""Installable platform module distributions and marketplace repositories."""

from __future__ import annotations

__all__ = [
    "ModuleDistributionInstaller",
    "ModuleMarketplaceRepository",
]

import hashlib
import json
import re
import shutil
import tarfile
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from archub_cms.domain.plugins import KnowledgePluginManifest

_MODULE_ID_RE = re.compile(r"[^a-zA-Z0-9_.-]+")
_INDEX_FILES = (
    "marketplace.json",
    "archub-marketplace.json",
    ".archub/marketplace.json",
)


class ModuleDistributionInstaller:
    """Installs plugin/module packages into the configured module directory.

    A package can be a directory, a single manifest file, a zip archive, or a
    tar/tar.gz archive. The package must contain exactly one ArcHub manifest
    (`plugin.json` or `*.archub-plugin.json`).
    """

    def __init__(self, *, install_roots: Iterable[Path | str]) -> None:
        roots = tuple(Path(item) for item in install_roots)
        if not roots:
            raise ValueError("at least one module install root is required")
        self._root = roots[0]

    @property
    def install_root(self) -> Path:
        return self._root

    def install(
        self,
        source: Path | str,
        *,
        replace: bool = False,
        expected_sha256: str = "",
    ) -> dict[str, Any]:
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(str(source_path))
        if expected_sha256 and source_path.is_file():
            self._verify_sha256(source_path, expected_sha256)

        with tempfile.TemporaryDirectory(prefix="archub-module-") as temp_dir:
            package_root = self._prepare_source(source_path, Path(temp_dir))
            manifest_path = self._single_manifest(package_root)
            manifest = KnowledgePluginManifest.from_dict(
                self._read_manifest(manifest_path),
                source=str(manifest_path),
            )
            errors = manifest.validate()
            if errors:
                raise ValueError(f"invalid module manifest: {'; '.join(errors)}")
            installed_path = self._install_tree(
                manifest,
                manifest_path.parent,
                replace=replace,
            )
        return {
            "plugin_id": manifest.plugin_id,
            "module_id": manifest.plugin_id,
            "name": manifest.name,
            "version": manifest.version,
            "capability": manifest.capability,
            "runtime": manifest.runtime,
            "installed_path": str(installed_path),
            "source": str(source_path),
        }

    def _prepare_source(self, source: Path, temp_root: Path) -> Path:
        if source.is_dir():
            return source
        if source.suffix.lower() in {".json"}:
            package_root = temp_root / "manifest"
            package_root.mkdir(parents=True)
            shutil.copy2(source, package_root / "plugin.json")
            return package_root
        if zipfile.is_zipfile(source):
            target = temp_root / "zip"
            target.mkdir()
            self._extract_zip(source, target)
            return target
        if tarfile.is_tarfile(source):
            target = temp_root / "tar"
            target.mkdir()
            self._extract_tar(source, target)
            return target
        raise ValueError(f"unsupported module distribution format: {source}")

    def _install_tree(
        self,
        manifest: KnowledgePluginManifest,
        source_root: Path,
        *,
        replace: bool,
    ) -> Path:
        install_root = self._root.resolve()
        install_root.mkdir(parents=True, exist_ok=True)
        target = (install_root / _safe_name(manifest.plugin_id)).resolve()
        if not _is_relative_to(target, install_root):
            raise ValueError("resolved install path escapes module root")
        if target.exists() and not replace:
            raise FileExistsError(str(target))
        staging = install_root / f".installing-{_safe_name(manifest.plugin_id)}"
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(source_root, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
        return target

    @staticmethod
    def _single_manifest(package_root: Path) -> Path:
        manifests = sorted(
            {
                *package_root.rglob("plugin.json"),
                *package_root.rglob("*.archub-plugin.json"),
            },
            key=lambda item: (len(item.relative_to(package_root).parts), str(item)),
        )
        if not manifests:
            raise ValueError("module distribution does not contain plugin.json")
        if len(manifests) > 1:
            raise ValueError("module distribution contains multiple manifests")
        return manifests[0]

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("module manifest must be a JSON object")
        return payload

    @staticmethod
    def _verify_sha256(path: Path, expected: str) -> None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest.casefold() != expected.strip().casefold():
            raise ValueError("module distribution sha256 mismatch")

    @staticmethod
    def _extract_zip(source: Path, target: Path) -> None:
        target_root = target.resolve()
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                destination = (target_root / info.filename).resolve()
                if not _is_relative_to(destination, target_root):
                    raise ValueError(f"unsafe zip member path: {info.filename}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, destination.open("wb") as dst:
                    shutil.copyfileobj(src, dst)  # type: ignore[arg-type]

    @staticmethod
    def _extract_tar(source: Path, target: Path) -> None:
        target_root = target.resolve()
        with tarfile.open(source) as archive:
            for member in archive.getmembers():
                if member.isdir():
                    continue
                if member.issym() or member.islnk():
                    raise ValueError(f"unsafe tar link member: {member.name}")
                destination = (target_root / member.name).resolve()
                if not _is_relative_to(destination, target_root):
                    raise ValueError(f"unsafe tar member path: {member.name}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                src = archive.extractfile(member)
                if src is None:
                    continue
                with src, destination.open("wb") as dst:
                    shutil.copyfileobj(src, dst)  # type: ignore[arg-type]


class ModuleMarketplaceRepository:
    """Reads a local marketplace repository index.

    The repository is a checked-out directory containing `marketplace.json`.
    Entries can point to a package via `package`, `archive`, `path`, or
    `manifest_path`, relative to the repository root.
    """

    def __init__(self, repository: Path | str) -> None:
        self._root = Path(repository)

    @property
    def root(self) -> Path:
        return self._root

    def catalog(self) -> dict[str, Any]:
        index_path = self._index_path()
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("marketplace index must be a JSON object")
        raw_items = payload.get("modules", payload.get("plugins", ()))
        if not isinstance(raw_items, list):
            raise ValueError("marketplace index must contain modules list")
        items = [self._normalize_item(item) for item in raw_items if isinstance(item, dict)]
        items.sort(key=lambda item: (item["module_id"], item["version"]))
        return {
            "repository": str(self._root),
            "index": str(index_path),
            "items": items,
            "total": len(items),
        }

    def package_for(self, module_id: str, *, version: str = "") -> dict[str, Any]:
        clean_id = module_id.strip()
        clean_version = version.strip()
        matches = [
            item
            for item in self.catalog()["items"]
            if item["module_id"] == clean_id
            and (not clean_version or item["version"] == clean_version)
        ]
        if not matches:
            raise KeyError(f"module not found in marketplace: {module_id}")
        return matches[-1]

    def _index_path(self) -> Path:
        if self._root.is_file():
            return self._root
        for candidate in _INDEX_FILES:
            path = self._root / candidate
            if path.exists():
                return path
        raise FileNotFoundError(f"marketplace index not found under {self._root}")

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        module_id = str(item.get("id") or item.get("plugin_id") or item.get("module_id") or "")
        package = str(
            item.get("package")
            or item.get("archive")
            or item.get("path")
            or item.get("manifest_path")
            or ""
        ).strip()
        return {
            "module_id": module_id.strip(),
            "plugin_id": module_id.strip(),
            "name": str(item.get("name") or module_id).strip(),
            "version": str(item.get("version") or "0.0.0").strip(),
            "capability": str(item.get("capability") or "platform_module").strip(),
            "runtime": str(item.get("runtime") or "manifest").strip(),
            "description": str(item.get("description") or "").strip(),
            "package": package,
            "sha256": str(item.get("sha256") or "").strip(),
            "tags": list(item.get("tags") or ()),
            "source": str((self._root / package).resolve()) if package else "",
        }


def _safe_name(value: str) -> str:
    return _MODULE_ID_RE.sub("-", value.strip()).strip(".-") or "module"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
