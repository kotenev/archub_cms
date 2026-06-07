"""Domain specifications for content and governance queries."""

from __future__ import annotations

__all__ = [
    "ActiveJobSpec",
    "CanPublishSpec",
    "IsOwnerSpec",
    "PublishedContentSpec",
    "PublicSpaceSpec",
    "TaggedWithSpec",
]

from archub_cms.domain.scheduler.job import JobStatus, ScheduledJob
from archub_cms.domain.spaces.space import Space
from archub_cms.kernel.specification import Specification, spec


def PublishedContentSpec() -> Specification:
    """Matches content nodes that are in the published state."""

    return spec(lambda node: getattr(node, "is_published", False))


def CanPublishSpec() -> Specification:
    """Matches content nodes that pass publish validation."""

    return spec(lambda node: getattr(node, "can_publish", lambda: None)().ok is True)


def ActiveJobSpec() -> Specification:
    """Matches scheduled jobs that are active and due to run."""

    return spec(lambda job: isinstance(job, ScheduledJob) and job.status == JobStatus.ACTIVE)


def IsOwnerSpec(username: str) -> Specification:
    """Matches spaces owned by the given user."""

    return spec(lambda space: isinstance(space, Space) and space.owner == username)


def PublicSpaceSpec() -> Specification:
    """Matches spaces with public visibility."""

    return spec(lambda space: isinstance(space, Space) and space.visibility == "public")


def TaggedWithSpec(tag_slug: str) -> Specification:
    """Matches any object with a ``tags`` tuple containing the given slug."""

    def _check(candidate: object) -> bool:
        tags = getattr(candidate, "tags", ())
        return tag_slug in tags

    return spec(_check)
