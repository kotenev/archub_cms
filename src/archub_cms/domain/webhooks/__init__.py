"""Webhooks / notifications bounded context (Outbox pattern).

Outbound event delivery: a :class:`Webhook` subscribes to event types (exact,
prefix ``content.*``, or ``*``) and is delivered to asynchronously. Deliveries
are persisted (the outbox) and dispatched in batches with retry — decoupling the
write path from slow/failing endpoints. In-process notification *channels* (the
``NotificationExt`` plugin point) provide a complementary push surface.
"""

from __future__ import annotations

from archub_cms.domain.webhooks.repository import WebhookRepository
from archub_cms.domain.webhooks.webhook import Webhook, WebhookDeliveryRecord

__all__ = ["Webhook", "WebhookDeliveryRecord", "WebhookRepository"]
