"""Pure facet computation over candidate documents."""

from __future__ import annotations

__all__ = ["FacetBuilder"]

from collections import Counter
from collections.abc import Iterable
from typing import Any

from archub_cms.domain.search.models import Facet


class FacetBuilder:
    """Counts facet values across a set of document dicts.

    Scalar fields (e.g. ``content_type_alias``, ``space_key``) count one per doc;
    list fields (e.g. ``tags``) count each element.
    """

    @staticmethod
    def build(
        documents: Iterable[dict[str, Any]], *, fields: Iterable[str], top: int = 20
    ) -> list[Facet]:
        docs = list(documents)
        facets: list[Facet] = []
        for field in fields:
            counter: Counter[str] = Counter()
            for doc in docs:
                value = doc.get(field)
                if isinstance(value, list | tuple):
                    counter.update(str(v) for v in value if str(v))
                elif value not in (None, ""):
                    counter[str(value)] += 1
            buckets = tuple(
                (value, count)
                for value, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
            )
            facets.append(Facet(field=field, buckets=buckets))
        return facets
