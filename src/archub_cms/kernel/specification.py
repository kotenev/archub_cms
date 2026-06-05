"""Specification pattern for composable, reusable query/domain predicates."""

from __future__ import annotations

__all__ = ["AndSpecification", "NotSpecification", "OrSpecification", "Specification"]

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class Specification(ABC, Generic[T]):
    """A boolean predicate over a candidate that composes with &, | and ~."""

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool: ...

    def __and__(self, other: Specification[T]) -> Specification[T]:
        return AndSpecification(self, other)

    def __or__(self, other: Specification[T]) -> Specification[T]:
        return OrSpecification(self, other)

    def __invert__(self) -> Specification[T]:
        return NotSpecification(self)


class _Predicate(Specification[T]):
    def __init__(self, predicate: Callable[[T], bool]) -> None:
        self._predicate = predicate

    def is_satisfied_by(self, candidate: T) -> bool:
        return bool(self._predicate(candidate))


def spec(predicate: Callable[[T], bool]) -> Specification[T]:
    """Wrap a plain predicate function as a Specification."""
    return _Predicate(predicate)


class AndSpecification(Specification[T]):
    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)


class OrSpecification(Specification[T]):
    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)


class NotSpecification(Specification[T]):
    def __init__(self, inner: Specification[T]) -> None:
        self._inner = inner

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self._inner.is_satisfied_by(candidate)
