"""Example import format: Markdown files."""

from __future__ import annotations

from archub_cms.extensibility.extension_points import ImportFormatExt


class MarkdownImportFormat(ImportFormatExt):
    format_id = "markdown"
    format_name = "Markdown"
    file_extensions = (".md", ".markdown", ".mdown")

    def parse(self, data: bytes, options: dict) -> list[dict]:
        text = data.decode("utf-8")
        lines = text.split("\n")
        title = ""
        body_lines = []
        for line in lines:
            if line.startswith("# ") and not title:
                title = line[2:].strip()
            else:
                body_lines.append(line)
        if not title:
            title = "Imported Document"
        return [
            {
                "title": title,
                "body": "\n".join(body_lines),
                "content_type": "text/markdown",
            }
        ]
