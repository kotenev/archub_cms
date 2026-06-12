"""SQLite repository for activity feed."""

from __future__ import annotations

__all__ = ["ActivityFeedRepository"]

import json
import sqlite3

from archub_cms.domain.activity_feed.models import ActivityEntry


class ActivityFeedRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_feed (
                entry_id TEXT PRIMARY KEY,
                activity_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                space_key TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                timestamp REAL NOT NULL
            )
            """
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_activity_actor ON activity_feed(actor)")
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_target ON activity_feed(target_type, target_id)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_activity_time ON activity_feed(timestamp DESC)"
        )
        self._db.commit()

    def save(self, entry: ActivityEntry) -> None:
        self._db.execute(
            "INSERT INTO activity_feed (entry_id, activity_type, actor, target_type, target_id, space_key, summary, metadata, timestamp)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.entry_id,
                entry.activity_type,
                entry.actor,
                entry.target_type,
                entry.target_id,
                entry.space_key,
                entry.summary,
                json.dumps(entry.metadata or {}),
                entry.timestamp,
            ),
        )
        self._db.commit()

    def list_recent(
        self, *, limit: int = 50, space_key: str = "", actor: str = ""
    ) -> list[ActivityEntry]:
        sql = "SELECT * FROM activity_feed"
        params: list[str | int] = []
        conditions: list[str] = []
        if space_key:
            conditions.append("space_key = ?")
            params.append(space_key)
        if actor:
            conditions.append("actor = ?")
            params.append(actor)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self._db.execute(sql, params).fetchall()
        return [
            ActivityEntry(
                entry_id=r["entry_id"],
                activity_type=r["activity_type"],
                actor=r["actor"],
                target_type=r["target_type"],
                target_id=r["target_id"],
                space_key=r["space_key"],
                summary=r["summary"],
                metadata=json.loads(r["metadata"]),
                timestamp=r["timestamp"],
            )
            for r in rows
        ]
