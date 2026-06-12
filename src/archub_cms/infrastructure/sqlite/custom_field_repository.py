"""SQLite repository for custom fields."""

from __future__ import annotations

__all__ = ["CustomFieldRepository"]

import sqlite3

from archub_cms.domain.custom_fields.models import CustomField, CustomFieldDefinition


class CustomFieldRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_field_definitions (
                field_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                field_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                required INTEGER DEFAULT 0,
                options TEXT DEFAULT '[]',
                default_value TEXT DEFAULT '',
                space_key TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_field_values (
                field_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                value TEXT DEFAULT '',
                PRIMARY KEY (field_id, node_id)
            )
            """
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_field_values_node ON custom_field_values(node_id)"
        )
        self._db.commit()

    def save_definition(self, definition: CustomFieldDefinition) -> None:
        import json

        self._db.execute(
            "INSERT OR REPLACE INTO custom_field_definitions (field_id, name, field_type, description, required, options, default_value, space_key, sort_order)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                definition.field_id,
                definition.name,
                definition.field_type,
                definition.description,
                int(definition.required),
                json.dumps(list(definition.options)),
                definition.default_value,
                definition.space_key,
                definition.sort_order,
            ),
        )
        self._db.commit()

    def save_value(self, field: CustomField) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO custom_field_values (field_id, node_id, value) VALUES (?, ?, ?)",
            (field.field_id, field.node_id, field.value),
        )
        self._db.commit()

    def get_definition(self, field_id: str) -> CustomFieldDefinition | None:
        import json

        row = self._db.execute(
            "SELECT * FROM custom_field_definitions WHERE field_id = ?", (field_id,)
        ).fetchone()
        if row is None:
            return None
        return CustomFieldDefinition(
            field_id=row["field_id"],
            name=row["name"],
            field_type=row["field_type"],
            description=row["description"],
            required=bool(row["required"]),
            options=tuple(json.loads(row["options"])),
            default_value=row["default_value"],
            space_key=row["space_key"],
            sort_order=row["sort_order"],
        )

    def list_definitions(self, space_key: str = "") -> list[CustomFieldDefinition]:
        import json

        sql = "SELECT * FROM custom_field_definitions"
        params: list[str] = []
        if space_key:
            sql += " WHERE space_key = ?"
            params.append(space_key)
        sql += " ORDER BY sort_order, name"
        rows = self._db.execute(sql, params).fetchall()
        return [
            CustomFieldDefinition(
                field_id=r["field_id"],
                name=r["name"],
                field_type=r["field_type"],
                description=r["description"],
                required=bool(r["required"]),
                options=tuple(json.loads(r["options"])),
                default_value=r["default_value"],
                space_key=r["space_key"],
                sort_order=r["sort_order"],
            )
            for r in rows
        ]

    def get_values_for_node(self, node_id: str) -> dict[str, str]:
        rows = self._db.execute(
            "SELECT field_id, value FROM custom_field_values WHERE node_id = ?", (node_id,)
        ).fetchall()
        return {r["field_id"]: r["value"] for r in rows}
