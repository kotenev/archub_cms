"""Package promotion application service for ArcHub CMS.

.. deprecated:: Superseded by the packaging bounded context
   (``archub_cms.application.packaging_service.PackagingService`` over the
   ``domain.packaging.ContentPackage`` value object). Kept for back-compat.
"""

from __future__ import annotations

__all__ = [
    "PackageOperationResult",
    "ArcHubPackageService",
    "get_archub_package_service",
]

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from archub_cms.domain.events import ArcHubDomainEvent
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


@dataclass(frozen=True)
class PackageOperationResult:
    """Result envelope for package promotion use cases."""

    payload: dict[str, Any]
    events: tuple[ArcHubDomainEvent, ...] = ()
    status_code: int = 200

    @property
    def ok(self) -> bool:
        return bool(self.payload.get("ok", True))

    def as_dict(self, *, include_events: bool = False) -> dict[str, Any]:
        if not include_events:
            return self.payload
        return {
            **self.payload,
            "events": [event.as_dict() for event in self.events],
        }


class ArcHubPackageService:
    """Application boundary for content package export and import flows."""

    def __init__(self, cms: ArcHubCMSService | None = None) -> None:
        self._cms = cms or get_archub_cms_service()

    def export(
        self,
        *,
        name: str = "ArcHub package",
        description: str = "",
        node_ids: Iterable[str] = (),
        include_descendants: bool = True,
        exported_by: str = "system",
    ) -> PackageOperationResult:
        selected_node_ids = tuple(node_ids)
        package = self._cms.export_content_package(
            name=name,
            description=description,
            node_ids=selected_node_ids,
            include_descendants=include_descendants,
            exported_by=exported_by,
        )
        return PackageOperationResult(
            payload=package,
            events=(
                _package_event(
                    "package.exported",
                    package,
                    actor=exported_by,
                    metadata={
                        "node_ids": list(selected_node_ids),
                        "include_descendants": include_descendants,
                        "counts": package.get("summary", {}).get("counts", {}),
                    },
                ),
            ),
        )

    def inspect(
        self,
        package: dict[str, Any],
        *,
        actor: str = "system",
    ) -> PackageOperationResult:
        inspection = self._cms.inspect_content_package(package)
        return PackageOperationResult(
            payload=inspection,
            events=(
                _package_event(
                    "package.inspected",
                    package,
                    actor=actor,
                    metadata={"counts": inspection.get("counts", {})},
                ),
            ),
            status_code=200 if inspection.get("ok") else 400,
        )

    def plan_import(
        self,
        package: dict[str, Any],
        *,
        overwrite: bool = False,
        actor: str = "system",
    ) -> PackageOperationResult:
        plan = self._cms.plan_content_package_import(package, overwrite=overwrite)
        return PackageOperationResult(
            payload=plan,
            events=(
                _package_event(
                    "package.import.planned",
                    package,
                    actor=actor,
                    metadata={
                        "overwrite": overwrite,
                        "counts": plan.get("counts", {}),
                        "conflicts": len(plan.get("conflicts", [])),
                    },
                ),
            ),
            status_code=200 if plan.get("ok") else 400,
        )

    def import_package(
        self,
        package: dict[str, Any],
        *,
        imported_by: str,
        overwrite: bool = False,
    ) -> PackageOperationResult:
        result = self._cms.import_content_package(
            package,
            imported_by=imported_by,
            overwrite=overwrite,
        )
        event_type = "package.imported" if result.get("ok") else "package.import.rejected"
        return PackageOperationResult(
            payload=result,
            events=(
                _package_event(
                    event_type,
                    package,
                    actor=imported_by,
                    metadata={
                        "overwrite": overwrite,
                        "imported": result.get("imported", {}),
                        "skipped": result.get("skipped", {}),
                    },
                ),
            ),
            status_code=200 if result.get("ok") else 400,
        )


def get_archub_package_service(cms: ArcHubCMSService | None = None) -> ArcHubPackageService:
    return ArcHubPackageService(cms=cms)


def _package_event(
    event_type: str,
    package: dict[str, Any],
    *,
    actor: str,
    metadata: dict[str, Any] | None = None,
) -> ArcHubDomainEvent:
    return ArcHubDomainEvent(
        event_type=event_type,
        aggregate_id=str(package.get("package_id") or package.get("name") or "package"),
        actor=actor,
        metadata=metadata or {},
    )
