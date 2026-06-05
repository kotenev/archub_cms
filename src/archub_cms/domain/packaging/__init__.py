"""Packaging bounded context: portable content bundles (export/import).

Models a self-describing :class:`ContentPackage` (schema-versioned bundle of
nodes, content model, media, redirects, workflows …) — the Confluence
space-export / Wiki.js-migration unit. The aggregate validates the schema and
summarizes contents; the application service exports/inspects/plans/imports.
"""

from __future__ import annotations

from archub_cms.domain.packaging.package import (
    PACKAGE_SCHEMA_VERSION,
    ContentPackage,
    PackageInspection,
)

__all__ = ["PACKAGE_SCHEMA_VERSION", "ContentPackage", "PackageInspection"]
