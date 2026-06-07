"""SQLite repository for the bookmarks bounded context."""

from __future__ import annotations

__all__ = ["SqliteBookmarkRepository"]

import sqlite3

from archub_cms.domain.bookmarks.bookmark import Bookmark, BookmarkFolder
from archub_cms.domain.bookmarks.repository import BookmarkRepository
from archub_cms.infrastructure.db.database import Database


class SqliteBookmarkRepository(BookmarkRepository):
    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        with self._db.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archub_bookmarks (
                    bookmark_id  TEXT PRIMARY KEY,
                    username     TEXT NOT NULL,
                    node_id      TEXT NOT NULL,
                    folder_id    TEXT NOT NULL DEFAULT '',
                    note         TEXT NOT NULL DEFAULT '',
                    created_at   REAL NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_bookmark_user ON archub_bookmarks(username)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_bookmark_user_node ON archub_bookmarks(username, node_id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archub_bookmark_folders (
                    folder_id          TEXT PRIMARY KEY,
                    username           TEXT NOT NULL,
                    name               TEXT NOT NULL,
                    parent_folder_id   TEXT NOT NULL DEFAULT '',
                    sort_order         INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def add(self, bookmark: Bookmark) -> Bookmark:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO archub_bookmarks
                (bookmark_id, username, node_id, folder_id, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bookmark.bookmark_id,
                    bookmark.username,
                    bookmark.node_id,
                    bookmark.folder_id,
                    bookmark.note,
                    bookmark.created_at,
                ),
            )
            conn.commit()
        return bookmark

    def remove(self, bookmark_id: str) -> bool:
        with self._db.connect() as conn:
            cursor = conn.execute(
                "DELETE FROM archub_bookmarks WHERE bookmark_id = ?", (bookmark_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_for_user(self, username: str, *, folder_id: str = "") -> list[Bookmark]:
        if folder_id:
            sql = "SELECT * FROM archub_bookmarks WHERE username = ? AND folder_id = ? ORDER BY created_at DESC"
            params: tuple[object, ...] = (username, folder_id)
        else:
            sql = "SELECT * FROM archub_bookmarks WHERE username = ? ORDER BY created_at DESC"
            params = (username,)
        with self._db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_bookmark(row) for row in rows]

    def get(self, bookmark_id: str) -> Bookmark | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM archub_bookmarks WHERE bookmark_id = ?", (bookmark_id,)
            ).fetchone()
        return self._row_to_bookmark(row) if row else None

    def find(self, username: str, node_id: str) -> Bookmark | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM archub_bookmarks WHERE username = ? AND node_id = ?",
                (username, node_id),
            ).fetchone()
        return self._row_to_bookmark(row) if row else None

    def folders(self, username: str) -> list[BookmarkFolder]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM archub_bookmark_folders WHERE username = ? ORDER BY sort_order, name",
                (username,),
            ).fetchall()
        return [self._row_to_folder(row) for row in rows]

    def create_folder(self, folder: BookmarkFolder) -> BookmarkFolder:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO archub_bookmark_folders
                (folder_id, username, name, parent_folder_id, sort_order)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    folder.folder_id,
                    folder.username,
                    folder.name,
                    folder.parent_folder_id,
                    folder.sort_order,
                ),
            )
            conn.commit()
        return folder

    def delete_folder(self, folder_id: str) -> bool:
        with self._db.connect() as conn:
            cursor = conn.execute(
                "DELETE FROM archub_bookmark_folders WHERE folder_id = ?", (folder_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_bookmark(row: sqlite3.Row) -> Bookmark:
        return Bookmark(
            bookmark_id=row["bookmark_id"],
            username=row["username"],
            node_id=row["node_id"],
            folder_id=row["folder_id"],
            note=row["note"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_folder(row: sqlite3.Row) -> BookmarkFolder:
        return BookmarkFolder(
            folder_id=row["folder_id"],
            username=row["username"],
            name=row["name"],
            parent_folder_id=row["parent_folder_id"],
            sort_order=row["sort_order"],
        )
