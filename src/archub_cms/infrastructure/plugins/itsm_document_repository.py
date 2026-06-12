"""Platform-owned document repositories for ITSM reference data.

The catalog, SLA and CMDB registries store keyed JSON documents in a single
``itsm_document`` table partitioned by a ``collection`` name, behind the audited
platform SQLite/PostgreSQL stores. Each repository instance is bound to one
collection and satisfies the plugin's
:class:`~archub_cms.extensibility.example_plugins.itsm.documents.DocumentRepository`
port.
"""

from __future__ import annotations

__all__ = ["PostgresDocumentRepository", "SqliteDocumentRepository"]

import json
from typing import Any

from archub_cms.extensibility.example_plugins.itsm.documents import DocumentRepository
from archub_cms.extensibility.platform_adapter import PostgresPluginStore, SQLitePluginStore

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS itsm_document (
    collection TEXT NOT NULL,
    doc_key TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (collection, doc_key)
)
"""

_CREATE_TABLE_PG = """
CREATE TABLE IF NOT EXISTS itsm_document (
    collection TEXT NOT NULL,
    doc_key TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    PRIMARY KEY (collection, doc_key)
)
"""


def _loads(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _timestamps(payload: dict[str, Any]) -> tuple[float, float]:
    created = float(payload.get("created_at") or 0.0)
    updated = float(payload.get("updated_at") or created)
    return created, updated


class SqliteDocumentRepository(DocumentRepository):
    """A single ``itsm_document`` collection through an audited SQLite store."""

    def __init__(self, store: SQLitePluginStore, collection: str) -> None:
        self._store = store
        self._collection = collection
        with self._store.transaction(
            action="itsm.document.schema.ensure", target=collection
        ) as conn:
            conn.execute(_CREATE_TABLE)

    def upsert(self, key: str, payload: dict[str, Any]) -> None:
        created, updated = _timestamps(payload)
        row = {
            "collection": self._collection,
            "doc_key": key,
            "payload_json": json.dumps(payload, ensure_ascii=False, default=str),
            "created_at": created,
            "updated_at": updated,
        }
        with self._store.transaction(
            action=f"itsm.document.{self._collection}.upsert", target=key
        ) as conn:
            conn.execute(
                """
                INSERT INTO itsm_document (
                    collection, doc_key, payload_json, created_at, updated_at
                ) VALUES (:collection, :doc_key, :payload_json, :created_at, :updated_at)
                ON CONFLICT(collection, doc_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                row,
            )

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._store.read(
            action=f"itsm.document.{self._collection}.get",
            target=key,
            callback=lambda conn: conn.execute(
                "SELECT payload_json FROM itsm_document WHERE collection = ? AND doc_key = ?",
                (self._collection, key),
            ).fetchone(),
        )
        return _loads(row["payload_json"]) if row is not None else None

    def list_all(self) -> list[dict[str, Any]]:
        rows = self._store.read(
            action=f"itsm.document.{self._collection}.list",
            callback=lambda conn: conn.execute(
                "SELECT payload_json FROM itsm_document WHERE collection = ? "
                "ORDER BY created_at, doc_key",
                (self._collection,),
            ).fetchall(),
        )
        return [_loads(row["payload_json"]) for row in rows]

    def delete(self, key: str) -> bool:
        with self._store.transaction(
            action=f"itsm.document.{self._collection}.delete", target=key
        ) as conn:
            cursor = conn.execute(
                "DELETE FROM itsm_document WHERE collection = ? AND doc_key = ?",
                (self._collection, key),
            )
            return cursor.rowcount > 0


class PostgresDocumentRepository(DocumentRepository):
    """A single ``itsm_document`` collection through an audited PostgreSQL store."""

    def __init__(self, store: PostgresPluginStore, collection: str) -> None:
        self._store = store
        self._collection = collection
        with self._store.transaction(
            action="itsm.document.schema.ensure", target=collection
        ) as conn:
            conn.execute(_CREATE_TABLE_PG)

    def upsert(self, key: str, payload: dict[str, Any]) -> None:
        created, updated = _timestamps(payload)
        row = {
            "collection": self._collection,
            "doc_key": key,
            "payload_json": json.dumps(payload, ensure_ascii=False, default=str),
            "created_at": created,
            "updated_at": updated,
        }
        with self._store.transaction(
            action=f"itsm.document.{self._collection}.upsert", target=key
        ) as conn:
            conn.execute(
                """
                INSERT INTO itsm_document (
                    collection, doc_key, payload_json, created_at, updated_at
                ) VALUES (
                    %(collection)s, %(doc_key)s, %(payload_json)s, %(created_at)s, %(updated_at)s
                )
                ON CONFLICT (collection, doc_key) DO UPDATE SET
                    payload_json = EXCLUDED.payload_json,
                    updated_at = EXCLUDED.updated_at
                """,
                row,
            )

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._store.read(
            action=f"itsm.document.{self._collection}.get",
            target=key,
            callback=lambda conn: conn.execute(
                "SELECT payload_json FROM itsm_document WHERE collection = %s AND doc_key = %s",
                (self._collection, key),
            ).fetchone(),
        )
        return _loads(row["payload_json"]) if row is not None else None

    def list_all(self) -> list[dict[str, Any]]:
        rows = self._store.read(
            action=f"itsm.document.{self._collection}.list",
            callback=lambda conn: conn.execute(
                "SELECT payload_json FROM itsm_document WHERE collection = %s "
                "ORDER BY created_at, doc_key",
                (self._collection,),
            ).fetchall(),
        )
        return [_loads(row["payload_json"]) for row in rows]

    def delete(self, key: str) -> bool:
        with self._store.transaction(
            action=f"itsm.document.{self._collection}.delete", target=key
        ) as conn:
            cursor = conn.execute(
                "DELETE FROM itsm_document WHERE collection = %s AND doc_key = %s",
                (self._collection, key),
            )
            return cursor.rowcount > 0
