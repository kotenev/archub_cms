"""SQLite repository for AI chat conversations."""

from __future__ import annotations

__all__ = ["AIChatRepository"]

import json
import sqlite3

from archub_cms.domain.ai_chat.models import ChatMessage, Conversation


class AIChatRepository:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._db.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                owner TEXT NOT NULL,
                space_key TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources TEXT DEFAULT '[]',
                model TEXT DEFAULT '',
                created_at REAL NOT NULL,
                tokens_used INTEGER DEFAULT 0
            )
            """
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON chat_messages(conversation_id)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_owner ON conversations(owner)"
        )
        self._db.commit()

    def save_conversation(self, conv: Conversation) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO conversations (conversation_id, title, owner, space_key, created_at, updated_at, message_count, is_archived)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                conv.conversation_id,
                conv.title,
                conv.owner,
                conv.space_key,
                conv.created_at,
                conv.updated_at,
                conv.message_count,
                int(conv.is_archived),
            ),
        )
        self._db.commit()

    def save_message(self, msg: ChatMessage) -> None:
        self._db.execute(
            "INSERT INTO chat_messages (message_id, conversation_id, role, content, sources, model, created_at, tokens_used)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                msg.message_id,
                msg.conversation_id,
                msg.role,
                msg.content,
                json.dumps(list(msg.sources)),
                msg.model,
                msg.created_at,
                msg.tokens_used,
            ),
        )
        self._db.commit()

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        row = self._db.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()
        if row is None:
            return None
        return Conversation(
            conversation_id=row["conversation_id"],
            title=row["title"],
            owner=row["owner"],
            space_key=row["space_key"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            message_count=row["message_count"],
            is_archived=bool(row["is_archived"]),
        )

    def list_conversations(self, owner: str, include_archived: bool = False) -> list[Conversation]:
        sql = "SELECT * FROM conversations WHERE owner = ?"
        if not include_archived:
            sql += " AND is_archived = 0"
        sql += " ORDER BY updated_at DESC"
        rows = self._db.execute(sql, (owner,)).fetchall()
        return [
            Conversation(
                conversation_id=r["conversation_id"],
                title=r["title"],
                owner=r["owner"],
                space_key=r["space_key"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                message_count=r["message_count"],
                is_archived=bool(r["is_archived"]),
            )
            for r in rows
        ]

    def list_messages(self, conversation_id: str) -> list[ChatMessage]:
        rows = self._db.execute(
            "SELECT * FROM chat_messages WHERE conversation_id = ? ORDER BY created_at",
            (conversation_id,),
        ).fetchall()
        return [
            ChatMessage(
                message_id=r["message_id"],
                conversation_id=r["conversation_id"],
                role=r["role"],
                content=r["content"],
                sources=tuple(json.loads(r["sources"])),
                model=r["model"],
                created_at=r["created_at"],
                tokens_used=r["tokens_used"],
            )
            for r in rows
        ]
