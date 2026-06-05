"""Embedding providers for semantic search — offline and online (Strategy).

``HashingEmbedder`` is a zero-dependency, fully-offline embedder: it hashes
tokens into a fixed-dimension bag-of-words vector and L2-normalizes it. It is
deterministic and needs no network or model download, so semantic search works
out of the box. ``OpenAIEmbedder`` calls an OpenAI-compatible ``/embeddings``
endpoint (cloud or a local server such as Ollama) when configured.
"""

from __future__ import annotations

__all__ = [
    "HashingEmbedder",
    "OpenAIEmbedder",
    "cosine_similarity",
    "get_embedder_from_settings",
]

import hashlib
import json
import math
import re
import urllib.error
import urllib.request

from archub_cms.ports import EmbeddingPort
from archub_cms.settings import ArcHubSettings

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokens(text: str) -> list[str]:
    return [t.casefold() for t in _TOKEN_RE.findall(text or "") if len(t) >= 2]


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    return max(-1.0, min(1.0, dot))  # inputs are pre-normalized


class HashingEmbedder:
    """Offline hashing embedder (the hashing-trick / feature-hashing)."""

    def __init__(self, *, dim: int = 256) -> None:
        self.dim = dim
        self.model = f"hashing-{dim}"

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dim
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return tuple(vector)
        return tuple(value / norm for value in vector)


class OpenAIEmbedder:
    """Online embedder for an OpenAI-compatible ``/embeddings`` endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        model: str = "",
        dim: int = 1536,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model or "text-embedding-3-small"
        self.dim = dim
        self._timeout = timeout_seconds

    def embed(self, text: str) -> tuple[float, ...]:
        body = json.dumps({"model": self.model, "input": text}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(
            f"{self._base_url}/embeddings", data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"embedding request failed: {exc}") from exc
        vector = data.get("data", [{}])[0].get("embedding") or []
        values = tuple(float(v) for v in vector)
        norm = math.sqrt(sum(v * v for v in values))
        if norm == 0.0:
            return values
        self.dim = len(values)
        return tuple(v / norm for v in values)


def get_embedder_from_settings(settings: ArcHubSettings | None = None) -> EmbeddingPort:
    """Pick an embedder: online when an OpenAI-compatible base URL is set."""
    source = settings or ArcHubSettings.from_env()
    provider = source.llm_provider.strip().casefold()
    if source.llm_base_url and provider in {
        "openai-compatible",
        "online",
        "ollama",
        "local-openai",
    }:
        return OpenAIEmbedder(
            base_url=source.llm_base_url,
            api_key=source.llm_api_key,
            model=source.llm_embedding_model,
            timeout_seconds=source.llm_timeout_seconds,
        )
    return HashingEmbedder()
