"""Example plugin: a 'summarize' LLM tool (offline + online).

Implements :class:`LLMToolExt`. ``run({"text": ...})`` summarizes the supplied
text through the configured LLM provider — the offline extractive provider when
no endpoint is set, or the OpenAI-compatible provider when ``ARCHUB_LLM_*`` is
configured. Reuses the provider-selection logic from the knowledge service.
"""

from __future__ import annotations

__all__ = ["SummarizeToolPlugin"]

from typing import Any

from archub_cms.ports import LLMRequest


class SummarizeToolPlugin:
    name = "summarize"

    def __init__(self) -> None:
        # Lazy import keeps plugin load cheap and avoids import-time cycles.
        from archub_cms.application.knowledge import _llm_provider_from_settings
        from archub_cms.settings import ArcHubSettings

        self._settings = ArcHubSettings.from_env()
        self._provider = _llm_provider_from_settings(self._settings)

    def run(self, arguments: dict[str, Any]) -> str:
        text = str(arguments.get("text") or "").strip()
        if not text:
            return ""
        request = LLMRequest(
            prompt=str(arguments.get("instruction") or "Summarize the key points."),
            system_prompt="You summarize knowledge-base content faithfully and concisely.",
            context=({"title": str(arguments.get("title") or "input"), "excerpt": text},),
            model=self._settings.llm_model,
            metadata={"tool": self.name},
        )
        return self._provider.complete(request).text
