"""Small value objects used by the ArcHub SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequestSpec:
    method: str
    path: str
    query: dict[str, Any] | None = None
    json_body: dict[str, Any] | None = None


@dataclass(frozen=True)
class ArcHubResponse:
    status: int
    headers: dict[str, str]
    data: Any
