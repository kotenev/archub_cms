"""AI chat domain models."""

from __future__ import annotations

__all__ = ["ChatMessage", "ChatRole", "Conversation"]

from dataclasses import dataclass
from typing import Any


class ChatRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ChatMessage:
    message_id: str
    conversation_id: str
    role: str
    content: str
    sources: tuple[dict[str, Any], ...] = ()
    model: str = ""
    created_at: float = 0.0
    tokens_used: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "sources": list(self.sources),
            "model": self.model,
            "created_at": self.created_at,
            "tokens_used": self.tokens_used,
        }


@dataclass
class Conversation:
    conversation_id: str
    title: str
    owner: str
    space_key: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    message_count: int = 0
    is_archived: bool = False

    def archive(self) -> None:
        self.is_archived = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "title": self.title,
            "owner": self.owner,
            "space_key": self.space_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "is_archived": self.is_archived,
        }
