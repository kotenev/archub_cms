"""Additive schema migrations for the new bounded contexts.

The legacy ``ArcHubCMSService._ensure_db`` still owns the original CMS tables;
relocating ~350 lines of in-place DDL wholesale would risk the behavior the
characterization tests pin. Instead, new contexts register their tables here as
idempotent, ordered migrations applied via :func:`apply_extension_migrations`.
As each legacy context is decomposed in later phases, its ``CREATE TABLE``
statements move from ``cms.py`` into this registry.
"""

from __future__ import annotations

__all__ = ["MIGRATIONS", "apply_extension_migrations"]

import sqlite3

# (id, SQL). ``id`` is a stable, human-readable key for traceability/logging.
MIGRATIONS: tuple[tuple[str, str], ...] = (
    (
        "0001_plugin_config",
        """
        CREATE TABLE IF NOT EXISTS archub_plugin_config (
            plugin_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0,
            settings_json TEXT NOT NULL DEFAULT '{}',
            updated_at REAL NOT NULL DEFAULT 0,
            updated_by TEXT NOT NULL DEFAULT ''
        )
        """,
    ),
    (
        "0002_embeddings",
        """
        CREATE TABLE IF NOT EXISTS archub_embeddings (
            route_path TEXT NOT NULL,
            model TEXT NOT NULL,
            dim INTEGER NOT NULL,
            vector_json TEXT NOT NULL,
            content_hash TEXT NOT NULL DEFAULT '',
            updated_at REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (route_path, model)
        )
        """,
    ),
)


def apply_extension_migrations(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Apply all additive migrations idempotently; return the applied ids."""
    applied: list[str] = []
    for migration_id, sql in MIGRATIONS:
        conn.execute(sql)
        applied.append(migration_id)
    conn.commit()
    return tuple(applied)
