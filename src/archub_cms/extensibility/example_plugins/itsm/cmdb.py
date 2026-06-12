"""ITIL CMDB: configuration items and their relationships, with impact analysis.

A :class:`ConfigurationItem` (CI) is a managed cloud object — a server, database,
load balancer, application or business service. :class:`CIRelationship` edges connect
them (``runs_on``, ``depends_on``, ``connected_to``, ``hosts``, ``uses``). The
:class:`Cmdb` facade stores both in :class:`DocumentRepository` collections and offers
**impact analysis**: given a CI, which other CIs are affected if it fails (upstream
dependents) and what it itself relies on (downstream dependencies) — the core question
an incident/change manager asks before acting.
"""

from __future__ import annotations

__all__ = [
    "CIRelationship",
    "CIStatus",
    "CIType",
    "Cmdb",
    "ConfigurationItem",
    "RelationshipType",
]

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from time import time
from typing import Any

from archub_cms.extensibility.example_plugins.itsm.documents import DocumentRepository, new_id
from archub_cms.extensibility.example_plugins.itsm.request import CloudResource

# Relationship types whose edges propagate failure impact from target → source
# (i.e. "source depends on target", so if target breaks, source is impacted).
_DEPENDENCY_TYPES = frozenset({"depends_on", "runs_on", "uses", "hosted_on"})


class CIType(StrEnum):
    BUSINESS_SERVICE = "business_service"
    APPLICATION = "application"
    SERVER = "server"
    DATABASE = "database"
    NETWORK = "network"
    STORAGE = "storage"
    CONTAINER = "container"
    LOAD_BALANCER = "load_balancer"
    OTHER = "other"


class CIStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class RelationshipType(StrEnum):
    DEPENDS_ON = "depends_on"
    RUNS_ON = "runs_on"
    HOSTED_ON = "hosted_on"
    CONNECTED_TO = "connected_to"
    HOSTS = "hosts"
    USES = "uses"


@dataclass
class ConfigurationItem:
    """A managed configuration item (CI) in the cloud estate."""

    id: str
    name: str
    ci_type: CIType = CIType.OTHER
    status: CIStatus = CIStatus.ACTIVE
    description: str = ""
    owner: str = ""
    service_id: str = ""
    cloud: CloudResource = field(default_factory=CloudResource)
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "ci_type": self.ci_type.value,
            "status": self.status.value,
            "description": self.description,
            "owner": self.owner,
            "service_id": self.service_id,
            "cloud": self.cloud.as_dict(),
            "attributes": dict(self.attributes),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ConfigurationItem:
        cloud = payload.get("cloud") if isinstance(payload.get("cloud"), dict) else {}
        return cls(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            ci_type=_enum(CIType, payload.get("ci_type"), CIType.OTHER),
            status=_enum(CIStatus, payload.get("status"), CIStatus.ACTIVE),
            description=str(payload.get("description") or ""),
            owner=str(payload.get("owner") or ""),
            service_id=str(payload.get("service_id") or ""),
            cloud=CloudResource(
                provider=str(cloud.get("provider") or ""),
                service=str(cloud.get("service") or ""),
                region=str(cloud.get("region") or ""),
                resource_id=str(cloud.get("resource_id") or ""),
            ),
            attributes=dict(payload.get("attributes") or {}),
            created_at=float(payload.get("created_at") or 0.0),
            updated_at=float(payload.get("updated_at") or 0.0),
        )


@dataclass
class CIRelationship:
    """A directed edge between two CIs (source --type--> target)."""

    id: str
    source_id: str
    target_id: str
    type: RelationshipType = RelationshipType.DEPENDS_ON
    created_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.type.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CIRelationship:
        return cls(
            id=str(payload.get("id") or ""),
            source_id=str(payload.get("source_id") or ""),
            target_id=str(payload.get("target_id") or ""),
            type=_enum(RelationshipType, payload.get("type"), RelationshipType.DEPENDS_ON),
            created_at=float(payload.get("created_at") or 0.0),
        )


class CmdbError(ValueError):
    """Raised on CMDB lookups that fail (mapped to HTTP 404 by the API)."""


class Cmdb:
    """Facade over CI + relationship :class:`DocumentRepository` collections."""

    def __init__(
        self,
        items: DocumentRepository,
        relationships: DocumentRepository,
        *,
        clock: Any = time,
    ) -> None:
        self._items = items
        self._rels = relationships
        self._clock = clock

    # -- configuration items ----------------------------------------------

    def add_item(self, **fields: Any) -> ConfigurationItem:
        now = self._clock()
        name = str(fields.get("name") or "").strip()
        if not name:
            raise CmdbError("configuration item name is required")
        cloud_payload = fields.get("cloud") if isinstance(fields.get("cloud"), dict) else {}
        item = ConfigurationItem(
            id=str(fields.get("id") or new_id("ci")),
            name=name,
            ci_type=_enum(CIType, fields.get("ci_type"), CIType.OTHER),
            status=_enum(CIStatus, fields.get("status"), CIStatus.ACTIVE),
            description=str(fields.get("description") or ""),
            owner=str(fields.get("owner") or ""),
            service_id=str(fields.get("service_id") or ""),
            cloud=CloudResource(
                provider=str(cloud_payload.get("provider") or ""),
                service=str(cloud_payload.get("service") or ""),
                region=str(cloud_payload.get("region") or ""),
                resource_id=str(cloud_payload.get("resource_id") or ""),
            ),
            attributes=dict(fields.get("attributes") or {}),
            created_at=now,
            updated_at=now,
        )
        self._items.upsert(item.id, item.as_dict())
        return item

    def get_item(self, ci_id: str) -> ConfigurationItem:
        payload = self._items.get(ci_id)
        if payload is None:
            raise CmdbError(f"unknown configuration item {ci_id!r}")
        return ConfigurationItem.from_dict(payload)

    def find_item(self, ci_id: str) -> ConfigurationItem | None:
        payload = self._items.get(ci_id)
        return ConfigurationItem.from_dict(payload) if payload is not None else None

    def update_item(self, ci_id: str, **changes: Any) -> ConfigurationItem:
        item = self.get_item(ci_id)
        for key in ("name", "description", "owner", "service_id"):
            if key in changes and changes[key] is not None:
                setattr(item, key, str(changes[key]))
        if changes.get("ci_type"):
            item.ci_type = _enum(CIType, changes["ci_type"], item.ci_type)
        if changes.get("status"):
            item.status = _enum(CIStatus, changes["status"], item.status)
        if isinstance(changes.get("attributes"), dict):
            item.attributes = dict(changes["attributes"])
        if isinstance(changes.get("cloud"), dict):
            cloud = changes["cloud"]
            item.cloud = CloudResource(
                provider=str(cloud.get("provider") or ""),
                service=str(cloud.get("service") or ""),
                region=str(cloud.get("region") or ""),
                resource_id=str(cloud.get("resource_id") or ""),
            )
        item.updated_at = self._clock()
        self._items.upsert(item.id, item.as_dict())
        return item

    def delete_item(self, ci_id: str) -> bool:
        # Also drop relationships touching the removed CI to avoid dangling edges.
        for rel in self.list_relationships():
            if ci_id in (rel.source_id, rel.target_id):
                self._rels.delete(rel.id)
        return self._items.delete(ci_id)

    def list_items(self, *, ci_type: str = "", service_id: str = "") -> list[ConfigurationItem]:
        items = [ConfigurationItem.from_dict(row) for row in self._items.list_all()]
        if ci_type:
            items = [i for i in items if i.ci_type.value == ci_type]
        if service_id:
            items = [i for i in items if i.service_id == service_id]
        return sorted(items, key=lambda i: (i.ci_type.value, i.name.casefold(), i.id))

    # -- relationships -----------------------------------------------------

    def relate(self, source_id: str, target_id: str, type: Any = "depends_on") -> CIRelationship:
        # Validate both endpoints exist (raises CmdbError otherwise).
        self.get_item(source_id)
        self.get_item(target_id)
        if source_id == target_id:
            raise CmdbError("a configuration item cannot relate to itself")
        relationship = CIRelationship(
            id=new_id("rel"),
            source_id=source_id,
            target_id=target_id,
            type=_enum(RelationshipType, type, RelationshipType.DEPENDS_ON),
            created_at=self._clock(),
        )
        self._rels.upsert(relationship.id, relationship.as_dict())
        return relationship

    def unrelate(self, relationship_id: str) -> bool:
        return self._rels.delete(relationship_id)

    def list_relationships(self, *, ci_id: str = "") -> list[CIRelationship]:
        rels = [CIRelationship.from_dict(row) for row in self._rels.list_all()]
        if ci_id:
            rels = [r for r in rels if ci_id in (r.source_id, r.target_id)]
        return sorted(rels, key=lambda r: r.created_at)

    # -- impact analysis ---------------------------------------------------

    def impact(self, ci_id: str) -> dict[str, Any]:
        """Upstream dependents (impacted if ``ci_id`` fails) + downstream dependencies."""

        self.get_item(ci_id)
        rels = self.list_relationships()
        # dependents[target] = sources that depend on target
        dependents: dict[str, list[str]] = {}
        dependencies: dict[str, list[str]] = {}
        for rel in rels:
            if rel.type.value in _DEPENDENCY_TYPES:
                dependents.setdefault(rel.target_id, []).append(rel.source_id)
                dependencies.setdefault(rel.source_id, []).append(rel.target_id)
        impacted = self._traverse(ci_id, dependents)
        depends_on = self._traverse(ci_id, dependencies)
        return {
            "ci_id": ci_id,
            "impacted": [self.get_item(cid).as_dict() for cid in impacted],
            "impacted_count": len(impacted),
            "depends_on": [self.get_item(cid).as_dict() for cid in depends_on],
            "depends_on_count": len(depends_on),
        }

    @staticmethod
    def _traverse(start: str, adjacency: dict[str, list[str]]) -> list[str]:
        seen: list[str] = []
        visited = {start}
        queue: deque[str] = deque([start])
        while queue:
            current = queue.popleft()
            for neighbour in adjacency.get(current, ()):
                if neighbour not in visited:
                    visited.add(neighbour)
                    seen.append(neighbour)
                    queue.append(neighbour)
        return seen

    def report(self) -> dict[str, Any]:
        items = self.list_items()
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for item in items:
            by_type[item.ci_type.value] = by_type.get(item.ci_type.value, 0) + 1
            by_status[item.status.value] = by_status.get(item.status.value, 0) + 1
        return {
            "items_total": len(items),
            "relationships_total": len(self.list_relationships()),
            "by_type": by_type,
            "by_status": by_status,
        }


def _enum(enum_cls: Any, value: Any, default: Any) -> Any:
    try:
        return enum_cls(str(value))
    except ValueError:
        return default
