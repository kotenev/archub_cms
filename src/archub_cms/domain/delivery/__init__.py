"""Delivery (syndication) bounded context: the public read surface.

Where ``application/delivery.py`` owns response *projection* (field limiting,
expansion), this context owns the published-site read models and rules:
``Redirect`` rules, the sitemap, the RSS/Atom feed, and the tag index — the
syndication metadata a headless knowledge platform serves to consumers.
"""

from __future__ import annotations

from archub_cms.domain.delivery.read_models import (
    FeedItem,
    PublishedDocument,
    SitemapEntry,
    TagBucket,
)
from archub_cms.domain.delivery.redirect import Redirect
from archub_cms.domain.delivery.repository import DeliveryRepository

__all__ = [
    "DeliveryRepository",
    "FeedItem",
    "PublishedDocument",
    "Redirect",
    "SitemapEntry",
    "TagBucket",
]
