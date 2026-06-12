"""Resilient LLM provider — online with graceful offline fallback.

Wraps a primary (online) :class:`LLMProviderPort` and a fallback (offline)
provider behind a :class:`CircuitBreaker`. While the online endpoint is healthy,
requests go online; after repeated failures the breaker opens and requests
short-circuit straight to the offline provider for a cooldown, then half-open to
probe recovery. Fallback responses are annotated ``degraded=True`` so callers
can see the system ran offline.
"""

from __future__ import annotations

__all__ = ["ResilientLLMProvider"]

from archub_cms.kernel.circuit_breaker import CircuitBreaker
from archub_cms.ports import LLMProviderPort, LLMRequest, LLMResponse


class ResilientLLMProvider:
    """An LLM provider that degrades from online to offline via a circuit breaker."""

    def __init__(
        self,
        *,
        primary: LLMProviderPort,
        fallback: LLMProviderPort,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._breaker = breaker or CircuitBreaker()
        self.provider_name = getattr(primary, "provider_name", "resilient")
        self.mode = getattr(primary, "mode", "online")

    @property
    def circuit_state(self) -> str:
        return self._breaker.state.value

    def complete(self, request: LLMRequest) -> LLMResponse:
        return self._breaker.run(
            lambda: self._primary.complete(request),
            lambda: self._degraded(request),
        )

    def _degraded(self, request: LLMRequest) -> LLMResponse:
        response = self._fallback.complete(request)
        return LLMResponse(
            text=response.text,
            provider=response.provider,
            model=response.model,
            mode=response.mode,
            metadata={
                **dict(response.metadata),
                "degraded": True,
                "circuit": self._breaker.state.value,
                "primary": self._primary.provider_name,
            },
        )
