"""Live edit domain models."""

from __future__ import annotations

__all__ = ["EditOperation", "EditSession", "OperationType", "UserPresence"]

from dataclasses import dataclass, field
from typing import Any


class OperationType:
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"


@dataclass(frozen=True)
class EditOperation:
    operation_id: str
    session_id: str
    user: str
    op_type: str
    position: int
    content: str = ""
    length: int = 0
    revision: int = 0
    timestamp: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "session_id": self.session_id,
            "user": self.user,
            "op_type": self.op_type,
            "position": self.position,
            "content": self.content,
            "length": self.length,
            "revision": self.revision,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class UserPresence:
    user: str
    node_id: str
    cursor_position: int = 0
    selection_start: int = 0
    selection_end: int = 0
    color: str = ""
    last_active: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "user": self.user,
            "node_id": self.node_id,
            "cursor_position": self.cursor_position,
            "selection_start": self.selection_start,
            "selection_end": self.selection_end,
            "color": self.color,
            "last_active": self.last_active,
        }


@dataclass
class EditSession:
    session_id: str
    node_id: str
    active_users: dict[str, UserPresence] = field(default_factory=dict)
    current_revision: int = 0
    created_at: float = 0.0

    def join(self, presence: UserPresence) -> None:
        self.active_users[presence.user] = presence

    def leave(self, username: str) -> None:
        self.active_users.pop(username, None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "node_id": self.node_id,
            "active_users": [p.as_dict() for p in self.active_users.values()],
            "current_revision": self.current_revision,
            "created_at": self.created_at,
        }
