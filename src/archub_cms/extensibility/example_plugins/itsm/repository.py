"""Repository port and in-memory storage for ITSM Service Desk requests.

SQL persistence is platform-owned and lives in ``infrastructure.plugins``. The
plugin package keeps only the storage port, shared row mapping, and an in-memory
implementation used by unit tests.
"""

from __future__ import annotations

__all__ = ["InMemoryRequestRepository", "RequestRepository"]

import json
from typing import Any, Protocol, runtime_checkable

from archub_cms.extensibility.example_plugins.itsm.request import (
    CloudResource,
    Priority,
    Request,
    RequestEvent,
    RequestType,
)


@runtime_checkable
class RequestRepository(Protocol):
    """Storage port for service-desk requests."""

    def next_key(self, prefix: str) -> str:
        """Allocate the next ``PREFIX-N`` reference for a new request."""

    def save(self, request: Request) -> None:
        """Insert or update a request."""

    def get(self, key: str) -> Request | None: ...

    def list_all(self) -> list[Request]: ...


def _request_to_row(request: Request) -> dict[str, Any]:
    return {
        "key": request.key,
        "type": request.type.value,
        "summary": request.summary,
        "description": request.description,
        "scheme_key": request.scheme_key,
        "status_id": request.status_id,
        "priority": request.priority.value,
        "reporter": request.reporter,
        "assignee": request.assignee,
        "cloud_json": json.dumps(request.cloud.as_dict(), ensure_ascii=False),
        "created_at": request.created_at,
        "updated_at": request.updated_at,
        "resolution": request.resolution,
        "resolved_at": request.resolved_at,
        "sla_response_due": request.sla_response_due,
        "sla_resolution_due": request.sla_resolution_due,
        "history_json": json.dumps(
            [event.as_dict() for event in request.history], ensure_ascii=False
        ),
    }


def _request_from_row(row: Any) -> Request:
    try:
        cloud_payload = json.loads(row["cloud_json"] or "{}")
    except (ValueError, TypeError):
        cloud_payload = {}
    try:
        history_payload = json.loads(row["history_json"] or "[]")
    except (ValueError, TypeError):
        history_payload = []
    return Request(
        key=str(row["key"]),
        type=RequestType(str(row["type"])),
        summary=str(row["summary"]),
        scheme_key=str(row["scheme_key"]),
        status_id=str(row["status_id"]),
        priority=Priority(str(row["priority"])),
        description=str(row["description"] or ""),
        reporter=str(row["reporter"] or ""),
        assignee=str(row["assignee"] or ""),
        cloud=CloudResource(
            provider=str(cloud_payload.get("provider") or ""),
            service=str(cloud_payload.get("service") or ""),
            region=str(cloud_payload.get("region") or ""),
            resource_id=str(cloud_payload.get("resource_id") or ""),
        ),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        resolution=str(row["resolution"] or ""),
        resolved_at=row["resolved_at"],
        sla_response_due=row["sla_response_due"],
        sla_resolution_due=row["sla_resolution_due"],
        history=[
            RequestEvent.from_dict(item) for item in history_payload if isinstance(item, dict)
        ],
    )


class InMemoryRequestRepository:
    """Process-local request store for tests and no-database scenarios."""

    def __init__(self) -> None:
        self._rows: dict[str, Request] = {}
        self._seq: dict[str, int] = {}

    def next_key(self, prefix: str) -> str:
        self._seq[prefix] = self._seq.get(prefix, 0) + 1
        return f"{prefix}-{self._seq[prefix]}"

    def save(self, request: Request) -> None:
        self._rows[request.key] = _request_from_row(_request_to_row(request))

    def get(self, key: str) -> Request | None:
        stored = self._rows.get(key)
        return _request_from_row(_request_to_row(stored)) if stored is not None else None

    def list_all(self) -> list[Request]:
        return [
            _request_from_row(_request_to_row(request))
            for request in sorted(self._rows.values(), key=lambda r: r.created_at)
        ]
