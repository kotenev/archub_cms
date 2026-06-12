"""Example AI chat handler: simple extractive QA."""

from __future__ import annotations

from archub_cms.extensibility.extension_points import ChatHandlerExt


class ExtractiveChatHandler(ChatHandlerExt):
    handler_id = "extractive"

    def respond(self, conversation_id: str, message: str, context: dict) -> dict:
        return {
            "content": f"Based on the knowledge base, here is information about: {message[:50]}...",
            "sources": [
                {"title": "Related Document", "route_path": "/docs/example", "relevance": 0.85}
            ],
            "model": "extractive",
        }
