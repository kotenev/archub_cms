"""A small document-store port shared by the catalog, SLA and CMDB registries.

The ITSM plugin's reference-data aggregates (services, SLA definitions,
configuration items, relationships, persisted workflow schemes) are simple keyed
JSON documents. Rather than hand-write a bespoke table per aggregate, each one is
stored in a :class:`DocumentRepository` *collection* — a namespaced key/value space
backed by the platform's audited SQLite/PostgreSQL store (see
``infrastructure.plugins.itsm_document_repository``). :class:`InMemoryDocumentRepository`
is the dependency-free variant used by unit tests and as a sandbox fallback.
"""

from __future__ import annotations

__all__ = ["DocumentRepository", "InMemoryDocumentRepository", "new_id"]

import json
import secrets
from typing import Any, Protocol, runtime_checkable


def new_id(prefix: str) -> str:
    """Generate a short, collision-resistant id like ``svc-3f9a2c1b``."""

    return f"{prefix}-{secrets.token_hex(4)}"


@runtime_checkable
class DocumentRepository(Protocol):
    """A namespaced key/value store of JSON documents (one logical collection)."""

    def upsert(self, key: str, payload: dict[str, Any]) -> None:
        """Insert or replace the document stored under ``key``."""

    def get(self, key: str) -> dict[str, Any] | None: ...

    def list_all(self) -> list[dict[str, Any]]: ...

    def delete(self, key: str) -> bool:
        """Remove ``key``; return whether a document existed."""


def _clone(payload: dict[str, Any]) -> dict[str, Any]:
    # Round-trip through JSON so callers cannot mutate stored documents in place
    # (mirrors the isolation a real database connection gives).
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


class InMemoryDocumentRepository:
    """Process-local document collection for tests and no-database scenarios."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] = {}

    def upsert(self, key: str, payload: dict[str, Any]) -> None:
        self._rows[key] = _clone(payload)

    def get(self, key: str) -> dict[str, Any] | None:
        stored = self._rows.get(key)
        return _clone(stored) if stored is not None else None

    def list_all(self) -> list[dict[str, Any]]:
        return [_clone(row) for row in self._rows.values()]

    def delete(self, key: str) -> bool:
        return self._rows.pop(key, None) is not None
