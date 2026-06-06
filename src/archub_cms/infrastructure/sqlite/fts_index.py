"""SQLite FTS5 full-text index — proper inverted index + BM25 ranking.

Upgrades search from a Python scan to a real full-text engine (porter stemming,
prefix matching, BM25 relevance, highlighted snippets) — the Wiki.js/Confluence
approach. Degrades gracefully if the SQLite build lacks FTS5 (``available`` is
then ``False`` and callers fall back to the lexical/federated search).
"""

from __future__ import annotations

__all__ = ["FtsIndex", "FtsHit"]

import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from archub_cms.infrastructure.db.database import Database

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_TABLE = "archub_fts"


@dataclass(frozen=True)
class FtsHit:
    route_path: str
    title: str
    score: float
    snippet: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_path": self.route_path,
            "title": self.title,
            "score": round(self.score, 4),
            "snippet": self.snippet,
        }


def _match_expression(query: str) -> str:
    # Tokens are alphanumeric only, so they are safe to embed directly; prefix
    # match each and OR them for recall.
    tokens = _TOKEN_RE.findall(query or "")
    return " OR ".join(f"{token}*" for token in tokens)


class FtsIndex:
    def __init__(self, database: Database) -> None:
        self._db = database
        self._available = self._init_table()

    @property
    def available(self) -> bool:
        return self._available

    def _init_table(self) -> bool:
        conn = self._db.connect()
        try:
            conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {_TABLE} USING fts5(
                    route_path UNINDEXED, title, body, tags,
                    tokenize='porter unicode61'
                )
                """
            )
            conn.commit()
            return True
        except sqlite3.OperationalError:
            return False
        finally:
            conn.close()

    def count(self) -> int:
        if not self._available:
            return 0
        conn = self._db.connect()
        try:
            row = conn.execute(f"SELECT count(*) AS n FROM {_TABLE}").fetchone()
            return int(row["n"]) if row is not None else 0
        finally:
            conn.close()

    def rebuild(self, documents: list[dict[str, Any]]) -> int:
        if not self._available:
            return 0
        conn = self._db.connect()
        try:
            conn.execute(f"DELETE FROM {_TABLE}")
            conn.executemany(
                f"INSERT INTO {_TABLE} (route_path, title, body, tags) VALUES (?, ?, ?, ?)",
                [
                    (
                        str(doc.get("route_path") or ""),
                        str(doc.get("title") or ""),
                        str(doc.get("body") or doc.get("summary") or ""),
                        " ".join(str(t) for t in (doc.get("tags") or ())),
                    )
                    for doc in documents
                ],
            )
            conn.commit()
            return self.count()
        finally:
            conn.close()

    def search(self, query: str, *, limit: int = 20) -> list[FtsHit]:
        expression = _match_expression(query)
        if not self._available or not expression:
            return []
        conn = self._db.connect()
        try:
            rows = conn.execute(
                f"""
                SELECT route_path, title,
                       -bm25({_TABLE}) AS score,
                       snippet({_TABLE}, 2, '[', ']', '…', 12) AS snippet
                FROM {_TABLE}
                WHERE {_TABLE} MATCH ?
                ORDER BY bm25({_TABLE})
                LIMIT ?
                """,
                (expression, max(1, limit)),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()
        return [
            FtsHit(
                route_path=str(row["route_path"]),
                title=str(row["title"]),
                score=float(row["score"] or 0.0),
                snippet=str(row["snippet"] or ""),
            )
            for row in rows
        ]
