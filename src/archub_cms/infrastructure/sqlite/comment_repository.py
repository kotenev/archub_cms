"""SQLite adapter for the collaboration ``CommentRepository`` port.

Backed by the ``archub_comments`` table (see ``infrastructure.db.schema``).
Mentions and reactions are stored as JSON columns on the comment row.
"""

from __future__ import annotations

__all__ = ["SqliteCommentRepository"]

import json
import sqlite3

from archub_cms.domain.collaboration.comment import Comment
from archub_cms.domain.collaboration.value_objects import Mention
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.db.schema import apply_extension_migrations


def _dump_reactions(reactions: dict[str, set[str]]) -> str:
    return json.dumps({kind: sorted(users) for kind, users in reactions.items() if users})


def _load_reactions(raw: str | None) -> dict[str, set[str]]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(kind): set(users) for kind, users in parsed.items() if isinstance(users, list)}


def _load_mentions(raw: str | None) -> tuple[Mention, ...]:
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return ()
    return tuple(Mention(str(item)) for item in parsed) if isinstance(parsed, list) else ()


def _comment_from_row(row: sqlite3.Row) -> Comment:
    return Comment(
        comment_id=str(row["comment_id"]),
        node_id=str(row["node_id"]),
        author=str(row["author"]),
        body=str(row["body"]),
        parent_comment_id=str(row["parent_comment_id"] or ""),
        mentions=_load_mentions(row["mentions_json"]),
        reactions=_load_reactions(row["reactions_json"]),
        resolved=bool(row["resolved"]),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
    )


class SqliteCommentRepository:
    def __init__(self, database: Database) -> None:
        self._db = database
        conn = self._db.connect()
        try:
            apply_extension_migrations(conn)
        finally:
            conn.close()

    def add(self, comment: Comment) -> None:
        conn = self._db.connect()
        try:
            conn.execute(
                """
                INSERT INTO archub_comments (
                    comment_id, node_id, parent_comment_id, author, body,
                    mentions_json, reactions_json, resolved, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._row(comment),
            )
            conn.commit()
        finally:
            conn.close()

    def update(self, comment: Comment) -> None:
        conn = self._db.connect()
        try:
            conn.execute(
                """
                UPDATE archub_comments SET
                    body = ?, mentions_json = ?, reactions_json = ?,
                    resolved = ?, updated_at = ?
                WHERE comment_id = ?
                """,
                (
                    comment.body,
                    json.dumps([m.username for m in comment.mentions]),
                    _dump_reactions(comment.reactions),
                    int(comment.resolved),
                    comment.updated_at,
                    comment.comment_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, comment_id: str) -> Comment | None:
        conn = self._db.connect()
        try:
            row = conn.execute(
                "SELECT * FROM archub_comments WHERE comment_id = ?", (comment_id,)
            ).fetchone()
            return _comment_from_row(row) if row is not None else None
        finally:
            conn.close()

    def delete(self, comment_id: str) -> bool:
        conn = self._db.connect()
        try:
            cursor = conn.execute(
                "DELETE FROM archub_comments WHERE comment_id = ? OR parent_comment_id = ?",
                (comment_id, comment_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list_for_node(self, node_id: str, *, include_resolved: bool = True) -> list[Comment]:
        conn = self._db.connect()
        try:
            if include_resolved:
                rows = conn.execute(
                    "SELECT * FROM archub_comments WHERE node_id = ? ORDER BY created_at",
                    (node_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM archub_comments
                    WHERE node_id = ? AND resolved = 0 ORDER BY created_at
                    """,
                    (node_id,),
                ).fetchall()
            return [_comment_from_row(row) for row in rows]
        finally:
            conn.close()

    def list_mentions_for(self, username: str) -> list[Comment]:
        target = username.strip().lstrip("@").casefold()
        conn = self._db.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM archub_comments WHERE mentions_json LIKE ? ORDER BY created_at DESC",
                (f'%"{target}"%',),
            ).fetchall()
        finally:
            conn.close()
        comments = [_comment_from_row(row) for row in rows]
        # LIKE is a coarse pre-filter; confirm membership exactly.
        return [c for c in comments if any(m.username == target for m in c.mentions)]

    @staticmethod
    def _row(comment: Comment) -> tuple:
        return (
            comment.comment_id,
            comment.node_id,
            comment.parent_comment_id,
            comment.author,
            comment.body,
            json.dumps([m.username for m in comment.mentions]),
            _dump_reactions(comment.reactions),
            int(comment.resolved),
            comment.created_at,
            comment.updated_at,
        )
