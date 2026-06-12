"""Trash / recycle-bin bounded context (Confluence/Wiki.js recycle bin).

Deleted nodes are soft-deleted (status ``trashed``), not destroyed. This context
lists the recycle bin, **restores** items to their original location, and
**purges** them permanently.
"""

from __future__ import annotations

from archub_cms.domain.trash.item import TrashedItem
from archub_cms.domain.trash.repository import TrashRepository

__all__ = ["TrashRepository", "TrashedItem"]
