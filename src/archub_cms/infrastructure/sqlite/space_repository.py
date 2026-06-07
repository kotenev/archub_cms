"""SQLite repository for the spaces bounded context."""

from __future__ import annotations

__all__ = ["SqliteSpaceRepository"]

import json
import sqlite3

from archub_cms.domain.spaces.repository import SpaceRepository
from archub_cms.domain.spaces.space import Space, SpaceSettings
from archub_cms.infrastructure.db.database import Database


class SqliteSpaceRepository(SpaceRepository):
    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._db.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archub_spaces (
                    space_key       TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    description     TEXT NOT NULL DEFAULT '',
                    root_node_id    TEXT NOT NULL DEFAULT '',
                    owner           TEXT NOT NULL DEFAULT '',
                    visibility      TEXT NOT NULL DEFAULT 'public',
                    settings        TEXT NOT NULL DEFAULT '{}',
                    tags            TEXT NOT NULL DEFAULT '[]',
                    document_count  INTEGER NOT NULL DEFAULT 0,
                    created_at      REAL NOT NULL DEFAULT 0,
                    updated_at      REAL NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def get(self, space_key: str) -> Space | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM archub_spaces WHERE space_key = ?", (space_key,)
            ).fetchone()
        return self._row_to_space(row) if row else None

    def list_all(self) -> list[Space]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM archub_spaces ORDER BY name").fetchall()
        return [self._row_to_space(row) for row in rows]

    def upsert(self, space: Space) -> Space:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO archub_spaces
                (space_key, name, description, root_node_id, owner, visibility,
                 settings, tags, document_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._space_to_row(space),
            )
            conn.commit()
        return space

    def delete(self, space_key: str) -> bool:
        with self._db.connect() as conn:
            cursor = conn.execute("DELETE FROM archub_spaces WHERE space_key = ?", (space_key,))
            conn.commit()
            return cursor.rowcount > 0

    def find_by_owner(self, owner: str) -> list[Space]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM archub_spaces WHERE owner = ? ORDER BY name",
                (owner,),
            ).fetchall()
        return [self._row_to_space(row) for row in rows]

    @staticmethod
    def _row_to_space(row: sqlite3.Row) -> Space:
        settings_data = json.loads(row["settings"])
        return Space(
            space_key=row["space_key"],
            name=row["name"],
            description=row["description"],
            root_node_id=row["root_node_id"],
            owner=row["owner"],
            visibility=row["visibility"],
            settings=SpaceSettings(
                **{
                    k: v
                    for k, v in settings_data.items()
                    if k in SpaceSettings.__dataclass_fields__
                }
            ),
            tags=tuple(json.loads(row["tags"])),
            document_count=row["document_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _space_to_row(space: Space) -> tuple[object, ...]:
        return (
            space.space_key,
            space.name,
            space.description,
            space.root_node_id,
            space.owner,
            space.visibility,
            json.dumps(space.settings.as_dict()),
            json.dumps(list(space.tags)),
            space.document_count,
            space.created_at,
            space.updated_at,
        )
