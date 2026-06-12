"""Value objects for the content context: Slug, RoutePath, Culture.

These encapsulate the normalization/validation rules the legacy service applied
inline (``_slugify``, ``_route_for``, ``_CULTURE_RE``) so they are reusable and
independently testable. They are immutable and compare by value.
"""

from __future__ import annotations

__all__ = ["Culture", "PUBLIC_ROOT", "RoutePath", "Slug"]

import re
from dataclasses import dataclass

PUBLIC_ROOT = "/cms"

_SLUG_NON_ALNUM_RE = re.compile(r"[^0-9a-zа-я]+", re.IGNORECASE)
_SLUG_DASHES_RE = re.compile(r"-{2,}")
_CULTURE_RE = re.compile(r"^[a-z]{2}(?:-[a-z0-9]{2,8})?$", re.IGNORECASE)


@dataclass(frozen=True)
class Slug:
    """URL slug, normalized to lowercase dash-separated tokens (Cyrillic-aware)."""

    value: str

    @classmethod
    def create(cls, raw: str, *, fallback: str = "content") -> Slug:
        slug = (raw or "").strip().lower().replace("ё", "е")
        slug = _SLUG_NON_ALNUM_RE.sub("-", slug)
        slug = _SLUG_DASHES_RE.sub("-", slug).strip("-")
        return cls(slug or fallback)

    @classmethod
    def root(cls) -> Slug:
        return cls("")

    @property
    def is_root(self) -> bool:
        return self.value == ""

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class RoutePath:
    """Public route path of a node, composed from a parent route and a slug."""

    value: str

    @classmethod
    def compose(cls, parent_route: str | None, slug: Slug | str) -> RoutePath:
        slug_value = slug.value if isinstance(slug, Slug) else str(slug)
        if not slug_value:
            return cls(PUBLIC_ROOT)
        base = (parent_route or PUBLIC_ROOT).rstrip("/")
        return cls(f"{base}/{slug_value}")

    @property
    def is_root(self) -> bool:
        return self.value.rstrip("/") == PUBLIC_ROOT

    @property
    def space_segment(self) -> str:
        parts = [p for p in self.value.strip("/").split("/") if p]
        if len(parts) > 1 and parts[0] == "cms":
            return parts[1]
        return parts[0] if parts else "root"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Culture:
    """A locale/culture code such as ``en`` or ``fr-FR`` (invariant = empty)."""

    value: str = ""

    @classmethod
    def parse(cls, raw: str) -> Culture:
        clean = (raw or "").strip()
        if not clean:
            return cls("")
        if not _CULTURE_RE.fullmatch(clean):
            raise ValueError(f"invalid culture: {raw!r}")
        language, _, region = clean.partition("-")
        return cls(f"{language.lower()}-{region.upper()}" if region else language.lower())

    @property
    def is_invariant(self) -> bool:
        return self.value == ""

    def __str__(self) -> str:
        return self.value
