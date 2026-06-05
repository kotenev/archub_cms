"""Agentic, tool-augmented answering over the knowledge base.

Extends RAG answering with **tool use**: the answer path can invoke registered
``LLMToolExt`` plugins (e.g. ``summarize``) and fold their outputs into the
grounded response. Tools may be selected explicitly or auto-selected when their
name appears in the question. Works offline (the bundled tools fall back to the
extractive provider) and online (real tool calls). This is the seam an
agent/online-LLM uses to act, not just retrieve.
"""

from __future__ import annotations

__all__ = ["AgentService", "get_archub_agent_service"]

from typing import Any

from archub_cms.application.knowledge import (
    ArcHubKnowledgeBaseService,
    get_archub_knowledge_base_service,
)
from archub_cms.extensibility.host import PluginHost, get_plugin_host


class AgentService:
    def __init__(
        self,
        *,
        knowledge: ArcHubKnowledgeBaseService | None = None,
        plugin_host: PluginHost | None = None,
    ) -> None:
        self._host = plugin_host or get_plugin_host()
        self._knowledge = knowledge or get_archub_knowledge_base_service(plugin_host=self._host)

    def available_tools(self) -> list[str]:
        return sorted(self._host.llm_tools)

    def select_tools(
        self, question: str, *, requested: tuple[str, ...] = (), auto: bool = False
    ) -> list[str]:
        tools = self._host.llm_tools
        if requested:
            return [name for name in requested if name in tools]
        if auto:
            lowered = question.casefold()
            return [name for name in sorted(tools) if name.casefold() in lowered]
        return []

    def answer(
        self,
        question: str,
        *,
        tools: tuple[str, ...] = (),
        auto: bool = False,
        space_key: str = "",
        corpus_key: str = "",
        limit: int = 5,
    ) -> dict[str, Any]:
        base = self._knowledge.answer(
            question, space_key=space_key, corpus_key=corpus_key, limit=limit
        )
        # Build a compact tool input from the retrieved source excerpts.
        context_text = "\n\n".join(s.excerpt for s in base.sources[:3] if s.excerpt) or question

        selected = self.select_tools(question, requested=tools, auto=auto)
        tools_used: list[dict[str, Any]] = []
        for name in selected:
            try:
                output = self._host.run_tool(
                    name, {"text": context_text, "title": question, "instruction": question}
                )
            except Exception as exc:  # a tool must not break answering
                tools_used.append({"name": name, "error": str(exc)})
                continue
            tools_used.append({"name": name, "output": output})

        result = base.as_dict()
        result["tools_used"] = tools_used
        result["available_tools"] = self.available_tools()
        if tools_used:
            augmentation = "\n".join(
                f"[{t['name']}] {t.get('output', t.get('error', ''))}" for t in tools_used
            )
            result["augmented_answer"] = f"{base.answer}\n\nTool results:\n{augmentation}"
        return result


def get_archub_agent_service(
    *,
    knowledge: ArcHubKnowledgeBaseService | None = None,
    plugin_host: PluginHost | None = None,
) -> AgentService:
    return AgentService(knowledge=knowledge, plugin_host=plugin_host)
