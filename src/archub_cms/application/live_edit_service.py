"""Live edit service: real-time collaborative editing."""

from __future__ import annotations

__all__ = ["LiveEditService", "get_archub_live_edit_service"]

from typing import Any

from archub_cms.domain.live_edit.models import EditOperation, EditSession, UserPresence
from archub_cms.extensibility.host import PluginHost, get_plugin_host


class LiveEditService:
    def __init__(self, plugin_host: PluginHost | None = None) -> None:
        self._host = plugin_host or get_plugin_host()
        self._sessions: dict[str, EditSession] = {}

    def create_session(self, node_id: str) -> EditSession:
        import time

        from archub_cms.kernel.value_objects import Identity

        session = EditSession(
            session_id=Identity.generate("session-").value,
            node_id=node_id,
            created_at=time.time(),
        )
        self._sessions[session.session_id] = session
        return session

    def join_session(self, session_id: str, user: str, color: str = "") -> UserPresence:
        import time

        presence = UserPresence(
            user=user,
            node_id=self._sessions.get(session_id, EditSession(session_id, "")).node_id,
            color=color or self._random_color(),
            last_active=time.time(),
        )
        if session_id in self._sessions:
            self._sessions[session_id].join(presence)
        return presence

    def leave_session(self, session_id: str, user: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].leave(user)

    def apply_operation(
        self, session_id: str, user: str, op_type: str, position: int, content: str = ""
    ) -> EditOperation:
        import time

        from archub_cms.kernel.value_objects import Identity

        return EditOperation(
            operation_id=Identity.generate("op-").value,
            session_id=session_id,
            user=user,
            op_type=op_type,
            position=position,
            content=content,
            timestamp=time.time(),
        )

    def get_active_users(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session:
            return {"users": [p.as_dict() for p in session.active_users.values()]}
        return {"users": []}

    def _random_color(self) -> str:
        import random

        colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]
        return random.choice(colors)


def get_archub_live_edit_service(
    plugin_host: PluginHost | None = None,
) -> LiveEditService:
    return LiveEditService(plugin_host=plugin_host)
