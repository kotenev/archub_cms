"""Localization / i18n bounded context (Wiki.js-style multi-language).

Models per-culture content variants (:class:`LocalizedVariant`) and a
translatable :class:`DictionaryEntry` whose ``resolve`` implements locale
fallback (exact culture → language → ``default``). Reuses the
:class:`~archub_cms.domain.content.value_objects.Culture` value object.
"""

from __future__ import annotations

from archub_cms.domain.localization.dictionary import DictionaryEntry
from archub_cms.domain.localization.repository import LocalizationRepository
from archub_cms.domain.localization.variant import LocalizedVariant

__all__ = ["DictionaryEntry", "LocalizationRepository", "LocalizedVariant"]
