"""Per-plugin enable/disable and settings persistence (SQLite).

Backed by the ``archub_plugin_config`` table from
``infrastructure.db.schema``. Falls back to the manifest's
``enabled_by_default`` when a plugin has no stored row yet.
"""

from __future__ import annotations

__all__ = ["PluginConfigStore"]

import json
import time
from typing import Any

from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.db.schema import apply_extension_migrations


class PluginConfigStore:
    def __init__(self, database: Database) -> None:
        self._db = database
        conn = self._db.connect()
        try:
            apply_extension_migrations(conn)
        finally:
            conn.close()

    def is_enabled(self, plugin_id: str, *, default: bool = False) -> bool:
        conn = self._db.connect()
        try:
            row = conn.execute(
                "SELECT enabled FROM archub_plugin_config WHERE plugin_id = ?",
                (plugin_id,),
            ).fetchone()
            return bool(row["enabled"]) if row is not None else default
        finally:
            conn.close()

    def get_settings(self, plugin_id: str) -> dict[str, Any]:
        conn = self._db.connect()
        try:
            row = conn.execute(
                "SELECT settings_json FROM archub_plugin_config WHERE plugin_id = ?",
                (plugin_id,),
            ).fetchone()
            if row is None:
                return {}
            try:
                parsed = json.loads(row["settings_json"] or "{}")
            except (ValueError, TypeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        finally:
            conn.close()

    def set_enabled(self, plugin_id: str, enabled: bool, *, updated_by: str = "") -> None:
        self._upsert(plugin_id, enabled=enabled, updated_by=updated_by)

    def set_settings(
        self, plugin_id: str, settings: dict[str, Any], *, updated_by: str = ""
    ) -> None:
        self._upsert(plugin_id, settings=settings, updated_by=updated_by)

    def all(self) -> dict[str, dict[str, Any]]:
        conn = self._db.connect()
        try:
            rows = conn.execute(
                "SELECT plugin_id, enabled, settings_json FROM archub_plugin_config"
            ).fetchall()
            result: dict[str, dict[str, Any]] = {}
            for row in rows:
                try:
                    settings = json.loads(row["settings_json"] or "{}")
                except (ValueError, TypeError):
                    settings = {}
                result[str(row["plugin_id"])] = {
                    "enabled": bool(row["enabled"]),
                    "settings": settings if isinstance(settings, dict) else {},
                }
            return result
        finally:
            conn.close()

    def _upsert(
        self,
        plugin_id: str,
        *,
        enabled: bool | None = None,
        settings: dict[str, Any] | None = None,
        updated_by: str = "",
    ) -> None:
        conn = self._db.connect()
        try:
            existing = conn.execute(
                "SELECT enabled, settings_json FROM archub_plugin_config WHERE plugin_id = ?",
                (plugin_id,),
            ).fetchone()
            current_enabled = bool(existing["enabled"]) if existing is not None else False
            current_settings = existing["settings_json"] if existing is not None else "{}"
            new_enabled = current_enabled if enabled is None else enabled
            new_settings = (
                json.dumps(settings, ensure_ascii=False, sort_keys=True)
                if settings is not None
                else current_settings
            )
            conn.execute(
                """
                INSERT INTO archub_plugin_config (
                    plugin_id, enabled, settings_json, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    settings_json = excluded.settings_json,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (plugin_id, int(new_enabled), new_settings, time.time(), updated_by),
            )
            conn.commit()
        finally:
            conn.close()
