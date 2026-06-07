"""Template service: manages page templates for reuse."""

from __future__ import annotations

__all__ = ["TemplateService", "get_archub_template_service"]

from typing import Any

from archub_cms.domain.templates.models import PageTemplate


class TemplateService:
    def __init__(self) -> None:
        pass

    def create_template(
        self,
        name: str,
        body: str,
        category: str = "blank",
        space_key: str = "",
        created_by: str = "",
    ) -> PageTemplate:
        import time

        from archub_cms.kernel.value_objects import Identity

        return PageTemplate(
            template_id=Identity.generate("tmpl-").value,
            name=name,
            body=body,
            category=category,
            space_key=space_key,
            created_by=created_by,
            created_at=time.time(),
        )

    def list_templates(self, *, space_key: str = "", category: str = "") -> dict[str, Any]:
        return {"templates": [], "total": 0}

    def get_template(self, template_id: str) -> PageTemplate | None:
        return None


def get_archub_template_service() -> TemplateService:
    return TemplateService()
