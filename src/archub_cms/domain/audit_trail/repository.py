"""Audit trail repository port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from archub_cms.domain.audit_trail.entry import AuditEntry, AuditQuery


@runtime_checkable
class AuditTrailRepository(Protocol):
    def record(self, entry: AuditEntry) -> AuditEntry: ...
    def get(self, entry_id: str) -> AuditEntry | None: ...
    def query(self, query: AuditQuery) -> list[AuditEntry]: ...
    def count(self, query: AuditQuery | None = None) -> int: ...
