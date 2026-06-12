"""Content modeling bounded context: document types, fields, data types, templates.

The modeling context owns the *schema* of the knowledge base — Umbraco/Confluence
"content types" with typed fields, compositions (mixins), allowed children, and
templates. This package holds the clean domain model and the repository port; the
adapter currently sources data from the legacy service's hydrated reads (the
content-type field/composition hydration is intricate and stays in ``cms.py`` for
now), mapping it to these domain objects.
"""

from __future__ import annotations

from archub_cms.domain.modeling.content_type import ContentTypeModel, DataType, Template
from archub_cms.domain.modeling.field import Field
from archub_cms.domain.modeling.repository import ModelingRepository

__all__ = [
    "ContentTypeModel",
    "DataType",
    "Field",
    "ModelingRepository",
    "Template",
]
