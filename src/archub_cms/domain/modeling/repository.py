"""Repository port for the modeling context."""

from __future__ import annotations

__all__ = ["ModelingRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.modeling.content_type import ContentTypeModel, DataType, Template


@runtime_checkable
class ModelingRepository(Protocol):
    def list_content_types(self) -> list[ContentTypeModel]: ...

    def get_content_type(self, alias: str) -> ContentTypeModel | None: ...

    def list_data_types(self, *, limit: int = 200) -> list[DataType]: ...

    def get_data_type(self, alias: str) -> DataType | None: ...

    def list_templates(self, *, limit: int = 200) -> list[Template]: ...
