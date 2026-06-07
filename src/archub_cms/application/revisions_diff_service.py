"""Revisions diff service: compare content revisions."""

from __future__ import annotations

__all__ = ["RevisionsDiffService", "get_archub_revisions_diff_service"]


from archub_cms.domain.revisions_diff.models import (
    DiffBlock,
    DiffLine,
    DiffType,
    RevisionComparison,
)


class RevisionsDiffService:
    def __init__(self) -> None:
        pass

    def compare(
        self, node_id: str, old_content: str, new_content: str, old_rev: int, new_rev: int
    ) -> RevisionComparison:
        old_lines = old_content.split("\n") if old_content else []
        new_lines = new_content.split("\n") if new_content else []
        blocks = self._compute_blocks(old_lines, new_lines)
        summary = {"added": 0, "removed": 0, "unchanged": 0}
        for block in blocks:
            for line in block.lines:
                if line.diff_type == DiffType.ADDED:
                    summary["added"] += 1
                elif line.diff_type == DiffType.REMOVED:
                    summary["removed"] += 1
                else:
                    summary["unchanged"] += 1
        return RevisionComparison(
            node_id=node_id,
            old_revision=old_rev,
            new_revision=new_rev,
            blocks=blocks,
            summary=summary,
        )

    def _compute_blocks(self, old_lines: list[str], new_lines: list[str]) -> tuple[DiffBlock, ...]:
        blocks: list[DiffBlock] = []
        max_len = max(len(old_lines), len(new_lines))
        diff_lines: list[DiffLine] = []
        for i in range(max_len):
            old = old_lines[i] if i < len(old_lines) else ""
            new = new_lines[i] if i < len(new_lines) else ""
            if old == "" and new != "":
                diff_lines.append(DiffLine(0, i + 1, new, DiffType.ADDED))
            elif new == "" and old != "":
                diff_lines.append(DiffLine(i + 1, 0, old, DiffType.REMOVED))
            elif old == new:
                diff_lines.append(DiffLine(i + 1, i + 1, old, DiffType.UNCHANGED))
            else:
                diff_lines.append(DiffLine(i + 1, 0, old, DiffType.REMOVED))
                diff_lines.append(DiffLine(0, i + 1, new, DiffType.ADDED))
        if diff_lines:
            blocks.append(DiffBlock(1, 1, tuple(diff_lines)))
        return tuple(blocks)

    def get_revision_content(self, node_id: str, revision: int) -> str | None:
        return None


def get_archub_revisions_diff_service() -> RevisionsDiffService:
    return RevisionsDiffService()
