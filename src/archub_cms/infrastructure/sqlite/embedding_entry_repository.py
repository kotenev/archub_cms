"""SQLite repository for embedding entries."""

from __future__ import annotations

__all__ = ["EmbeddingEntryRepository"]

import sqlite3

from archub_cms.domain.embedding_store.models import EmbeddingEntry, EmbeddingStatus


class EmbeddingEntryRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS embedding_entries (
                entry_id TEXT PRIMARY KEY,
                route_path TEXT NOT NULL UNIQUE,
                model TEXT NOT NULL,
                dim INTEGER NOT NULL,
                status TEXT DEFAULT 'indexed',
                content_hash TEXT DEFAULT '',
                token_count INTEGER DEFAULT 0,
                indexed_at REAL NOT NULL
            )
            """
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_embedding_status ON embedding_entries(status)"
        )
        self._db.commit()

    def save(self, entry: EmbeddingEntry) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO embedding_entries (entry_id, route_path, model, dim, status, content_hash, token_count, indexed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.entry_id,
                entry.route_path,
                entry.model,
                entry.dim,
                entry.status,
                entry.content_hash,
                entry.token_count,
                entry.indexed_at,
            ),
        )
        self._db.commit()

    def get_by_path(self, route_path: str) -> EmbeddingEntry | None:
        row = self._db.execute(
            "SELECT * FROM embedding_entries WHERE route_path = ?", (route_path,)
        ).fetchone()
        if row is None:
            return None
        return EmbeddingEntry(
            entry_id=row["entry_id"],
            route_path=row["route_path"],
            model=row["model"],
            dim=row["dim"],
            status=row["status"],
            content_hash=row["content_hash"],
            token_count=row["token_count"],
            indexed_at=row["indexed_at"],
        )

    def mark_stale(self, route_path: str) -> None:
        self._db.execute(
            "UPDATE embedding_entries SET status = ? WHERE route_path = ?",
            (EmbeddingStatus.STALE, route_path),
        )
        self._db.commit()

    def list_by_status(self, status: str, limit: int = 100) -> list[EmbeddingEntry]:
        rows = self._db.execute(
            "SELECT * FROM embedding_entries WHERE status = ? LIMIT ?", (status, limit)
        ).fetchall()
        return [
            EmbeddingEntry(
                entry_id=r["entry_id"],
                route_path=r["route_path"],
                model=r["model"],
                dim=r["dim"],
                status=r["status"],
                content_hash=r["content_hash"],
                token_count=r["token_count"],
                indexed_at=r["indexed_at"],
            )
            for r in rows
        ]

    def stats(self) -> dict[str, int]:
        rows = self._db.execute(
            "SELECT status, COUNT(*) as cnt FROM embedding_entries GROUP BY status"
        ).fetchall()
        result = {"total": 0, "indexed": 0, "stale": 0, "failed": 0, "pending": 0}
        for r in rows:
            result["total"] += r["cnt"]
            result[r["status"]] = r["cnt"]
        return result
