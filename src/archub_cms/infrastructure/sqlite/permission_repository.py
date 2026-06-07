"""SQLite repository for fine-grained permissions."""

from __future__ import annotations

__all__ = ["PermissionRepository"]

import sqlite3

from archub_cms.domain.permissions.models import Permission


class PermissionRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS permissions (
                permission_id TEXT PRIMARY KEY,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                level TEXT DEFAULT 'view',
                scope TEXT DEFAULT 'page',
                granted_by TEXT DEFAULT '',
                granted_at REAL NOT NULL
            )
            """
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_permissions_subject ON permissions(subject_type, subject_id)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_permissions_resource ON permissions(resource_type, resource_id)"
        )
        self._db.commit()

    def save(self, permission: Permission) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO permissions (permission_id, subject_type, subject_id, resource_type, resource_id, level, scope, granted_by, granted_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                permission.permission_id,
                permission.subject_type,
                permission.subject_id,
                permission.resource_type,
                permission.resource_id,
                permission.level,
                permission.scope,
                permission.granted_by,
                permission.granted_at,
            ),
        )
        self._db.commit()

    def list_for_resource(self, resource_type: str, resource_id: str) -> list[Permission]:
        rows = self._db.execute(
            "SELECT * FROM permissions WHERE resource_type = ? AND resource_id = ?",
            (resource_type, resource_id),
        ).fetchall()
        return [
            Permission(
                permission_id=r["permission_id"],
                subject_type=r["subject_type"],
                subject_id=r["subject_id"],
                resource_type=r["resource_type"],
                resource_id=r["resource_id"],
                level=r["level"],
                scope=r["scope"],
                granted_by=r["granted_by"],
                granted_at=r["granted_at"],
            )
            for r in rows
        ]

    def list_for_subject(self, subject_type: str, subject_id: str) -> list[Permission]:
        rows = self._db.execute(
            "SELECT * FROM permissions WHERE subject_type = ? AND subject_id = ?",
            (subject_type, subject_id),
        ).fetchall()
        return [
            Permission(
                permission_id=r["permission_id"],
                subject_type=r["subject_type"],
                subject_id=r["subject_id"],
                resource_type=r["resource_type"],
                resource_id=r["resource_id"],
                level=r["level"],
                scope=r["scope"],
                granted_by=r["granted_by"],
                granted_at=r["granted_at"],
            )
            for r in rows
        ]

    def delete(self, permission_id: str) -> bool:
        cursor = self._db.execute(
            "DELETE FROM permissions WHERE permission_id = ?", (permission_id,)
        )
        self._db.commit()
        return cursor.rowcount > 0
