"""Retry policy: configurable retry logic with exponential backoff for
resilient integration calls (LLM providers, search indexers, webhooks).

Works in concert with the CircuitBreaker for online LLM resilience.
"""

from __future__ import annotations

__all__ = ["RetryPolicy", "RetryResult"]

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetryResult:
    """Outcome of a retry-wrapped operation."""

    success: bool
    attempts: int
    total_delay: float
    last_error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "attempts": self.attempts,
            "total_delay": self.total_delay,
            "last_error": self.last_error,
        }


class RetryPolicy:
    """Configurable retry with exponential backoff and jitter."""

    def __init__(
        self,
        *,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def execute(self, operation: Callable[[], Any]) -> RetryResult:
        last_error = ""
        total_delay = 0.0
        for attempt in range(1, self.max_retries + 1):
            try:
                operation()
                return RetryResult(success=True, attempts=attempt, total_delay=total_delay)
            except Exception as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (self.exponential_base ** (attempt - 1)),
                        self.max_delay,
                    )
                    total_delay += delay
                    time.sleep(delay)
        return RetryResult(
            success=False, attempts=self.max_retries, total_delay=total_delay, last_error=last_error
        )

    def compute_delay(self, attempt: int) -> float:
        return min(self.base_delay * (self.exponential_base ** (attempt - 1)), self.max_delay)
