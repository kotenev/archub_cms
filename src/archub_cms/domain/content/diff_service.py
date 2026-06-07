"""Domain service: content diff computation for versioning and audit.

Pure domain service that computes field-level diffs between two content
payloads, producing structured change records for audit trail entries
and version comparison views.
"""

from __future__ import annotations

__all__ = ["compute_content_diff", "ContentFieldDiff", "DiffType"]

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DiffType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class ContentFieldDiff:
    """A single field-level change between two content payloads."""

    field: str
    diff_type: DiffType
    old_value: Any = None
    new_value: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "diff_type": self.diff_type.value,
            "old_value": self.old_value,
            "new_value": self.new_value,
        }


def compute_content_diff(
    old_payload: dict[str, Any],
    new_payload: dict[str, Any],
) -> list[ContentFieldDiff]:
    """Compute field-level diffs between two content payloads."""
    diffs: list[ContentFieldDiff] = []
    all_keys = set(old_payload.keys()) | set(new_payload.keys())
    for key in sorted(all_keys):
        old_val = old_payload.get(key)
        new_val = new_payload.get(key)
        if key not in old_payload:
            diffs.append(ContentFieldDiff(key, DiffType.ADDED, new_value=new_val))
        elif key not in new_payload:
            diffs.append(ContentFieldDiff(key, DiffType.REMOVED, old_value=old_val))
        elif old_val != new_val:
            diffs.append(
                ContentFieldDiff(key, DiffType.CHANGED, old_value=old_val, new_value=new_val)
            )
    return diffs
