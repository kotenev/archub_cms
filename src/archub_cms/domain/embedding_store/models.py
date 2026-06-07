"""Embedding store domain models."""

from __future__ import annotations

__all__ = ["EmbeddingEntry", "EmbeddingStatus"]

from dataclasses import dataclass
from typing import Any


class EmbeddingStatus:
    PENDING = "pending"
    INDEXED = "indexed"
    STALE = "stale"
    FAILED = "failed"


@dataclass(frozen=True)
class EmbeddingEntry:
    entry_id: str
    route_path: str
    model: str
    dim: int
    status: str = EmbeddingStatus.INDEXED
    content_hash: str = ""
    token_count: int = 0
    indexed_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "route_path": self.route_path,
            "model": self.model,
            "dim": self.dim,
            "status": self.status,
            "content_hash": self.content_hash,
            "token_count": self.token_count,
            "indexed_at": self.indexed_at,
        }
