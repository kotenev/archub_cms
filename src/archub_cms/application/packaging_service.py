"""Application service for the packaging context (export/inspect/plan/import).

Wraps the legacy package operations with the :class:`ContentPackage` domain
value object and emits ``packaging.exported`` / ``packaging.imported`` events.
"""

from __future__ import annotations

__all__ = ["PackagingService", "get_archub_packaging_service"]

from collections.abc import Iterable
from typing import Any

from archub_cms.domain.packaging.package import ContentPackage, PackageInspection
from archub_cms.kernel.events import ArcHubDomainEvent, EventBus, get_event_bus
from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service


class PackagingService:
    def __init__(
        self,
        *,
        cms: ArcHubCMSService | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._bus = event_bus or get_event_bus()

    def export(
        self,
        *,
        name: str = "ArcHub package",
        description: str = "",
        node_ids: Iterable[str] = (),
        include_descendants: bool = True,
        actor: str = "",
    ) -> ContentPackage:
        data = self._cms.export_content_package(
            name=name,
            description=description,
            node_ids=list(node_ids),
            include_descendants=include_descendants,
            exported_by=actor,
        )
        package = ContentPackage(data)
        self._bus.publish(
            ArcHubDomainEvent(
                "packaging.exported",
                package.package_id,
                actor,
                {"name": package.name, "summary": package.summary()},
            )
        )
        return package

    def inspect(self, package: dict[str, Any]) -> PackageInspection:
        return PackageInspection.from_result(self._cms.inspect_content_package(package))

    def plan(self, package: dict[str, Any], *, overwrite: bool = False) -> dict[str, Any]:
        return self._cms.plan_content_package_import(package, overwrite=overwrite)

    def import_package(
        self, package: dict[str, Any], *, actor: str, overwrite: bool = False
    ) -> dict[str, Any]:
        wrapped = ContentPackage(package)
        if not wrapped.is_supported:
            raise ValueError(f"unsupported package schema: {wrapped.schema_version or '(missing)'}")
        result = self._cms.import_content_package(package, imported_by=actor, overwrite=overwrite)
        self._bus.publish(
            ArcHubDomainEvent(
                "packaging.imported",
                wrapped.package_id,
                actor,
                {"name": wrapped.name, "overwrite": overwrite},
            )
        )
        return result


def get_archub_packaging_service(*, cms: ArcHubCMSService | None = None) -> PackagingService:
    return PackagingService(cms=cms)
