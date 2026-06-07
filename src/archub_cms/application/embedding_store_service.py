"""Embedding store service: manage vector embeddings for content."""

from __future__ import annotations

__all__ = ["EmbeddingStoreService", "get_archub_embedding_store_service"]

from typing import Any

from archub_cms.domain.embedding_store.models import EmbeddingEntry


class EmbeddingStoreService:
    def __init__(self) -> None:
        pass

    def index_content(
        self, route_path: str, model: str, dim: int, content_hash: str
    ) -> EmbeddingEntry:
        import time

        from archub_cms.kernel.value_objects import Identity

        return EmbeddingEntry(
            entry_id=Identity.generate("emb-").value,
            route_path=route_path,
            model=model,
            dim=dim,
            content_hash=content_hash,
            indexed_at=time.time(),
        )

    def mark_stale(self, route_path: str) -> None:
        pass

    def get_entry(self, route_path: str) -> EmbeddingEntry | None:
        return None

    def list_stale(self, limit: int = 100) -> dict[str, Any]:
        return {"entries": [], "total": 0}

    def stats(self) -> dict[str, Any]:
        return {
            "total_indexed": 0,
            "stale": 0,
            "failed": 0,
            "models": [],
        }


def get_archub_embedding_store_service() -> EmbeddingStoreService:
    return EmbeddingStoreService()
