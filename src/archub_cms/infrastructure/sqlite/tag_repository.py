"""SQLite repository for the tags bounded context."""

from __future__ import annotations

__all__ = ["SqliteTagRepository"]

import json
import sqlite3

from archub_cms.domain.tags.repository import TagRepository
from archub_cms.domain.tags.tag import Tag, TagNode
from archub_cms.infrastructure.db.database import Database


class SqliteTagRepository(TagRepository):
    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._db.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archub_tags (
                    slug          TEXT PRIMARY KEY,
                    display_name  TEXT NOT NULL DEFAULT '',
                    parent_slug   TEXT NOT NULL DEFAULT '',
                    aliases       TEXT NOT NULL DEFAULT '[]',
                    usage_count   INTEGER NOT NULL DEFAULT 0,
                    description   TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.commit()

    def get(self, slug: str) -> Tag | None:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM archub_tags WHERE slug = ?", (slug,)).fetchone()
        return self._row_to_tag(row) if row else None

    def list_all(self) -> list[Tag]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM archub_tags ORDER BY display_name").fetchall()
        return [self._row_to_tag(row) for row in rows]

    def tree(self) -> list[TagNode]:
        tags = self.list_all()
        by_parent: dict[str, list[Tag]] = {}
        for tag in tags:
            by_parent.setdefault(tag.parent_slug, []).append(tag)
        roots = by_parent.get("", [])

        def build_node(tag: Tag) -> TagNode:
            children = [build_node(child) for child in by_parent.get(tag.slug, [])]
            return TagNode(tag=tag, children=tuple(children))

        return [build_node(root) for root in roots]

    def upsert(self, tag: Tag) -> Tag:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO archub_tags
                (slug, display_name, parent_slug, aliases, usage_count, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tag.slug,
                    tag.display_name,
                    tag.parent_slug,
                    json.dumps(list(tag.aliases)),
                    tag.usage_count,
                    tag.description,
                ),
            )
            conn.commit()
        return tag

    def delete(self, slug: str) -> bool:
        with self._db.connect() as conn:
            cursor = conn.execute("DELETE FROM archub_tags WHERE slug = ?", (slug,))
            conn.commit()
            return cursor.rowcount > 0

    def find_by_alias(self, alias: str) -> Tag | None:
        lowered = alias.casefold()
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM archub_tags").fetchall()
        for row in rows:
            tag = self._row_to_tag(row)
            if lowered in [a.casefold() for a in tag.aliases]:
                return tag
        return None

    @staticmethod
    def _row_to_tag(row: sqlite3.Row) -> Tag:
        return Tag(
            slug=row["slug"],
            display_name=row["display_name"],
            parent_slug=row["parent_slug"],
            aliases=tuple(json.loads(row["aliases"])),
            usage_count=row["usage_count"],
            description=row["description"],
        )
