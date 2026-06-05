"""The ``DictionaryEntry`` aggregate with locale-fallback resolution."""

from __future__ import annotations

__all__ = ["DictionaryEntry"]

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DictionaryEntry:
    """A translatable label keyed by locale, with fallback resolution.

    ``resolve`` mirrors how localized labels are looked up: try the exact culture
    (``fr-FR``), then the language (``fr``), then a ``default`` value, then any
    available value — finally the caller's ``default``.
    """

    key: str
    group: str = ""
    values: dict[str, str] = field(default_factory=dict)

    def resolve(self, culture: str = "", *, default: str = "") -> str:
        clean = (culture or "").strip()
        if clean and clean in self.values:
            return self.values[clean]
        language = clean.split("-", 1)[0]
        if language and language in self.values:
            return self.values[language]
        # case-insensitive retry for exact + language
        lowered = {k.casefold(): v for k, v in self.values.items()}
        if clean.casefold() in lowered:
            return lowered[clean.casefold()]
        if language.casefold() in lowered:
            return lowered[language.casefold()]
        if "default" in self.values:
            return self.values["default"]
        return next(iter(self.values.values()), default)

    @property
    def locales(self) -> tuple[str, ...]:
        return tuple(sorted(self.values))

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "group": self.group,
            "values": dict(self.values),
            "locales": list(self.locales),
        }
