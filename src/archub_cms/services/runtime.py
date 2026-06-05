"""Runtime content integration helpers for ArcHub CMS."""

from __future__ import annotations

__all__ = [
    "default_runtime_import_sources",
    "runtime_corpus_specs",
    "sync_runtime_content",
]

from pathlib import Path
from typing import Any

from archub_cms.integrations.rag import iter_rag_corpus_specs
from archub_cms.services.cms import ArcHubCMSService


def runtime_corpus_specs() -> tuple[Any, ...]:
    return tuple(iter_rag_corpus_specs())


def default_runtime_import_sources() -> dict[str, Any]:
    return {
        "experts": (),
        "rag_specs": runtime_corpus_specs(),
        "bot_resource_roots": (Path("demo_content/bot_resources"),),
    }


def sync_runtime_content(
    cms: ArcHubCMSService,
    *,
    created_by: str = "system",
    export: bool = True,
) -> dict[str, Any]:
    sources = default_runtime_import_sources()
    import_report = cms.bootstrap_runtime_content(
        experts=sources["experts"],
        rag_specs=sources["rag_specs"],
        bot_resource_roots=sources["bot_resource_roots"],
        created_by=created_by,
    )
    export_report = cms.export_runtime_content() if export else None
    return {
        "import": import_report,
        "export": export_report,
        "catalog": cms.runtime_catalog(sources["rag_specs"]),
    }
