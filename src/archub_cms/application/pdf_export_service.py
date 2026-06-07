"""PDF/export generation service."""

from __future__ import annotations

__all__ = ["PDFExportService", "get_archub_pdf_export_service"]

from typing import Any

from archub_cms.domain.pdf_export.models import ExportJob, ExportStatus
from archub_cms.extensibility.host import PluginHost, get_plugin_host


class PDFExportService:
    def __init__(self, plugin_host: PluginHost | None = None) -> None:
        self._host = plugin_host or get_plugin_host()

    def create_export_job(
        self,
        format: str,
        target_type: str,
        target_id: str,
        requester: str,
        options: dict[str, Any] | None = None,
    ) -> ExportJob:
        import time

        from archub_cms.kernel.value_objects import Identity

        return ExportJob(
            job_id=Identity.generate("export-").value,
            format=format,
            target_type=target_type,
            target_id=target_id,
            requester=requester,
            options=options,
            created_at=time.time(),
        )

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        return {"job_id": job_id, "status": ExportStatus.PENDING}

    def list_jobs(self, requester: str, limit: int = 20) -> dict[str, Any]:
        return {"jobs": [], "total": 0}

    def get_supported_formats(self) -> dict[str, Any]:
        formats = self._host.export_formats
        return {
            "formats": [
                {"id": fid, "name": f.format_name, "extension": f.file_extension}
                for fid, f in formats.items()
            ]
            + [
                {"id": "pdf", "name": "PDF", "extension": ".pdf"},
                {"id": "html", "name": "HTML", "extension": ".html"},
                {"id": "markdown", "name": "Markdown", "extension": ".md"},
            ],
            "total": len(formats) + 3,
        }


def get_archub_pdf_export_service(
    plugin_host: PluginHost | None = None,
) -> PDFExportService:
    return PDFExportService(plugin_host=plugin_host)
