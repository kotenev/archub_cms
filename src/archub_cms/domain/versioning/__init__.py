"""Versioning bounded context: content history, restore, and field-level diff.

Every content change snapshots a :class:`Version`. This context models the
version history and adds a Wiki.js/Confluence-style **diff** — a field-level
comparison between two versions (added/removed/changed fields) — on top of the
legacy version store.
"""

from __future__ import annotations

from archub_cms.domain.versioning.diff import ChangeType, FieldChange, VersionDiff
from archub_cms.domain.versioning.repository import VersioningRepository
from archub_cms.domain.versioning.version import Version

__all__ = [
    "ChangeType",
    "FieldChange",
    "Version",
    "VersionDiff",
    "VersioningRepository",
]
