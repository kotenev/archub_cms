"""Field-level diff between two content versions."""

from __future__ import annotations

__all__ = ["ChangeType", "FieldChange", "VersionDiff"]

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from archub_cms.domain.versioning.version import Version


class ChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


@dataclass(frozen=True)
class FieldChange:
    field: str
    change: ChangeType
    before: Any = None
    after: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "change": self.change.value,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class VersionDiff:
    """The set of field changes turning ``from_version`` into ``to_version``."""

    node_id: str
    from_version_no: int
    to_version_no: int
    changes: tuple[FieldChange, ...] = ()

    @classmethod
    def between(cls, from_version: Version, to_version: Version) -> VersionDiff:
        before = from_version.payload or {}
        after = to_version.payload or {}
        changes: list[FieldChange] = []
        for key in sorted(set(before) | set(after)):
            in_before = key in before
            in_after = key in after
            if in_before and not in_after:
                changes.append(FieldChange(key, ChangeType.REMOVED, before=before[key]))
            elif in_after and not in_before:
                changes.append(FieldChange(key, ChangeType.ADDED, after=after[key]))
            elif before[key] != after[key]:
                changes.append(
                    FieldChange(key, ChangeType.CHANGED, before=before[key], after=after[key])
                )
        return cls(
            node_id=to_version.node_id,
            from_version_no=from_version.version_no,
            to_version_no=to_version.version_no,
            changes=tuple(changes),
        )

    @property
    def is_empty(self) -> bool:
        return not self.changes

    def summary(self) -> dict[str, int]:
        counts = {change_type.value: 0 for change_type in ChangeType}
        for change in self.changes:
            counts[change.change.value] += 1
        return counts

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "from_version_no": self.from_version_no,
            "to_version_no": self.to_version_no,
            "changes": [change.as_dict() for change in self.changes],
            "summary": self.summary(),
            "is_empty": self.is_empty,
        }
