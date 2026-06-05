"""The ``Version`` entity for the versioning context."""

from __future__ import annotations

__all__ = ["Version"]

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Version:
    """An immutable snapshot of a node's payload at a point in time."""

    version_id: int
    node_id: str
    version_no: int
    status: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    created_by: str = ""
    note: str = ""

    def as_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "version_id": self.version_id,
            "node_id": self.node_id,
            "version_no": self.version_no,
            "status": self.status,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "note": self.note,
        }
        if include_payload:
            data["payload"] = dict(self.payload)
        return data
