"""SQLite adapter for the subscriptions repository port."""

from __future__ import annotations

__all__ = ["SqliteSubscriptionRepository"]

import sqlite3

from archub_cms.domain.subscriptions.subscription import Subscription
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.db.schema import apply_extension_migrations


def _row(row: sqlite3.Row) -> Subscription:
    return Subscription(
        subscription_id=str(row["subscription_id"]),
        subscriber=str(row["subscriber"]),
        node_id=str(row["node_id"] or ""),
        event_prefix=str(row["event_prefix"] or ""),
        created_at=float(row["created_at"] or 0.0),
    )


class SqliteSubscriptionRepository:
    def __init__(self, database: Database) -> None:
        self._db = database
        conn = self._db.connect()
        try:
            apply_extension_migrations(conn)
        finally:
            conn.close()

    def add(self, subscription: Subscription) -> None:
        conn = self._db.connect()
        try:
            conn.execute(
                """
                INSERT INTO archub_subscriptions (
                    subscription_id, subscriber, node_id, event_prefix, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(subscription_id) DO NOTHING
                """,
                (
                    subscription.subscription_id,
                    subscription.subscriber,
                    subscription.node_id,
                    subscription.event_prefix,
                    subscription.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def remove(self, subscription_id: str) -> bool:
        conn = self._db.connect()
        try:
            cursor = conn.execute(
                "DELETE FROM archub_subscriptions WHERE subscription_id = ?", (subscription_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def for_subscriber(self, subscriber: str) -> list[Subscription]:
        conn = self._db.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM archub_subscriptions WHERE subscriber = ? ORDER BY created_at DESC",
                (subscriber,),
            ).fetchall()
            return [_row(r) for r in rows]
        finally:
            conn.close()

    def watchers_of(self, node_id: str) -> list[Subscription]:
        conn = self._db.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM archub_subscriptions WHERE node_id = ? ORDER BY subscriber",
                (node_id,),
            ).fetchall()
            return [_row(r) for r in rows]
        finally:
            conn.close()

    def find(self, subscriber: str, node_id: str, event_prefix: str) -> Subscription | None:
        conn = self._db.connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM archub_subscriptions
                WHERE subscriber = ? AND node_id = ? AND event_prefix = ?
                LIMIT 1
                """,
                (subscriber, node_id, event_prefix),
            ).fetchone()
            return _row(row) if row is not None else None
        finally:
            conn.close()
