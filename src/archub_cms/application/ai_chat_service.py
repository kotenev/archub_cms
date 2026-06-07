"""AI chat service: conversational interface over the knowledge base."""

from __future__ import annotations

__all__ = ["AIChatService", "get_archub_ai_chat_service"]

from typing import Any

from archub_cms.domain.ai_chat.models import ChatMessage, Conversation
from archub_cms.extensibility.host import PluginHost, get_plugin_host


class AIChatService:
    def __init__(self, plugin_host: PluginHost | None = None) -> None:
        self._host = plugin_host or get_plugin_host()

    def create_conversation(self, title: str, owner: str, space_key: str = "") -> Conversation:
        import time

        from archub_cms.kernel.value_objects import Identity

        return Conversation(
            conversation_id=Identity.generate("conv-").value,
            title=title,
            owner=owner,
            space_key=space_key,
            created_at=time.time(),
        )

    def send_message(self, conversation_id: str, message: str, user: str) -> dict[str, Any]:
        handlers = self._host.chat_handlers
        if handlers:
            for _handler_id, handler in handlers.items():
                return handler.respond(conversation_id, message, {"user": user})
        return {
            "message": ChatMessage(
                message_id="msg-1",
                conversation_id=conversation_id,
                role="assistant",
                content="AI chat not configured.",
            ).as_dict(),
            "sources": [],
        }

    def list_conversations(self, owner: str) -> dict[str, Any]:
        return {"conversations": [], "total": 0}


def get_archub_ai_chat_service(
    plugin_host: PluginHost | None = None,
) -> AIChatService:
    return AIChatService(plugin_host=plugin_host)
