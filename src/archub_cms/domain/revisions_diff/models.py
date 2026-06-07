"""Revisions diff domain models."""

from __future__ import annotations

__all__ = ["DiffBlock", "DiffLine", "DiffType", "RevisionComparison"]

from dataclasses import dataclass
from typing import Any


class DiffType:
    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


@dataclass(frozen=True)
class DiffLine:
    line_number_old: int
    line_number_new: int
    content: str
    diff_type: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "line_number_old": self.line_number_old,
            "line_number_new": self.line_number_new,
            "content": self.content,
            "diff_type": self.diff_type,
        }


@dataclass(frozen=True)
class DiffBlock:
    start_old: int
    start_new: int
    lines: tuple[DiffLine, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_old": self.start_old,
            "start_new": self.start_new,
            "lines": [line.as_dict() for line in self.lines],
        }


@dataclass(frozen=True)
class RevisionComparison:
    node_id: str
    old_revision: int
    new_revision: int
    blocks: tuple[DiffBlock, ...]
    summary: dict[str, int] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "old_revision": self.old_revision,
            "new_revision": self.new_revision,
            "blocks": [b.as_dict() for b in self.blocks],
            "summary": self.summary or {},
        }
