"""Installable platform module distributions and marketplace repositories."""

from __future__ import annotations

__all__ = [
    "ModuleDistributionBuilder",
    "ModuleDistributionInstaller",
    "ModuleMarketplaceRepository",
]

import hashlib
import json
import re
import shutil
import tarfile
import tempfile
import time
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archub_cms.application.core_plugins import rust_crate_path
from archub_cms.domain.plugins import KnowledgePluginManifest

_MODULE_ID_RE = re.compile(r"[^a-zA-Z0-9_.-]+")
_INDEX_FILES = (
    "marketplace.json",
    "archub-marketplace.json",
    ".archub/marketplace.json",
)
_ZIP_DATE_TIME = (2026, 1, 1, 0, 0, 0)
_IGNORED_PACKAGE_NAMES = {".DS_Store"}
_IGNORED_PACKAGE_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}


@dataclass(frozen=True)
class _PackageBuild:
    manifest: KnowledgePluginManifest
    archive_path: Path
    package_path: str
    sha256: str
    source: str


class ModuleDistributionBuilder:
    """Build marketplace-ready archives for platform modules and plugins."""

    def __init__(self, *, output_root: Path | str, replace: bool = True) -> None:
        self._output_root = Path(output_root)
        self._replace = replace

    @property
    def output_root(self) -> Path:
        return self._output_root

    def build_all(self, manifests: Iterable[KnowledgePluginManifest]) -> dict[str, Any]:
        builds: list[_PackageBuild] = []
        for manifest in sorted(manifests, key=lambda item: (item.capability, item.plugin_id)):
            errors = manifest.validate()
            if errors:
                raise ValueError(
                    f"invalid manifest {manifest.plugin_id!r}: {'; '.join(errors)}"
                )
            builds.append(self._build_one(manifest))
        index = {
            "schema_version": "1.0",
            "generated_at": time.time(),
            "modules": [self._marketplace_item(build) for build in builds],
        }
        index_path = self._output_root / "marketplace.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "output_root": str(self._output_root),
            "index": str(index_path),
            "modules": index["modules"],
            "total": len(builds),
        }

    def _build_one(self, manifest: KnowledgePluginManifest) -> _PackageBuild:
        archive_path = self._archive_path(manifest)
        if archive_path.exists() and not self._replace:
            raise FileExistsError(str(archive_path))
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        if archive_path.exists():
            archive_path.unlink()

        source_root = self._source_root(manifest)
        if source_root is None:
            with tempfile.TemporaryDirectory(prefix="archub-module-build-") as temp_dir:
                if _is_builtin_rust_core(manifest):
                    package_root = self._write_rust_core_package(manifest, Path(temp_dir))
                else:
                    package_root = self._write_manifest_only_package(manifest, Path(temp_dir))
                self._write_zip(package_root, archive_path)
        else:
            self._write_zip(source_root, archive_path)
        return _PackageBuild(
            manifest=manifest,
            archive_path=archive_path,
            package_path=archive_path.relative_to(self._output_root).as_posix(),
            sha256=_sha256(archive_path),
            source=manifest.source,
        )

    def _archive_path(self, manifest: KnowledgePluginManifest) -> Path:
        filename = f"{_safe_name(manifest.plugin_id)}-{manifest.version}.zip"
        return (
            self._output_root
            / _safe_name(manifest.capability)
            / _safe_name(manifest.plugin_id)
            / manifest.version
            / filename
        )

    @staticmethod
    def _source_root(manifest: KnowledgePluginManifest) -> Path | None:
        source = Path(manifest.source)
        if manifest.source == "builtin" or not source.exists() or source.is_dir():
            return source if source.is_dir() else None
        return source.parent

    @staticmethod
    def _write_manifest_only_package(
        manifest: KnowledgePluginManifest, temp_root: Path
    ) -> Path:
        package_root = temp_root / _safe_name(manifest.plugin_id)
        package_root.mkdir(parents=True)
        (package_root / "plugin.json").write_text(
            json.dumps(_manifest_payload(manifest), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (package_root / "README.md").write_text(
            f"# {manifest.name}\n\n{manifest.description or 'ArcHub platform module.'}\n",
            encoding="utf-8",
        )
        return package_root

    @staticmethod
    def _write_rust_core_package(
        manifest: KnowledgePluginManifest, temp_root: Path
    ) -> Path:
        crate_root = rust_crate_path(manifest.rust_crate)
        if crate_root is None:
            raise FileNotFoundError(f"rust crate not found: {manifest.rust_crate}")
        package_root = ModuleDistributionBuilder._write_manifest_only_package(manifest, temp_root)
        members = ["rust/archub-core"]
        if manifest.rust_crate != "archub-core":
            members.append(f"rust/{manifest.rust_crate}")
        (package_root / "Cargo.toml").write_text(
            _rust_package_workspace(members),
            encoding="utf-8",
        )
        for member in members:
            source = rust_crate_path(Path(member).name)
            if source is None:
                raise FileNotFoundError(f"rust crate not found: {Path(member).name}")
            target = package_root / member
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                source,
                target,
                ignore=shutil.ignore_patterns("target", ".git", "__pycache__", "*.pyc"),
            )
        return package_root

    @staticmethod
    def _write_zip(source_root: Path, archive_path: Path) -> None:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(source_root.rglob("*")):
                if not path.is_file() or _ignored_package_path(path, source_root):
                    continue
                relative = path.relative_to(source_root).as_posix()
                info = zipfile.ZipInfo(relative, _ZIP_DATE_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())

    @staticmethod
    def _marketplace_item(build: _PackageBuild) -> dict[str, Any]:
        manifest = build.manifest
        return {
            "id": manifest.plugin_id,
            "plugin_id": manifest.plugin_id,
            "module_id": manifest.plugin_id,
            "name": manifest.name,
            "version": manifest.version,
            "capability": manifest.capability,
            "runtime": manifest.runtime,
            "description": manifest.description,
            "provider": manifest.provider,
            "permissions": list(manifest.permissions),
            "tags": list(manifest.tags),
            "core": manifest.core,
            "language": manifest.language,
            "rust_crate": manifest.rust_crate,
            "provides": list(manifest.provides),
            "package": build.package_path,
            "sha256": build.sha256,
            "source": build.source,
        }


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
            "core": manifest.core,
            "language": manifest.language,
            "rust_crate": manifest.rust_crate,
            "provides": list(manifest.provides),
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
            "core": bool(item.get("core", False)),
            "language": str(item.get("language") or "").strip(),
            "rust_crate": str(item.get("rust_crate") or "").strip(),
            "provides": list(item.get("provides") or ()),
            "source": str((self._root / package).resolve()) if package else "",
        }


def _safe_name(value: str) -> str:
    return _MODULE_ID_RE.sub("-", value.strip()).strip(".-") or "module"


def _manifest_payload(manifest: KnowledgePluginManifest) -> dict[str, Any]:
    payload = manifest.as_dict()
    payload["id"] = manifest.plugin_id
    payload.pop("plugin_id", None)
    payload.pop("source", None)
    payload.pop("valid", None)
    payload.pop("errors", None)
    return payload


def _is_builtin_rust_core(manifest: KnowledgePluginManifest) -> bool:
    return manifest.source == "builtin" and manifest.core and manifest.runtime == "rust"


def _rust_package_workspace(members: list[str]) -> str:
    member_lines = "\n".join(f'    "{member}",' for member in sorted(set(members)))
    return (
        "[workspace]\n"
        "members = [\n"
        f"{member_lines}\n"
        ']\n'
        'resolver = "2"\n\n'
        "[workspace.package]\n"
        'version = "0.1.0"\n'
        'edition = "2021"\n'
        'license = "Apache-2.0"\n'
        'authors = ["ArcHub contributors"]\n'
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ignored_package_path(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if path.name in _IGNORED_PACKAGE_NAMES or path.suffix == ".pyc":
        return True
    return any(part in _IGNORED_PACKAGE_PARTS for part in relative.parts)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
