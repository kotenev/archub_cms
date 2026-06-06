"""Audit trail bounded context: full event-sourced audit log.

Records every significant domain event as an immutable audit entry with
actor, action, aggregate, timestamp, and diff metadata. Supports querying
by aggregate, actor, action type, and time range for compliance and debugging.
"""

from __future__ import annotations

from archub_cms.domain.audit_trail.entry import AuditEntry, AuditQuery
from archub_cms.domain.audit_trail.repository import AuditTrailRepository

__all__ = [
    "AuditEntry",
    "AuditQuery",
    "AuditTrailRepository",
]
