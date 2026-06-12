"""The ``Redirect`` aggregate for the delivery context."""

from __future__ import annotations

__all__ = ["Redirect", "normalize_path"]

from dataclasses import dataclass
from typing import Any

_PERMANENT_CODES = (301, 308)
_VALID_CODES = (301, 302, 307, 308)
_PUBLIC_ROOT = "/cms"


def normalize_path(path: str) -> str:
    """Normalize a public path the way the delivery surface compares them."""
    clean = "/" + (path or "").strip().strip("/")
    return clean.rstrip("/") or _PUBLIC_ROOT


@dataclass
class Redirect:
    """A source→target redirect rule with a matching predicate."""

    redirect_id: str
    source_path: str
    target_path: str
    status_code: int = 301
    active: bool = True
    note: str = ""

    @property
    def is_permanent(self) -> bool:
        return self.status_code in _PERMANENT_CODES

    def matches(self, path: str) -> bool:
        return self.active and normalize_path(path) == normalize_path(self.source_path)

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.source_path.strip():
            errors.append("redirect source is required")
        if not self.target_path.strip():
            errors.append("redirect target is required")
        if normalize_path(self.source_path) == normalize_path(self.target_path):
            errors.append("redirect source and target must differ")
        if self.status_code not in _VALID_CODES:
            errors.append(f"status code must be one of {_VALID_CODES}")
        return tuple(errors)

    @property
    def valid(self) -> bool:
        return not self.validate()

    def as_dict(self) -> dict[str, Any]:
        return {
            "redirect_id": self.redirect_id,
            "source_path": normalize_path(self.source_path),
            "target_path": self.target_path,
            "status_code": self.status_code,
            "is_permanent": self.is_permanent,
            "active": self.active,
            "note": self.note,
        }
