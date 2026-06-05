"""Media bounded context: managed asset references (images, docs, video).

Models asset *metadata* (filename, content type, folder, tags) as the
:class:`MediaAsset` aggregate with content-type allow-listing. Actual blob bytes
live behind the ``StorageExt`` plugin port, so backends (memory/filesystem/git/
s3) are pluggable.
"""

from __future__ import annotations

from archub_cms.domain.media.asset import MediaAsset
from archub_cms.domain.media.repository import MediaRepository

__all__ = ["MediaAsset", "MediaRepository"]
