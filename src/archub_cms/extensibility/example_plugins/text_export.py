"""Example export format: plain text."""

from __future__ import annotations

from archub_cms.extensibility.extension_points import ExportFormatExt


class TextExportFormat(ExportFormatExt):
    format_id = "txt"
    format_name = "Plain Text"
    file_extension = ".txt"

    def export(self, content: list[dict], options: dict) -> bytes:
        lines = []
        for doc in content:
            title = doc.get("title", "Untitled")
            body = doc.get("body", "")
            lines.append(f"# {title}")
            lines.append("")
            lines.append(body)
            lines.append("")
            lines.append("---")
            lines.append("")
        return "\n".join(lines).encode("utf-8")
