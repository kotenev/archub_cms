"""Standalone RAG corpus registry used by ArcHub runtime exports."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "RagCorpusSpec",
    "get_rag_corpus_spec",
    "iter_rag_corpus_specs",
    "rebuild_corpus_index",
    "register_rag_corpus",
]


@dataclass(frozen=True)
class RagCorpusSpec:
    key: str
    title: str
    corpus_dirs: tuple[Path, ...] = ()
    default_index_dir: Path = Path("data/rag_indexes/default")


_CORPORA: dict[str, RagCorpusSpec] = {}


def register_rag_corpus(spec: RagCorpusSpec) -> None:
    key = spec.key.strip()
    if not key:
        raise ValueError("RAG corpus key is required")
    _CORPORA[key] = spec


def iter_rag_corpus_specs() -> tuple[RagCorpusSpec, ...]:
    if not _CORPORA:
        register_rag_corpus(
            RagCorpusSpec(
                key="demo",
                title="Demo knowledge corpus",
                corpus_dirs=(Path("demo_content/rag/demo"),),
                default_index_dir=Path("data/rag_indexes/demo"),
            )
        )
    return tuple(sorted(_CORPORA.values(), key=lambda item: item.key))


def get_rag_corpus_spec(key: str | None) -> RagCorpusSpec | None:
    clean = str(key or "").strip()
    if not clean:
        return None
    for spec in iter_rag_corpus_specs():
        if spec.key == clean:
            return spec
    return None


def rebuild_corpus_index(
    *,
    corpus_dirs: Iterable[Path],
    index_dir: Path,
    model: str,
) -> str:
    """Default external-indexer hook for standalone ArcHub releases."""
    material_count = 0
    for corpus_dir in corpus_dirs:
        if corpus_dir.exists():
            material_count += sum(1 for _ in corpus_dir.rglob("*.md"))
    index_dir.parent.mkdir(parents=True, exist_ok=True)
    return f"skipped:external-indexer-required:{material_count}:materials:{model}"
