"""Example content transformer plugin demonstrating ContentTransformerExt."""

from __future__ import annotations

from typing import Any

from archub_cms.extensibility.extension_points import ContentTransformerExt


class TableOfContentsTransformer:
    """Injects a table of contents into content during render phase."""

    def setup(self, context: Any) -> None:
        context.register(TocInjector())


class TocInjector(ContentTransformerExt):
    transformer_name = "toc-injector"
    phase = "render"

    def transform(self, content: dict[str, Any]) -> dict[str, Any]:
        body = content.get("body", "")
        if not body:
            return content
        headings: list[str] = []
        for line in body.split("\n"):
            stripped = line.strip()
            if stripped.startswith("## "):
                headings.append(stripped[3:].strip())
        if not headings:
            return content
        toc_lines = ["**Table of Contents**"]
        for heading in headings:
            anchor = heading.lower().replace(" ", "-")
            toc_lines.append(f"- [{heading}](#{anchor})")
        toc = "\n".join(toc_lines) + "\n\n---\n\n"
        return {**content, "body": toc + body}
