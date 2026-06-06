"""Edit-locks bounded context (Confluence/Wiki.js "page is being edited by X").

A short-lived :class:`EditLock` reserves a node for one editor so concurrent
edits don't clobber each other. Locks expire after a TTL; another editor may
force-acquire. State lives in the legacy store; this context models the lock and
its lifecycle (acquire/release with conflict + expiry rules).
"""

from __future__ import annotations

from archub_cms.domain.locks.lock import EditLock
from archub_cms.domain.locks.repository import LockRepository

__all__ = ["EditLock", "LockRepository"]
