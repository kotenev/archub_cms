"""SQLite connection factory shared by the legacy service and new repositories.

This centralizes how a connection is opened (row factory, thread setting) so the
god class (``ArcHubCMSService._connect``) and the extracted bounded-context
repositories all talk to the *same* database the same way. New repositories
receive a ``Database`` (or a bound connection from a ``UnitOfWork``) instead of
each re-implementing ``sqlite3.connect``.
"""

from __future__ import annotations

__all__ = ["Database", "connect"]

import sqlite3
from pathlib import Path


def connect(db_path: str) -> sqlite3.Connection:
    """Open a connection configured the way ArcHub expects everywhere.

    Ensures the parent directory exists first: the plugin host opens its config
    store before the legacy service runs its own ``mkdir``, so on a fresh nested
    ``ARCHUB_CMS_DB`` path the connection would otherwise fail to open.
    """
    parent = Path(db_path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class Database:
    """Thin handle around a database path that hands out configured connections."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    @property
    def path(self) -> str:
        return self._db_path

    def connect(self) -> sqlite3.Connection:
        return connect(self._db_path)
