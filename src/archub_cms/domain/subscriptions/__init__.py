"""Subscriptions / watchers bounded context (Confluence "watch").

A user can *watch* a specific node (page) and/or an event-type prefix
(``content.published``). A :class:`Subscription` matches activity events; the
inbox is *derived* by filtering the activity log against a subscriber's
subscriptions — no event-handler writes, so it stays decoupled from the write
path.
"""

from __future__ import annotations

from archub_cms.domain.subscriptions.repository import SubscriptionRepository
from archub_cms.domain.subscriptions.subscription import Subscription

__all__ = ["Subscription", "SubscriptionRepository"]
