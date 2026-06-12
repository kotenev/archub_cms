"""SQLite repository for page templates."""

from __future__ import annotations

__all__ = ["TemplateRepository"]

import sqlite3

from archub_cms.domain.templates.models import PageTemplate


class TemplateRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS page_templates (
                template_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                body TEXT NOT NULL,
                category TEXT DEFAULT 'blank',
                icon TEXT DEFAULT '📄',
                description TEXT DEFAULT '',
                source_node_id TEXT DEFAULT '',
                space_key TEXT DEFAULT '',
                created_by TEXT DEFAULT '',
                created_at REAL NOT NULL,
                usage_count INTEGER DEFAULT 0
            )
            """
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_templates_space ON page_templates(space_key)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_templates_category ON page_templates(category)"
        )
        self._db.commit()

    def save(self, template: PageTemplate) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO page_templates (template_id, name, body, category, icon, description, source_node_id, space_key, created_by, created_at, usage_count)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                template.template_id,
                template.name,
                template.body,
                template.category,
                template.icon,
                template.description,
                template.source_node_id,
                template.space_key,
                template.created_by,
                template.created_at,
                template.usage_count,
            ),
        )
        self._db.commit()

    def get(self, template_id: str) -> PageTemplate | None:
        row = self._db.execute(
            "SELECT * FROM page_templates WHERE template_id = ?", (template_id,)
        ).fetchone()
        if row is None:
            return None
        return PageTemplate(
            template_id=row["template_id"],
            name=row["name"],
            body=row["body"],
            category=row["category"],
            icon=row["icon"],
            description=row["description"],
            source_node_id=row["source_node_id"],
            space_key=row["space_key"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            usage_count=row["usage_count"],
        )

    def list_all(self, *, space_key: str = "", category: str = "") -> list[PageTemplate]:
        sql = "SELECT * FROM page_templates"
        params: list[str] = []
        conditions: list[str] = []
        if space_key:
            conditions.append("space_key = ?")
            params.append(space_key)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY name"
        rows = self._db.execute(sql, params).fetchall()
        return [
            PageTemplate(
                template_id=r["template_id"],
                name=r["name"],
                body=r["body"],
                category=r["category"],
                icon=r["icon"],
                description=r["description"],
                source_node_id=r["source_node_id"],
                space_key=r["space_key"],
                created_by=r["created_by"],
                created_at=r["created_at"],
                usage_count=r["usage_count"],
            )
            for r in rows
        ]

    def increment_usage(self, template_id: str) -> None:
        self._db.execute(
            "UPDATE page_templates SET usage_count = usage_count + 1 WHERE template_id = ?",
            (template_id,),
        )
        self._db.commit()
