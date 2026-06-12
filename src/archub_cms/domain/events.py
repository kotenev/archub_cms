"""Back-compat shim.

The canonical home for domain events is now :mod:`archub_cms.kernel.events`,
which also provides the in-process ``EventBus``. This module re-exports the
event primitives so existing imports keep working.
"""

from __future__ import annotations

__all__ = ["ArcHubDomainEvent", "content_event"]

from archub_cms.kernel.events import ArcHubDomainEvent, content_event
