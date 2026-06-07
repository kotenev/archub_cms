"""Page cloning domain models."""

from __future__ import annotations

__all__ = ["CloneOptions", "CloneResult"]

from dataclasses import dataclass
from typing import Any


@dataclass
class CloneOptions:
    source_id: str
    target_parent_id: str = ""
    target_space_key: str = ""
    clone_children: bool = True
    clone_attachments: bool = True
    clone_custom_fields: bool = True
    clone_comments: bool = False
    title_prefix: str = "Copy of "
    owner: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_parent_id": self.target_parent_id,
            "target_space_key": self.target_space_key,
            "clone_children": self.clone_children,
            "clone_attachments": self.clone_attachments,
            "clone_custom_fields": self.clone_custom_fields,
            "clone_comments": self.clone_comments,
            "title_prefix": self.title_prefix,
            "owner": self.owner,
        }


@dataclass(frozen=True)
class CloneResult:
    source_id: str
    cloned_root_id: str
    pages_cloned: int
    attachments_cloned: int
    custom_fields_cloned: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "cloned_root_id": self.cloned_root_id,
            "pages_cloned": self.pages_cloned,
            "attachments_cloned": self.attachments_cloned,
            "custom_fields_cloned": self.custom_fields_cloned,
        }
