"""Tests for the Circuit Breaker + resilient LLM provider (Phase 24)."""

from __future__ import annotations

from archub_cms.application.resilient_llm import ResilientLLMProvider
from archub_cms.kernel.circuit_breaker import CircuitBreaker, CircuitState
from archub_cms.ports import LLMRequest, LLMResponse


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# --- circuit breaker mechanics -------------------------------------------


def test_breaker_opens_after_threshold_and_short_circuits():
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=2, reset_timeout=10.0, clock=clock)
    assert cb.state is CircuitState.CLOSED and cb.allow()

    cb.record_failure()
    assert cb.state is CircuitState.CLOSED  # 1 < 2
    cb.record_failure()
    assert cb.state is CircuitState.OPEN and not cb.allow()


def test_breaker_half_opens_then_recovers():
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=10.0, clock=clock)
    cb.record_failure()
    assert cb.state is CircuitState.OPEN

    clock.advance(10.0)
    assert cb.state is CircuitState.HALF_OPEN and cb.allow()

    cb.record_success()
    assert cb.state is CircuitState.CLOSED and cb.failure_count == 0


def test_breaker_run_routes_to_fallback_on_failure_and_when_open():
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=10.0, clock=clock)
    calls = {"primary": 0, "fallback": 0}

    def primary_ok() -> str:
        calls["primary"] += 1
        return "primary"

    def primary_boom() -> str:
        calls["primary"] += 1
        raise RuntimeError("down")

    def fallback() -> str:
        calls["fallback"] += 1
        return "fallback"

    assert cb.run(primary_ok, fallback) == "primary"  # healthy
    assert cb.run(primary_boom, fallback) == "fallback"  # fails → opens
    primary_calls = calls["primary"]
    assert cb.run(primary_ok, fallback) == "fallback"  # open → short-circuits
    assert calls["primary"] == primary_calls  # primary NOT called while open


# --- resilient LLM provider ----------------------------------------------


class _Primary:
    provider_name = "online"
    mode = "online"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.fail:
            raise RuntimeError("api down")
        return LLMResponse(text="online answer", provider="online", mode="online")


class _Fallback:
    provider_name = "offline-extractive"
    mode = "offline"

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text="offline answer", provider="offline-extractive", mode="offline")


def test_resilient_provider_degrades_and_recovers():
    clock = _Clock()
    primary = _Primary()
    provider = ResilientLLMProvider(
        primary=primary,
        fallback=_Fallback(),
        breaker=CircuitBreaker(failure_threshold=2, reset_timeout=10.0, clock=clock),
    )
    req = LLMRequest(prompt="q")

    # healthy → online
    online = provider.complete(req)
    assert online.text == "online answer" and online.mode == "online"
    assert provider.circuit_state == "closed"

    # primary fails → degraded offline, annotated
    primary.fail = True
    deg = provider.complete(req)
    assert deg.text == "offline answer" and deg.metadata["degraded"] is True
    deg2 = provider.complete(req)  # second failure opens the breaker
    assert deg2.metadata["circuit"] in {"open", "closed"}
    assert provider.circuit_state == "open"

    # while open, primary is not even called
    before = primary.calls
    provider.complete(req)
    assert primary.calls == before

    # after cooldown the breaker half-opens; healthy primary closes it
    clock.advance(10.0)
    primary.fail = False
    recovered = provider.complete(req)
    assert recovered.text == "online answer"
    assert provider.circuit_state == "closed"


def test_provider_exposes_primary_identity():
    provider = ResilientLLMProvider(primary=_Primary(), fallback=_Fallback())
    assert provider.provider_name == "online"
    assert provider.mode == "online"


# --- wiring: online settings produce a resilient provider ----------------


def test_online_settings_wrap_in_resilient_provider():
    from archub_cms.application.knowledge import _llm_provider_from_settings
    from archub_cms.settings import ArcHubSettings

    online = ArcHubSettings(llm_provider="openai-compatible", llm_base_url="https://api.example/v1")
    assert isinstance(_llm_provider_from_settings(online), ResilientLLMProvider)

    offline = ArcHubSettings(llm_provider="offline-extractive")
    assert not isinstance(_llm_provider_from_settings(offline), ResilientLLMProvider)
