"""Search bounded context: federated, faceted knowledge search.

A single "search everything" surface (Confluence/Wiki.js style) that ranks via
the hybrid lexical+semantic+plugin ranker and computes **facets** (counts by
content type, space and tag) plus filtering and pagination over the result set.
"""

from __future__ import annotations

from archub_cms.domain.search.facets import FacetBuilder
from archub_cms.domain.search.models import (
    Facet,
    SearchQuery,
    SearchResultItem,
    SearchResults,
)

__all__ = [
    "Facet",
    "FacetBuilder",
    "SearchQuery",
    "SearchResultItem",
    "SearchResults",
]
