"""SQLite repository for the audit trail bounded context."""

from __future__ import annotations

__all__ = ["SqliteAuditTrailRepository"]

import json
import sqlite3

from archub_cms.domain.audit_trail.entry import AuditEntry, AuditQuery
from archub_cms.domain.audit_trail.repository import AuditTrailRepository
from archub_cms.infrastructure.db.database import Database


class SqliteAuditTrailRepository(AuditTrailRepository):
    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._db.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archub_audit_trail (
                    entry_id        TEXT PRIMARY KEY,
                    action          TEXT NOT NULL,
                    aggregate_id    TEXT NOT NULL,
                    aggregate_type  TEXT NOT NULL DEFAULT '',
                    actor           TEXT NOT NULL DEFAULT '',
                    timestamp       REAL NOT NULL,
                    diff            TEXT NOT NULL DEFAULT '{}',
                    metadata        TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_aggregate ON archub_audit_trail(aggregate_id)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON archub_audit_trail(actor)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_action ON archub_audit_trail(action)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON archub_audit_trail(timestamp)"
            )
            conn.commit()

    def record(self, entry: AuditEntry) -> AuditEntry:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO archub_audit_trail
                (entry_id, action, aggregate_id, aggregate_type, actor, timestamp, diff, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.action,
                    entry.aggregate_id,
                    entry.aggregate_type,
                    entry.actor,
                    entry.timestamp,
                    json.dumps(entry.diff, default=str),
                    json.dumps(entry.metadata, default=str),
                ),
            )
            conn.commit()
        return entry

    def get(self, entry_id: str) -> AuditEntry | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM archub_audit_trail WHERE entry_id = ?", (entry_id,)
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def query(self, query: AuditQuery) -> list[AuditEntry]:
        clauses: list[str] = []
        params: list[object] = []
        if query.aggregate_id:
            clauses.append("aggregate_id = ?")
            params.append(query.aggregate_id)
        if query.actor:
            clauses.append("actor = ?")
            params.append(query.actor)
        if query.action:
            clauses.append("action = ?")
            params.append(query.action)
        if query.aggregate_type:
            clauses.append("aggregate_type = ?")
            params.append(query.aggregate_type)
        if query.from_timestamp:
            clauses.append("timestamp >= ?")
            params.append(query.from_timestamp)
        if query.to_timestamp:
            clauses.append("timestamp <= ?")
            params.append(query.to_timestamp)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM archub_audit_trail{where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([query.limit, query.offset])
        with self._db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def count(self, query: AuditQuery | None = None) -> int:
        if query is None:
            with self._db.connect() as conn:
                row = conn.execute("SELECT COUNT(*) FROM archub_audit_trail").fetchone()
            return int(row[0])
        entries = self.query(query)
        return len(entries)

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> AuditEntry:
        return AuditEntry(
            entry_id=row["entry_id"],
            action=row["action"],
            aggregate_id=row["aggregate_id"],
            aggregate_type=row["aggregate_type"],
            actor=row["actor"],
            timestamp=row["timestamp"],
            diff=json.loads(row["diff"]),
            metadata=json.loads(row["metadata"]),
        )
