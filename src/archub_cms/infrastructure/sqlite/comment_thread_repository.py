"""SQLite repository for comment threads."""

from __future__ import annotations

__all__ = ["CommentThreadRepository"]

import sqlite3

from archub_cms.domain.comments_thread.models import Comment, CommentThread


class CommentThreadRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS comment_threads (
                thread_id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                title TEXT DEFAULT '',
                resolved INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                comment_count INTEGER DEFAULT 0
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                comment_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                author TEXT NOT NULL,
                body TEXT NOT NULL,
                parent_comment_id TEXT DEFAULT '',
                status TEXT DEFAULT 'active',
                created_at REAL NOT NULL,
                updated_at REAL DEFAULT 0,
                reactions TEXT DEFAULT '{}'
            )
            """
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_comments_thread ON comments(thread_id)")
        self._db.commit()

    def save_thread(self, thread: CommentThread) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO comment_threads (thread_id, node_id, title, resolved, created_at, comment_count)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                thread.thread_id,
                thread.node_id,
                thread.title,
                int(thread.resolved),
                thread.created_at,
                thread.comment_count,
            ),
        )
        self._db.commit()

    def save_comment(self, comment: Comment) -> None:
        import json

        self._db.execute(
            "INSERT OR REPLACE INTO comments (comment_id, thread_id, author, body, parent_comment_id, status, created_at, updated_at, reactions)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                comment.comment_id,
                comment.thread_id,
                comment.author,
                comment.body,
                comment.parent_comment_id,
                comment.status,
                comment.created_at,
                comment.updated_at,
                json.dumps(comment.reactions),
            ),
        )
        self._db.commit()

    def get_thread(self, thread_id: str) -> CommentThread | None:
        row = self._db.execute(
            "SELECT * FROM comment_threads WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        if row is None:
            return None
        return CommentThread(
            thread_id=row["thread_id"],
            node_id=row["node_id"],
            title=row["title"],
            resolved=bool(row["resolved"]),
            created_at=row["created_at"],
            comment_count=row["comment_count"],
        )

    def list_threads_for_node(self, node_id: str) -> list[CommentThread]:
        rows = self._db.execute(
            "SELECT * FROM comment_threads WHERE node_id = ? ORDER BY created_at DESC", (node_id,)
        ).fetchall()
        return [
            CommentThread(
                thread_id=r["thread_id"],
                node_id=r["node_id"],
                title=r["title"],
                resolved=bool(r["resolved"]),
                created_at=r["created_at"],
                comment_count=r["comment_count"],
            )
            for r in rows
        ]

    def list_comments_for_thread(self, thread_id: str) -> list[Comment]:
        import json

        rows = self._db.execute(
            "SELECT * FROM comments WHERE thread_id = ? ORDER BY created_at", (thread_id,)
        ).fetchall()
        return [
            Comment(
                comment_id=r["comment_id"],
                thread_id=r["thread_id"],
                author=r["author"],
                body=r["body"],
                parent_comment_id=r["parent_comment_id"],
                status=r["status"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                reactions=json.loads(r["reactions"]),
            )
            for r in rows
        ]
