"""SQLite repository for the notification hub bounded context."""

from __future__ import annotations

__all__ = ["SqliteNotificationRepository"]

import json
import sqlite3

from archub_cms.domain.notifications.notification import Notification, NotificationPreference
from archub_cms.domain.notifications.repository import NotificationRepository
from archub_cms.infrastructure.db.database import Database


class SqliteNotificationRepository(NotificationRepository):
    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        with self._db.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archub_notifications (
                    notification_id TEXT PRIMARY KEY,
                    recipient       TEXT NOT NULL,
                    title           TEXT NOT NULL DEFAULT '',
                    body            TEXT NOT NULL DEFAULT '',
                    channel         TEXT NOT NULL DEFAULT 'in_app',
                    event_type      TEXT NOT NULL DEFAULT '',
                    aggregate_id    TEXT NOT NULL DEFAULT '',
                    read            INTEGER NOT NULL DEFAULT 0,
                    created_at      REAL NOT NULL DEFAULT 0,
                    metadata        TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notif_recipient ON archub_notifications(recipient)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archub_notification_preferences (
                    username   TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    channels   TEXT NOT NULL DEFAULT '["in_app"]',
                    enabled    INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (username, event_type)
                )
                """
            )
            conn.commit()

    def store(self, notification: Notification) -> Notification:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO archub_notifications
                (notification_id, recipient, title, body, channel, event_type,
                 aggregate_id, read, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notification.notification_id,
                    notification.recipient,
                    notification.title,
                    notification.body,
                    notification.channel,
                    notification.event_type,
                    notification.aggregate_id,
                    int(notification.read),
                    notification.created_at,
                    json.dumps(notification.metadata),
                ),
            )
            conn.commit()
        return notification

    def mark_read(self, notification_id: str) -> bool:
        with self._db.connect() as conn:
            cursor = conn.execute(
                "UPDATE archub_notifications SET read = 1 WHERE notification_id = ?",
                (notification_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def inbox(
        self, username: str, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        where = "recipient = ?"
        params: list[object] = [username]
        if unread_only:
            where += " AND read = 0"
        sql = f"SELECT * FROM archub_notifications WHERE {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_notification(row) for row in rows]

    def preferences(self, username: str) -> list[NotificationPreference]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM archub_notification_preferences WHERE username = ?",
                (username,),
            ).fetchall()
        return [self._row_to_preference(row) for row in rows]

    def set_preference(self, preference: NotificationPreference) -> NotificationPreference:
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO archub_notification_preferences
                (username, event_type, channels, enabled)
                VALUES (?, ?, ?, ?)
                """,
                (
                    preference.username,
                    preference.event_type,
                    json.dumps(list(preference.channels)),
                    int(preference.enabled),
                ),
            )
            conn.commit()
        return preference

    @staticmethod
    def _row_to_notification(row: sqlite3.Row) -> Notification:
        return Notification(
            notification_id=row["notification_id"],
            recipient=row["recipient"],
            title=row["title"],
            body=row["body"],
            channel=row["channel"],
            event_type=row["event_type"],
            aggregate_id=row["aggregate_id"],
            read=bool(row["read"]),
            created_at=row["created_at"],
            metadata=json.loads(row["metadata"]),
        )

    @staticmethod
    def _row_to_preference(row: sqlite3.Row) -> NotificationPreference:
        return NotificationPreference(
            username=row["username"],
            event_type=row["event_type"],
            channels=tuple(json.loads(row["channels"])),
            enabled=bool(row["enabled"]),
        )
