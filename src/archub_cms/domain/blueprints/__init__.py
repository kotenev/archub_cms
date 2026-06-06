"""Blueprints / templates bounded context (Confluence blueprints, Wiki.js/Obsidian templates).

A :class:`Blueprint` is a reusable, pre-filled content template for a content
type. New content is *instantiated* from it, merging caller overrides over the
template payload — the "create from template" flow every wiki has.
"""

from __future__ import annotations

from archub_cms.domain.blueprints.blueprint import Blueprint
from archub_cms.domain.blueprints.repository import BlueprintRepository

__all__ = ["Blueprint", "BlueprintRepository"]
