"""Repository port for the localization context."""

from __future__ import annotations

__all__ = ["LocalizationRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.localization.dictionary import DictionaryEntry
from archub_cms.domain.localization.variant import LocalizedVariant


@runtime_checkable
class LocalizationRepository(Protocol):
    def variants(self, node_id: str) -> list[LocalizedVariant]: ...

    def variant(self, node_id: str, culture: str) -> LocalizedVariant | None: ...

    def dictionary(self, *, group: str = "", limit: int = 200) -> list[DictionaryEntry]: ...

    def dictionary_entry(self, key: str, *, group: str = "") -> DictionaryEntry | None: ...
