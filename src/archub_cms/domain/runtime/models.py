"""Read models for the runtime / RAG-export context."""

from __future__ import annotations

__all__ = ["ExportStatus", "RagHit", "RuntimeSnapshot"]

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuntimeSnapshot:
    """Counts of the published content that feeds the AI/RAG runtime."""

    generated_at: float
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> RuntimeSnapshot:
        counts = snapshot.get("counts") if isinstance(snapshot.get("counts"), dict) else {}
        return cls(
            generated_at=float(snapshot.get("generated_at") or 0.0),
            counts={str(k): int(v) for k, v in counts.items()},
        )

    def as_dict(self) -> dict[str, Any]:
        return {"generated_at": self.generated_at, "counts": dict(self.counts), "total": self.total}


@dataclass(frozen=True)
class ExportStatus:
    """State of the on-disk runtime export (snapshot freshness)."""

    export_dir: str
    exists: bool
    generated_at: float | None = None
    counts: dict[str, int] = field(default_factory=dict)
    needs_export: bool = False

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> ExportStatus:
        return cls(
            export_dir=str(result.get("export_dir") or ""),
            exists=bool(result.get("exists")),
            generated_at=result.get("generated_at"),
            counts=dict(result.get("counts") or {}),
            needs_export=bool(result.get("needs_export")),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "export_dir": self.export_dir,
            "exists": self.exists,
            "generated_at": self.generated_at,
            "counts": dict(self.counts),
            "needs_export": self.needs_export,
        }


@dataclass(frozen=True)
class RagHit:
    """A corpus-scoped retrieval result used to ground LLM answers."""

    route_path: str
    title: str
    corpus_key: str = ""
    excerpt: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_path": self.route_path,
            "title": self.title,
            "corpus_key": self.corpus_key,
            "excerpt": self.excerpt,
        }
