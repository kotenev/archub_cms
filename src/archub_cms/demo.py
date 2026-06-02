"""Demo content bootstrap for the standalone ArcHub CMS release."""
from __future__ import annotations

from archub_cms.services.cms import ArcHubCMSService, get_archub_cms_service

__all__ = ["seed_demo_content"]


def seed_demo_content(cms: ArcHubCMSService | None = None) -> dict[str, int]:
    service = cms or get_archub_cms_service()
    created = 0
    published = 0

    root = service.get_node("root")
    if root is not None and not root.is_published:
        service.update_node(
            "root",
            name="ArcHub CMS",
            slug="",
            payload={
                "title": "ArcHub CMS",
                "description": "Standalone headless CMS demo site.",
            },
            updated_by="demo",
        )
        service.publish_node("root", published_by="demo")
        published += 1

    if service.find_node_by_field("bot_landing", "title", "ArcHub CMS demo") is None:
        node = service.create_node(
            parent_id="root",
            content_type_alias="bot_landing",
            name="ArcHub CMS demo",
            slug="demo",
            payload={
                "title": "ArcHub CMS demo",
                "hero_title": "ArcHub CMS",
                "hero_text": (
                    "A standalone headless CMS with Umbraco-style content models, "
                    "draft/publish workflow, delivery APIs and a block content builder."
                ),
                "cta_label": "Open backoffice",
                "cta_url": "/admin/archub",
                "body": (
                    "<p>This demo content is seeded by the standalone ArcHub package. "
                    "Edit it in the backoffice, publish changes, then consume the "
                    "published payload through the headless API.</p>"
                ),
                "builder_blocks": [
                    {
                        "type": "feature_grid",
                        "title": "CMS capabilities",
                        "settings": {
                            "headline": "What is included",
                            "items": (
                                "Content tree\nDocument types\nPreview tokens\n"
                                "Personalization segments\nContent Builder\nRAG material exports"
                            ),
                        },
                    }
                ],
            },
            created_by="demo",
        )
        service.publish_node(node.node_id, published_by="demo")
        created += 1
        published += 1

    if service.find_node_by_field("page", "title", "For developers") is None:
        node = service.create_node(
            parent_id="root",
            content_type_alias="page",
            name="For developers",
            slug="developers",
            payload={
                "title": "For developers",
                "summary": "Embedding ArcHub CMS in a FastAPI host.",
                "body": (
                    "<p>Install the package, include the router or create the demo app, "
                    "then connect auth, templates and runtime sources through ports.</p>"
                ),
                "builder_blocks": [],
                "seo_title": "ArcHub CMS for developers",
                "seo_description": "FastAPI headless CMS package with productized ports.",
            },
            created_by="demo",
        )
        service.publish_node(node.node_id, published_by="demo")
        created += 1
        published += 1

    if service.find_node_by_field("rag_material", "title", "Demo RAG material") is None:
        node = service.create_node(
            parent_id="root",
            content_type_alias="rag_material",
            name="Demo RAG material",
            slug="demo-rag-material",
            payload={
                "title": "Demo RAG material",
                "corpus_key": "demo",
                "source_path": "demo_content/rag/demo/overview.md",
                "body": (
                    "ArcHub can manage expert-specific RAG materials as published CMS "
                    "content and export them into runtime snapshots."
                ),
                "tags": "cms,rag,demo",
                "active": "1",
            },
            created_by="demo",
        )
        service.publish_node(node.node_id, published_by="demo")
        created += 1
        published += 1

    return {"created": created, "published": published}
