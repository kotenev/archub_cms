"""A small typed ``Result`` for explicit, non-exceptional error handling.

Domain validation (e.g. publish guards, slug rules) returns ``Result`` so
callers branch on outcomes instead of catching broad exceptions.
"""

from __future__ import annotations

__all__ = ["Err", "Ok", "Result"]

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

    @property
    def ok(self) -> bool:
        return True

    def unwrap(self) -> T:
        return self.value


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E
    details: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return False

    def unwrap(self) -> object:
        raise ValueError(f"called unwrap on Err: {self.error}")


Result = Ok[T] | Err[E]
