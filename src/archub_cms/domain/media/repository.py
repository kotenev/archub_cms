"""Repository port for the media context."""

from __future__ import annotations

__all__ = ["MediaRepository"]

from typing import Protocol, runtime_checkable

from archub_cms.domain.media.asset import MediaAsset


@runtime_checkable
class MediaRepository(Protocol):
    def list_assets(self, *, folder: str = "", limit: int = 100) -> list[MediaAsset]: ...
