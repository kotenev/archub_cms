"""SQLite adapter for the content repository port.

Reads the ``archub_content_nodes`` table (the same table the legacy service
owns) and maps rows to :class:`ContentNode` aggregates. Row→aggregate mapping
mirrors ``cms._node_from_row`` exactly so both views of the tree agree.
"""

from __future__ import annotations

__all__ = ["SqliteContentRepository"]

import json
import sqlite3
from typing import Any

from archub_cms.domain.content.node import ContentNode, NodeStatus
from archub_cms.domain.content.value_objects import RoutePath, Slug
from archub_cms.infrastructure.db.database import Database

_TRASHED = "trashed"


def _load_dict(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _node_from_row(row: sqlite3.Row) -> ContentNode:
    return ContentNode(
        node_id=str(row["node_id"]),
        parent_id=str(row["parent_id"]) if row["parent_id"] is not None else None,
        content_type_alias=str(row["content_type_alias"]),
        name=str(row["name"]),
        slug=Slug(str(row["slug"] or "")),
        route_path=RoutePath(str(row["route_path"])),
        level=int(row["level"] or 0),
        status=NodeStatus(str(row["status"] or "draft")),
        draft=_load_dict(row["draft_json"]),
        published=_load_dict(row["published_json"]),
        sort_order=int(row["sort_order"] or 0),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        published_at=float(row["published_at"]) if row["published_at"] is not None else None,
        created_by=str(row["created_by"] or ""),
        updated_by=str(row["updated_by"] or ""),
    )


class SqliteContentRepository:
    """Read repository over the content tree using short-lived connections."""

    def __init__(self, database: Database) -> None:
        self._db = database

    def get(self, node_id: str) -> ContentNode | None:
        conn = self._db.connect()
        try:
            row = conn.execute(
                "SELECT * FROM archub_content_nodes WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            return _node_from_row(row) if row is not None else None
        finally:
            conn.close()

    def get_by_route(self, route_path: str) -> ContentNode | None:
        clean = "/" + route_path.strip("/")
        conn = self._db.connect()
        try:
            row = conn.execute(
                "SELECT * FROM archub_content_nodes WHERE route_path = ? AND status = 'published'",
                (clean,),
            ).fetchone()
            return _node_from_row(row) if row is not None else None
        finally:
            conn.close()

    def list_tree(self, *, include_trashed: bool = False) -> list[ContentNode]:
        conn = self._db.connect()
        try:
            if include_trashed:
                rows = conn.execute(
                    """
                    SELECT * FROM archub_content_nodes
                    ORDER BY level, parent_id IS NOT NULL, parent_id, sort_order, name
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM archub_content_nodes
                    WHERE status != ?
                    ORDER BY level, parent_id IS NOT NULL, parent_id, sort_order, name
                    """,
                    (_TRASHED,),
                ).fetchall()
            return [_node_from_row(row) for row in rows]
        finally:
            conn.close()

    def children(self, parent_id: str | None) -> list[ContentNode]:
        conn = self._db.connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM archub_content_nodes
                WHERE parent_id IS ? AND status != ?
                ORDER BY sort_order, name
                """,
                (parent_id, _TRASHED),
            ).fetchall()
            return [_node_from_row(row) for row in rows]
        finally:
            conn.close()

    def slug_exists(
        self, parent_id: str | None, slug: str, *, exclude_id: str | None = None
    ) -> bool:
        conn = self._db.connect()
        try:
            row = conn.execute(
                """
                SELECT 1 FROM archub_content_nodes
                WHERE parent_id IS ? AND slug = ? AND node_id != ?
                LIMIT 1
                """,
                (parent_id, slug, exclude_id or ""),
            ).fetchone()
            return row is not None
        finally:
            conn.close()
