"""Shared value objects: Identity, Timestamp, Pagination, Page.

Framework-agnostic value types reused across bounded contexts so every
context speaks the same language for IDs, time, and result pagination.
"""

from __future__ import annotations

__all__ = [
    "Identity",
    "Page",
    "Pagination",
    "Timestamp",
]

import time as _time
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Identity:
    """Type-safe aggregate identifier (string wrapper)."""

    value: str

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Identity({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Identity):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def generate(cls, prefix: str = "") -> Identity:
        import secrets

        return cls(f"{prefix}{secrets.token_urlsafe(10)}")


@dataclass(frozen=True, slots=True)
class Timestamp:
    """Immutable UTC epoch-seconds timestamp with convenience factories."""

    epoch: float

    def __float__(self) -> float:
        return self.epoch

    def __str__(self) -> str:
        return f"{self.epoch:.6f}"

    @classmethod
    def now(cls) -> Timestamp:
        return cls(_time.time())

    @classmethod
    def from_epoch(cls, value: float) -> Timestamp:
        return cls(value)

    @property
    def is_zero(self) -> bool:
        return self.epoch == 0.0

    def as_dict(self) -> dict[str, Any]:
        return {"epoch": self.epoch}


@dataclass(frozen=True, slots=True)
class Pagination:
    """Cursor-free page descriptor (offset + limit)."""

    offset: int = 0
    limit: int = 20

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise ValueError("offset must be >= 0")
        if self.limit < 1:
            raise ValueError("limit must be >= 1")

    @classmethod
    def first(cls, *, limit: int = 20) -> Pagination:
        return cls(offset=0, limit=limit)

    def next_page(self) -> Pagination:
        return Pagination(offset=self.offset + self.limit, limit=self.limit)

    def as_dict(self) -> dict[str, Any]:
        return {"offset": self.offset, "limit": self.limit}


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """A single page of results from a paginated query."""

    items: tuple[T, ...]
    total: int
    pagination: Pagination

    @property
    def has_next(self) -> bool:
        return self.pagination.offset + len(self.items) < self.total

    @property
    def page_number(self) -> int:
        return (self.pagination.offset // self.pagination.limit) + 1

    @property
    def total_pages(self) -> int:
        if self.pagination.limit <= 0:
            return 1
        import math

        return max(1, math.ceil(self.total / self.pagination.limit))

    def as_dict(self, *, item_serializer: Any = None) -> dict[str, Any]:
        serialize = item_serializer or (lambda x: x)
        return {
            "items": [serialize(item) for item in self.items],
            "total": self.total,
            "offset": self.pagination.offset,
            "limit": self.pagination.limit,
            "has_next": self.has_next,
            "page": self.page_number,
            "total_pages": self.total_pages,
        }
