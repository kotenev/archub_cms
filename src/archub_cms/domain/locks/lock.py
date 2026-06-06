"""The ``EditLock`` aggregate."""

from __future__ import annotations

__all__ = ["EditLock"]

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EditLock:
    """A time-bounded edit reservation on a content node."""

    node_id: str
    owner: str
    token: str = ""
    note: str = ""
    acquired_at: float = 0.0
    expires_at: float = 0.0
    node_name: str = ""
    route_path: str = ""

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at

    def is_active(self, now: float) -> bool:
        return not self.is_expired(now)

    def held_by(self, owner: str) -> bool:
        return self.owner.strip().casefold() == owner.strip().casefold()

    def remaining_seconds(self, now: float) -> float:
        return max(0.0, self.expires_at - now)

    def blocks(self, owner: str, now: float) -> bool:
        """True if an *active* lock is held by someone other than ``owner``."""
        return self.is_active(now) and not self.held_by(owner)

    def as_dict(self, *, now: float | None = None) -> dict[str, Any]:
        data = {
            "node_id": self.node_id,
            "owner": self.owner,
            "note": self.note,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "node_name": self.node_name,
            "route_path": self.route_path,
        }
        if now is not None:
            data["active"] = self.is_active(now)
            data["remaining_seconds"] = round(self.remaining_seconds(now), 1)
        return data
