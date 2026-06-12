"""Analytics / health bounded context: knowledge-base observability.

Aggregates content-quality and activity signals into a health dashboard. The
:class:`HealthReport` derives a 0–100 **score** and an **A–F grade** from audit
issues — turning the raw issue list into an at-a-glance quality indicator
(Confluence/Wiki.js admin-analytics style).
"""

from __future__ import annotations

from archub_cms.domain.analytics.models import ActivityEntry, AuditIssue, HealthReport
from archub_cms.domain.analytics.repository import AnalyticsRepository

__all__ = ["ActivityEntry", "AnalyticsRepository", "AuditIssue", "HealthReport"]
