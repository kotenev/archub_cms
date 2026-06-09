"""Platform-owned persistence and audit surface exposed to plugins.

Plugins should not construct database connections directly. They ask this
adapter for a platform-backed repository/store, and every store operation writes
an immutable plugin audit entry.
"""

from __future__ import annotations

__all__ = [
    "PluginAuditEntry",
    "PluginAuditLog",
    "PluginPlatformAdapter",
    "PostgresPluginStore",
    "SQLitePluginStore",
]

import json
import os
import secrets
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlsplit, urlunsplit

from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.db.schema import apply_extension_migrations
from archub_cms.settings import ArcHubSettings

T = TypeVar("T")

_POSTGRES_ALIASES = {"postgres", "postgresql", "pg"}


@dataclass(frozen=True)
class PluginAuditEntry:
    """A single platform audit record for a plugin lifecycle or persistence action."""

    audit_id: str
    plugin_id: str
    action: str
    target: str = ""
    actor: str = ""
    backend: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "plugin_id": self.plugin_id,
            "action": self.action,
            "target": self.target,
            "actor": self.actor,
            "backend": self.backend,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


class PluginAuditLog:
    """SQLite-backed plugin audit log owned by the platform runtime."""

    def __init__(self, database: Database) -> None:
        self._db = database
        conn = self._db.connect()
        try:
            apply_extension_migrations(conn)
        finally:
            conn.close()

    def record(
        self,
        *,
        plugin_id: str,
        action: str,
        target: str = "",
        actor: str = "",
        backend: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PluginAuditEntry:
        entry = PluginAuditEntry(
            audit_id=secrets.token_urlsafe(12),
            plugin_id=plugin_id,
            action=action,
            target=target,
            actor=actor,
            backend=backend,
            metadata=dict(metadata or {}),
            created_at=time.time(),
        )
        conn = self._db.connect()
        try:
            conn.execute(
                """
                INSERT INTO archub_plugin_audit (
                    audit_id, plugin_id, action, target, actor, backend,
                    metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.audit_id,
                    entry.plugin_id,
                    entry.action,
                    entry.target,
                    entry.actor,
                    entry.backend,
                    _json(dict(entry.metadata)),  # type: ignore[arg-type]
                    entry.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return entry

    def query(
        self,
        *,
        plugin_id: str = "",
        action: str = "",
        limit: int = 50,
    ) -> list[PluginAuditEntry]:
        clauses: list[str] = []
        params: list[Any] = []
        if plugin_id:
            clauses.append("plugin_id = ?")
            params.append(plugin_id)
        if action:
            clauses.append("action = ?")
            params.append(action)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            "SELECT * FROM archub_plugin_audit"
            f"{where} ORDER BY created_at DESC LIMIT ?"
        )
        params.append(limit)
        conn = self._db.connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_entry(row) for row in rows]

    @staticmethod
    def _row_to_entry(row: Any) -> PluginAuditEntry:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except (TypeError, ValueError):
            metadata = {}
        return PluginAuditEntry(
            audit_id=str(row["audit_id"]),
            plugin_id=str(row["plugin_id"]),
            action=str(row["action"]),
            target=str(row["target"] or ""),
            actor=str(row["actor"] or ""),
            backend=str(row["backend"] or ""),
            metadata=metadata if isinstance(metadata, dict) else {},
            created_at=float(row["created_at"] or 0.0),
        )


class SQLitePluginStore:
    """Audited SQLite adapter for platform-owned plugin repositories."""

    backend = "sqlite"

    def __init__(
        self,
        *,
        plugin_id: str,
        database: Database,
        audit_log: PluginAuditLog,
    ) -> None:
        self.plugin_id = plugin_id
        self._db = database
        self._audit = audit_log

    @property
    def database_path(self) -> str:
        return self._db.path

    @contextmanager
    def transaction(
        self,
        *,
        action: str,
        target: str = "",
        actor: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[Any]:
        conn = self._db.connect()
        try:
            yield conn
        except Exception as exc:
            conn.rollback()
            self.audit(
                f"{action}.failed",
                target=target,
                actor=actor,
                metadata=_with_error(metadata, exc),
            )
            raise
        else:
            conn.commit()
            self.audit(action, target=target, actor=actor, metadata=metadata)
        finally:
            conn.close()

    def read(
        self,
        *,
        action: str,
        callback: Callable[[Any], T],
        target: str = "",
        actor: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> T:
        conn = self._db.connect()
        try:
            result = callback(conn)
        except Exception as exc:
            self.audit(
                f"{action}.failed",
                target=target,
                actor=actor,
                metadata=_with_error(metadata, exc),
            )
            raise
        else:
            self.audit(action, target=target, actor=actor, metadata=metadata)
            return result
        finally:
            conn.close()

    def audit(
        self,
        action: str,
        *,
        target: str = "",
        actor: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PluginAuditEntry:
        payload = {"db_path": self._db.path, **dict(metadata or {})}
        return self._audit.record(
            plugin_id=self.plugin_id,
            action=action,
            target=target,
            actor=actor,
            backend=self.backend,
            metadata=payload,
        )


class PostgresPluginStore:
    """Audited PostgreSQL adapter for platform-owned plugin repositories."""

    backend = "postgres"

    def __init__(
        self,
        *,
        plugin_id: str,
        dsn: str,
        audit_log: PluginAuditLog,
    ) -> None:
        self.plugin_id = plugin_id
        self._dsn = dsn
        self._audit = audit_log

    @property
    def dsn(self) -> str:
        return self._dsn

    def connect(self) -> Any:
        try:
            import psycopg  # noinspection PyUnresolvedReferences
            from psycopg.rows import dict_row  # noinspection PyUnresolvedReferences
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "PostgreSQL plugin storage requires the 'psycopg' driver "
                "(install archub-cms[postgres] or `pip install psycopg[binary]`)"
            ) from exc
        return psycopg.connect(self._dsn, row_factory=dict_row)

    @contextmanager
    def transaction(
        self,
        *,
        action: str,
        target: str = "",
        actor: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[Any]:
        conn = self.connect()
        try:
            yield conn
        except Exception as exc:
            conn.rollback()
            self.audit(
                f"{action}.failed",
                target=target,
                actor=actor,
                metadata=_with_error(metadata, exc),
            )
            raise
        else:
            conn.commit()
            self.audit(action, target=target, actor=actor, metadata=metadata)
        finally:
            conn.close()

    def read(
        self,
        *,
        action: str,
        callback: Callable[[Any], T],
        target: str = "",
        actor: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> T:
        conn = self.connect()
        try:
            result = callback(conn)
        except Exception as exc:
            self.audit(
                f"{action}.failed",
                target=target,
                actor=actor,
                metadata=_with_error(metadata, exc),
            )
            raise
        else:
            self.audit(action, target=target, actor=actor, metadata=metadata)
            return result
        finally:
            conn.close()

    def audit(
        self,
        action: str,
        *,
        target: str = "",
        actor: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PluginAuditEntry:
        payload = {"dsn": _redact_dsn(self._dsn), **dict(metadata or {})}
        return self._audit.record(
            plugin_id=self.plugin_id,
            action=action,
            target=target,
            actor=actor,
            backend=self.backend,
            metadata=payload,
        )


class PluginPlatformAdapter:
    """Capability boundary exposed on :class:`PluginContext`."""

    def __init__(
        self,
        *,
        plugin_id: str,
        settings: ArcHubSettings | None = None,
        audit_log: PluginAuditLog | None = None,
    ) -> None:
        self.plugin_id = plugin_id
        self._settings = settings or ArcHubSettings.from_env()
        self._audit = audit_log or PluginAuditLog(Database(self._settings.cms_db_path))

    @property
    def audit_log(self) -> PluginAuditLog:
        return self._audit

    def audit(
        self,
        action: str,
        *,
        target: str = "",
        actor: str = "",
        backend: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PluginAuditEntry:
        return self._audit.record(
            plugin_id=self.plugin_id,
            action=action,
            target=target,
            actor=actor,
            backend=backend,
            metadata=metadata,
        )

    def sqlite_store(
        self,
        *,
        db_path: str | Path | None = None,
        purpose: str = "",
    ) -> SQLitePluginStore:
        path = Path(db_path) if db_path is not None else self._settings.cms_db_path
        store = SQLitePluginStore(
            plugin_id=self.plugin_id,
            database=Database(path),
            audit_log=self._audit,
        )
        store.audit("adapter.sqlite.open", target=purpose, metadata={"purpose": purpose})
        return store

    def postgres_store(self, *, dsn: str, purpose: str = "") -> PostgresPluginStore:
        if not dsn:
            raise RuntimeError("PostgreSQL plugin storage requires a DSN")
        store = PostgresPluginStore(plugin_id=self.plugin_id, dsn=dsn, audit_log=self._audit)
        store.audit("adapter.postgres.open", target=purpose, metadata={"purpose": purpose})
        return store

    def service_desk_repository(self, settings: dict[str, Any] | None = None) -> Any:
        """Create the ITSM request repository through the selected platform backend."""

        from archub_cms.infrastructure.plugins.itsm_request_repository import (
            PostgresRequestRepository,
            SqliteRequestRepository,
        )

        plugin_settings = dict(settings or {})
        storage = str(plugin_settings.get("storage") or "sqlite").strip().lower()
        if storage in _POSTGRES_ALIASES:
            dsn = str(
                plugin_settings.get("dsn")
                or plugin_settings.get("postgres_dsn")
                or os.environ.get("ARCHUB_ITSM_PG_DSN")
                or ""
            )
            if not dsn:
                raise RuntimeError(
                    "ITSM storage 'postgres' requires a 'dsn' setting or ARCHUB_ITSM_PG_DSN"
                )
            return PostgresRequestRepository(
                self.postgres_store(dsn=dsn, purpose="itsm.service_desk")
            )

        db_path = plugin_settings.get("db_path") or self._settings.cms_db_path
        return SqliteRequestRepository(
            self.sqlite_store(db_path=db_path, purpose="itsm.service_desk")
        )


def _json(value: dict[str, Any]) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return json.dumps({"repr": repr(value)}, ensure_ascii=False)


def _with_error(
    metadata: dict[str, Any] | None,
    exc: Exception,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    payload["error"] = str(exc)
    payload["error_type"] = type(exc).__name__
    return payload


def _redact_dsn(dsn: str) -> str:
    parsed = urlsplit(dsn)
    if not parsed.password:
        return dsn
    username = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:***@{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
