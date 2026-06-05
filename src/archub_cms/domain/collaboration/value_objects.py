"""Value objects for the collaboration context."""

from __future__ import annotations

__all__ = ["Mention", "extract_mentions"]

import re
from dataclasses import dataclass

# @username — letters, digits, dot, underscore, hyphen; 2..64 chars.
_MENTION_RE = re.compile(r"(?<![\w@])@([a-zA-Z0-9][a-zA-Z0-9._-]{1,63})")


@dataclass(frozen=True)
class Mention:
    """A normalized @mention of a user, compared case-insensitively."""

    username: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "username", self.username.strip().lstrip("@").casefold())

    def __str__(self) -> str:
        return f"@{self.username}"


def extract_mentions(text: str) -> tuple[Mention, ...]:
    """Return the unique, ordered @mentions found in ``text``."""
    seen: list[Mention] = []
    for match in _MENTION_RE.finditer(text or ""):
        mention = Mention(match.group(1))
        if mention not in seen:
            seen.append(mention)
    return tuple(seen)
