"""SQLite repository for the scheduler bounded context."""

from __future__ import annotations

__all__ = ["SqliteScheduledJobRepository"]

import json
import sqlite3
from typing import Any

from archub_cms.domain.scheduler.job import JobStatus, ScheduledJob
from archub_cms.domain.scheduler.repository import ScheduledJobRepository
from archub_cms.infrastructure.db.database import Database


class SqliteScheduledJobRepository(ScheduledJobRepository):
    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._db.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archub_scheduled_jobs (
                    job_id          TEXT PRIMARY KEY,
                    name            TEXT NOT NULL DEFAULT '',
                    action          TEXT NOT NULL,
                    cron_expression TEXT NOT NULL DEFAULT '',
                    next_run_at     REAL NOT NULL DEFAULT 0,
                    status          TEXT NOT NULL DEFAULT 'active',
                    payload         TEXT NOT NULL DEFAULT '{}',
                    last_run_at     REAL NOT NULL DEFAULT 0,
                    last_result     TEXT NOT NULL DEFAULT '',
                    run_count       INTEGER NOT NULL DEFAULT 0,
                    failure_count   INTEGER NOT NULL DEFAULT 0,
                    created_by      TEXT NOT NULL DEFAULT '',
                    tags            TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.commit()

    def get(self, job_id: str) -> ScheduledJob | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM archub_scheduled_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._row_to_job(row) if row else None

    def list_active(self) -> list[ScheduledJob]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM archub_scheduled_jobs WHERE status = 'active' ORDER BY next_run_at"
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def list_all(self) -> list[ScheduledJob]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM archub_scheduled_jobs ORDER BY name").fetchall()
        return [self._row_to_job(row) for row in rows]

    def upsert(self, job: ScheduledJob) -> ScheduledJob:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO archub_scheduled_jobs
                (job_id, name, action, cron_expression, next_run_at, status,
                 payload, last_run_at, last_result, run_count, failure_count,
                 created_by, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._job_to_row(job),
            )
            conn.commit()
        return job

    def delete(self, job_id: str) -> bool:
        with self._db.connect() as conn:
            cursor = conn.execute("DELETE FROM archub_scheduled_jobs WHERE job_id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> ScheduledJob:
        return ScheduledJob(
            job_id=row["job_id"],
            name=row["name"],
            action=row["action"],
            cron_expression=row["cron_expression"],
            next_run_at=row["next_run_at"],
            status=JobStatus(row["status"]),
            payload=json.loads(row["payload"]),
            last_run_at=row["last_run_at"],
            last_result=row["last_result"],
            run_count=row["run_count"],
            failure_count=row["failure_count"],
            created_by=row["created_by"],
            tags=tuple(json.loads(row["tags"])),
        )

    @staticmethod
    def _job_to_row(job: ScheduledJob) -> tuple[Any, ...]:
        return (
            job.job_id,
            job.name,
            job.action,
            job.cron_expression,
            job.next_run_at,
            job.status.value,
            json.dumps(job.payload),
            job.last_run_at,
            job.last_result,
            job.run_count,
            job.failure_count,
            job.created_by,
            json.dumps(list(job.tags)),
        )
