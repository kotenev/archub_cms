"""ITIL Service Level Management: named SLA definitions with per-priority targets.

An :class:`SlaDefinition` is a reusable agreement (e.g. "Gold", "Silver") declaring
response/resolution minutes per :class:`Priority`. A catalog service links to one,
so when a request is raised against that service the desk computes its SLA due-times
from the definition. :class:`SlaRegistry` is the CRUD facade; :meth:`SlaDefinition.to_policy`
adapts a definition to the :class:`SlaPolicy` the :class:`ServiceDesk` already consumes.
"""

from __future__ import annotations

__all__ = ["SlaDefinition", "SlaRegistry"]

from dataclasses import dataclass, field
from time import time
from typing import Any

from archub_cms.extensibility.example_plugins.itsm.documents import DocumentRepository, new_id
from archub_cms.extensibility.example_plugins.itsm.request import Priority, SlaPolicy

# Sensible defaults (response, resolution) in minutes if a priority is unspecified.
_DEFAULT_TARGETS: dict[str, tuple[int, int]] = {
    "critical": (15, 240),
    "high": (30, 480),
    "medium": (120, 1440),
    "low": (480, 4320),
}


@dataclass
class SlaDefinition:
    """A named agreement mapping each priority to response/resolution minutes."""

    id: str
    name: str
    description: str = ""
    # priority value -> (response_minutes, resolution_minutes)
    targets: dict[str, tuple[int, int]] = field(default_factory=lambda: dict(_DEFAULT_TARGETS))
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_policy(self) -> SlaPolicy:
        return SlaPolicy(name=self.name or self.id, targets=dict(self.targets))

    def response_minutes(self, priority: Priority) -> int:
        return self.targets.get(priority.value, _DEFAULT_TARGETS[priority.value])[0]

    def resolution_minutes(self, priority: Priority) -> int:
        return self.targets.get(priority.value, _DEFAULT_TARGETS[priority.value])[1]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "targets": {key: list(value) for key, value in self.targets.items()},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SlaDefinition:
        return cls(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            description=str(payload.get("description") or ""),
            targets=_parse_targets(payload.get("targets")),
            created_at=float(payload.get("created_at") or 0.0),
            updated_at=float(payload.get("updated_at") or 0.0),
        )


class SlaError(ValueError):
    """Raised on SLA lookups that fail (mapped to HTTP 404 by the API)."""


class SlaRegistry:
    """CRUD facade over an SLA-definition :class:`DocumentRepository` collection."""

    def __init__(self, repository: DocumentRepository, *, clock: Any = time) -> None:
        self._repo = repository
        self._clock = clock

    def create(self, **fields: Any) -> SlaDefinition:
        now = self._clock()
        name = str(fields.get("name") or "").strip()
        if not name:
            raise SlaError("SLA name is required")
        definition = SlaDefinition(
            id=str(fields.get("id") or new_id("sla")),
            name=name,
            description=str(fields.get("description") or ""),
            targets=_parse_targets(fields.get("targets")),
            created_at=now,
            updated_at=now,
        )
        self._repo.upsert(definition.id, definition.as_dict())
        return definition

    def get(self, sla_id: str) -> SlaDefinition:
        payload = self._repo.get(sla_id)
        if payload is None:
            raise SlaError(f"unknown SLA definition {sla_id!r}")
        return SlaDefinition.from_dict(payload)

    def find(self, sla_id: str) -> SlaDefinition | None:
        payload = self._repo.get(sla_id)
        return SlaDefinition.from_dict(payload) if payload is not None else None

    def update(self, sla_id: str, **changes: Any) -> SlaDefinition:
        definition = self.get(sla_id)
        if changes.get("name"):
            definition.name = str(changes["name"]).strip()
        if "description" in changes and changes["description"] is not None:
            definition.description = str(changes["description"])
        if changes.get("targets") is not None:
            definition.targets = _parse_targets(changes["targets"])
        definition.updated_at = self._clock()
        self._repo.upsert(definition.id, definition.as_dict())
        return definition

    def delete(self, sla_id: str) -> bool:
        return self._repo.delete(sla_id)

    def list(self) -> list[SlaDefinition]:
        items = [SlaDefinition.from_dict(row) for row in self._repo.list_all()]
        return sorted(items, key=lambda d: (d.name.casefold(), d.id))

    def policy_for(self, sla_id: str) -> SlaPolicy | None:
        definition = self.find(sla_id)
        return definition.to_policy() if definition is not None else None


def _parse_targets(value: Any) -> dict[str, tuple[int, int]]:
    targets = dict(_DEFAULT_TARGETS)
    if isinstance(value, dict):
        for key, pair in value.items():
            priority = str(key).strip().lower()
            if priority not in _DEFAULT_TARGETS:
                continue
            try:
                response, resolution = int(pair[0]), int(pair[1])
            except (TypeError, ValueError, IndexError):
                continue
            targets[priority] = (max(response, 0), max(resolution, 0))
    return targets
