"""SQLite repository for export jobs."""

from __future__ import annotations

__all__ = ["ExportJobRepository"]

import sqlite3

from archub_cms.domain.pdf_export.models import ExportJob


class ExportJobRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS export_jobs (
                job_id TEXT PRIMARY KEY,
                format TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                requester TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                options TEXT DEFAULT '{}',
                output_path TEXT DEFAULT '',
                created_at REAL NOT NULL,
                completed_at REAL DEFAULT 0,
                error TEXT DEFAULT ''
            )
            """
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_export_requester ON export_jobs(requester)"
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_export_status ON export_jobs(status)")
        self._db.commit()

    def save(self, job: ExportJob) -> None:
        import json

        self._db.execute(
            "INSERT OR REPLACE INTO export_jobs (job_id, format, target_type, target_id, requester, status, options, output_path, created_at, completed_at, error)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job.job_id,
                job.format,
                job.target_type,
                job.target_id,
                job.requester,
                job.status,
                json.dumps(job.options or {}),
                job.output_path,
                job.created_at,
                job.completed_at,
                job.error,
            ),
        )
        self._db.commit()

    def get(self, job_id: str) -> ExportJob | None:
        import json

        row = self._db.execute("SELECT * FROM export_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return ExportJob(
            job_id=row["job_id"],
            format=row["format"],
            target_type=row["target_type"],
            target_id=row["target_id"],
            requester=row["requester"],
            status=row["status"],
            options=json.loads(row["options"]),
            output_path=row["output_path"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            error=row["error"],
        )

    def list_for_user(self, requester: str, limit: int = 20) -> list[ExportJob]:
        import json

        rows = self._db.execute(
            "SELECT * FROM export_jobs WHERE requester = ? ORDER BY created_at DESC LIMIT ?",
            (requester, limit),
        ).fetchall()
        return [
            ExportJob(
                job_id=r["job_id"],
                format=r["format"],
                target_type=r["target_type"],
                target_id=r["target_id"],
                requester=r["requester"],
                status=r["status"],
                options=json.loads(r["options"]),
                output_path=r["output_path"],
                created_at=r["created_at"],
                completed_at=r["completed_at"],
                error=r["error"],
            )
            for r in rows
        ]
