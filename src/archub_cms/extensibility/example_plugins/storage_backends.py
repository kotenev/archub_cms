"""Example plugin: pluggable storage backends (Wiki.js-style StorageExt).

Registers an in-memory storage backend (``memory``) implementing the
:class:`StorageExt` port (``read``/``write`` blobs by key). A filesystem backend
is included to show the same port supports multiple backends — git/db/s3 adapters
would implement the identical contract.

Only the in-memory backend is registered by default (no disk side effects); the
filesystem backend is registered when ``base_dir`` is set in plugin settings.
"""

from __future__ import annotations

__all__ = ["FilesystemStorage", "MemoryStorage", "StorageBackendsPlugin"]

from pathlib import Path

from archub_cms.extensibility.extension_points import PluginContext


class MemoryStorage:
    name = "memory"

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def write(self, key: str, data: bytes) -> None:
        self._blobs[key] = bytes(data)

    def read(self, key: str) -> bytes:
        if key not in self._blobs:
            raise KeyError(key)
        return self._blobs[key]

    def exists(self, key: str) -> bool:
        return key in self._blobs

    def keys(self) -> list[str]:
        return sorted(self._blobs)


class FilesystemStorage:
    name = "filesystem"

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)

    def _path(self, key: str) -> Path:
        # Contain keys under base_dir; reject traversal.
        safe = Path(key.strip("/"))
        if ".." in safe.parts:
            raise ValueError(f"invalid storage key: {key!r}")
        return self._base / safe

    def write(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(data))

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class StorageBackendsPlugin:
    def setup(self, context: PluginContext) -> None:
        context.register(MemoryStorage())
        base_dir = context.settings.get("base_dir")
        if base_dir:
            context.register(FilesystemStorage(base_dir))
