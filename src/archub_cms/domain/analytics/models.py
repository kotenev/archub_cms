"""Read models for the analytics / health context."""

from __future__ import annotations

__all__ = ["ActivityEntry", "AuditIssue", "HealthReport"]

from dataclasses import dataclass, field
from typing import Any

# score deductions per issue severity
_ERROR_PENALTY = 12
_WARNING_PENALTY = 3


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    message: str
    node_id: str = ""
    route_path: str = ""
    content_type_alias: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "message": self.message,
            "node_id": self.node_id,
            "route_path": self.route_path,
            "content_type_alias": self.content_type_alias,
        }


@dataclass(frozen=True)
class HealthReport:
    """Content health summary with a derived score and grade."""

    ok: bool
    nodes: int = 0
    published: int = 0
    draft: int = 0
    unpublished: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: tuple[AuditIssue, ...] = ()

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def score(self) -> int:
        """A 0–100 health score: full marks minus weighted issue penalties."""
        penalty = self.error_count * _ERROR_PENALTY + self.warning_count * _WARNING_PENALTY
        return max(0, 100 - penalty)

    def grade(self) -> str:
        score = self.score()
        if self.error_count == 0 and self.warning_count == 0:
            return "A"
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> HealthReport:
        issues: list[AuditIssue] = []
        for raw in result.get("issues") or ():
            issues.append(_issue_from(raw))
        return cls(
            ok=bool(result.get("ok", True)),
            nodes=int(result.get("nodes") or 0),
            published=int(result.get("published") or 0),
            draft=int(result.get("draft") or 0),
            unpublished=int(result.get("unpublished") or 0),
            error_count=int(result.get("error_count") or 0),
            warning_count=int(result.get("warning_count") or 0),
            info_count=int(result.get("info_count") or 0),
            issues=tuple(issues),
        )

    def as_dict(self, *, include_issues: bool = True) -> dict[str, Any]:
        data = {
            "ok": self.ok,
            "score": self.score(),
            "grade": self.grade(),
            "nodes": self.nodes,
            "published": self.published,
            "draft": self.draft,
            "unpublished": self.unpublished,
            "issue_count": self.issue_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
        }
        if include_issues:
            data["issues"] = [issue.as_dict() for issue in self.issues]
        return data


@dataclass(frozen=True)
class ActivityEntry:
    action: str
    actor: str = ""
    summary: str = ""
    node_id: str = ""
    node_name: str = ""
    occurred_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "actor": self.actor,
            "summary": self.summary,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "occurred_at": self.occurred_at,
            "metadata": dict(self.metadata),
        }


def _issue_from(raw: Any) -> AuditIssue:
    # Accept either a domain/dataclass object (with attributes) or a plain dict.
    def _get(name: str) -> str:
        if isinstance(raw, dict):
            return str(raw.get(name) or "")
        return str(getattr(raw, name, "") or "")

    return AuditIssue(
        severity=_get("severity"),
        message=_get("message"),
        node_id=_get("node_id"),
        route_path=_get("route_path"),
        content_type_alias=_get("content_type_alias"),
    )
