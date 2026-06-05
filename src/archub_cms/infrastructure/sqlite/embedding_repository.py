"""SQLite-backed vector store implementing the SearchPort.

Embeddings are stored in the ``archub_embeddings`` table (see
``infrastructure.db.schema``). Indexing is content-addressed: a document is only
re-embedded when its text hash changes. Querying loads the candidate vectors for
the active model and ranks by cosine similarity. This is intentionally a simple,
dependency-free brute-force store suitable for embedded/corporate-scale corpora;
a pgvector/FAISS adapter can implement the same port later.
"""

from __future__ import annotations

__all__ = ["SqliteEmbeddingRepository"]

import hashlib
import json
import time

from archub_cms.application.embeddings import cosine_similarity
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.db.schema import apply_extension_migrations
from archub_cms.ports import EmbeddingPort


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SqliteEmbeddingRepository:
    def __init__(self, database: Database, embedder: EmbeddingPort) -> None:
        self._db = database
        self._embedder = embedder
        conn = self._db.connect()
        try:
            apply_extension_migrations(conn)
        finally:
            conn.close()

    def index(self, route_path: str, text: str) -> None:
        content_hash = _content_hash(text)
        conn = self._db.connect()
        try:
            row = conn.execute(
                "SELECT content_hash FROM archub_embeddings WHERE route_path = ? AND model = ?",
                (route_path, self._embedder.model),
            ).fetchone()
            if row is not None and str(row["content_hash"]) == content_hash:
                return  # unchanged — skip re-embedding
            vector = self._embedder.embed(text)
            conn.execute(
                """
                INSERT INTO archub_embeddings (
                    route_path, model, dim, vector_json, content_hash, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(route_path, model) DO UPDATE SET
                    dim = excluded.dim,
                    vector_json = excluded.vector_json,
                    content_hash = excluded.content_hash,
                    updated_at = excluded.updated_at
                """,
                (
                    route_path,
                    self._embedder.model,
                    len(vector),
                    json.dumps(vector),
                    content_hash,
                    time.time(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def query(self, text: str, *, limit: int) -> list[tuple[str, float]]:
        query_vector = self._embedder.embed(text)
        conn = self._db.connect()
        try:
            rows = conn.execute(
                "SELECT route_path, vector_json FROM archub_embeddings WHERE model = ?",
                (self._embedder.model,),
            ).fetchall()
        finally:
            conn.close()
        scored: list[tuple[str, float]] = []
        for row in rows:
            try:
                vector = tuple(float(v) for v in json.loads(row["vector_json"]))
            except (ValueError, TypeError):
                continue
            scored.append((str(row["route_path"]), cosine_similarity(query_vector, vector)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[: max(1, limit)]

    def count(self) -> int:
        conn = self._db.connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM archub_embeddings WHERE model = ?",
                (self._embedder.model,),
            ).fetchone()
            return int(row["n"]) if row is not None else 0
        finally:
            conn.close()
