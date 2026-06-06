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
    (
        "0003_comments",
        """
        CREATE TABLE IF NOT EXISTS archub_comments (
            comment_id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL,
            parent_comment_id TEXT NOT NULL DEFAULT '',
            author TEXT NOT NULL,
            body TEXT NOT NULL,
            mentions_json TEXT NOT NULL DEFAULT '[]',
            reactions_json TEXT NOT NULL DEFAULT '{}',
            resolved INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL DEFAULT 0
        )
        """,
    ),
    (
        "0003_comments_node_idx",
        "CREATE INDEX IF NOT EXISTS idx_archub_comments_node ON archub_comments (node_id)",
    ),
    (
        "0004_subscriptions",
        """
        CREATE TABLE IF NOT EXISTS archub_subscriptions (
            subscription_id TEXT PRIMARY KEY,
            subscriber TEXT NOT NULL,
            node_id TEXT NOT NULL DEFAULT '',
            event_prefix TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL DEFAULT 0
        )
        """,
    ),
    (
        "0004_subscriptions_subscriber_idx",
        "CREATE INDEX IF NOT EXISTS idx_archub_subscriptions_subscriber "
        "ON archub_subscriptions (subscriber)",
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
