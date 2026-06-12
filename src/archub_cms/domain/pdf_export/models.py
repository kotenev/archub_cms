"""PDF export domain models."""

from __future__ import annotations

__all__ = ["ExportFormat", "ExportJob", "ExportStatus"]

from dataclasses import dataclass
from typing import Any


class ExportFormat:
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    DOCX = "docx"
    EPUB = "epub"
    CONFLUENCE_XML = "confluence_xml"


class ExportStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExportJob:
    job_id: str
    format: str
    target_type: str
    target_id: str
    requester: str
    status: str = ExportStatus.PENDING
    options: dict[str, Any] | None = None
    output_path: str = ""
    created_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""

    def mark_processing(self) -> None:
        self.status = ExportStatus.PROCESSING

    def mark_completed(self, output_path: str) -> None:
        self.status = ExportStatus.COMPLETED
        self.output_path = output_path

    def mark_failed(self, error: str) -> None:
        self.status = ExportStatus.FAILED
        self.error = error

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "format": self.format,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "requester": self.requester,
            "status": self.status,
            "options": self.options or {},
            "output_path": self.output_path,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }
