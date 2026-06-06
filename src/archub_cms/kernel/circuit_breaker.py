"""A small Circuit Breaker for guarding flaky external calls (online LLM, HTTP).

Closed → calls flow through. After ``failure_threshold`` consecutive failures the
breaker Opens and short-circuits to the fallback for ``reset_timeout`` seconds,
then Half-opens to let one trial through: success closes it, failure re-opens it.
The clock is injectable for deterministic tests.
"""

from __future__ import annotations

__all__ = ["CircuitBreaker", "CircuitState"]

import time
from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        reset_timeout: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = max(1, failure_threshold)
        self._reset_timeout = reset_timeout
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if self._opened_at is None:
            return CircuitState.CLOSED
        if self._clock() - self._opened_at >= self._reset_timeout:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    @property
    def failure_count(self) -> int:
        return self._failures

    def allow(self) -> bool:
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = self._clock()

    def run(self, primary: Callable[[], T], fallback: Callable[[], T]) -> T:
        """Call ``primary`` if the circuit allows; otherwise/on failure ``fallback``."""
        if not self.allow():
            return fallback()
        try:
            result = primary()
        except Exception:  # any primary failure trips toward open
            self.record_failure()
            return fallback()
        self.record_success()
        return result
