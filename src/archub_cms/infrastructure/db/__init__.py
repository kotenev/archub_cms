"""Database connection factory and additive schema migrations."""

from __future__ import annotations

from archub_cms.infrastructure.db.database import Database, connect
from archub_cms.infrastructure.db.schema import apply_extension_migrations

__all__ = ["Database", "apply_extension_migrations", "connect"]
