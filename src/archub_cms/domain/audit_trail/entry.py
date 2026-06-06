"""AuditEntry: immutable audit log record."""

from __future__ import annotations

__all__ = ["AuditEntry", "AuditQuery"]

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuditEntry:
    """A single immutable audit record capturing a domain action."""

    entry_id: str
    action: str
    aggregate_id: str
    aggregate_type: str
    actor: str
    timestamp: float
    diff: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "action": self.action,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "diff": dict(self.diff),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AuditQuery:
    """Parameters for querying the audit trail."""

    aggregate_id: str = ""
    actor: str = ""
    action: str = ""
    aggregate_type: str = ""
    from_timestamp: float = 0.0
    to_timestamp: float = 0.0
    limit: int = 50
    offset: int = 0

    def matches(self, entry: AuditEntry) -> bool:
        if self.aggregate_id and entry.aggregate_id != self.aggregate_id:
            return False
        if self.actor and entry.actor != self.actor:
            return False
        if self.action and entry.action != self.action:
            return False
        if self.aggregate_type and entry.aggregate_type != self.aggregate_type:
            return False
        if self.from_timestamp and entry.timestamp < self.from_timestamp:
            return False
        return not (self.to_timestamp and entry.timestamp > self.to_timestamp)
