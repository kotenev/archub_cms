"""Content Builder service for ArcHub CMS.

The builder is intentionally independent from the CMS storage service. ArcHub
stores builder blocks as JSON in a content payload, while this service owns the
block registry, normalization, previews, and public HTML rendering.
"""
from __future__ import annotations

__all__ = [
    "BuilderAuditIssue",
    "BuilderField",
    "ContentBlueprint",
    "ContentBlock",
    "ContentBlockType",
    "ArcHubContentBuilderService",
    "get_archub_content_builder_service",
]

import html
import json
import re
import secrets
from dataclasses import dataclass
from functools import cache
from typing import Any

_SCRIPT_RE = re.compile(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script\s*>", re.IGNORECASE)
_EVENT_ATTR_RE = re.compile(r"\son[a-z]+\s*=\s*(['\"]).*?\1", re.IGNORECASE | re.DOTALL)
_JS_URL_RE = re.compile(r"(href|src)\s*=\s*(['\"])\s*javascript:[^'\"]*\2", re.IGNORECASE)


@dataclass(frozen=True)
class BuilderAuditIssue:
    severity: str
    block_id: str
    block_type: str
    message: str


@dataclass(frozen=True)
class ContentBlueprint:
    alias: str
    name: str
    content_type_aliases: tuple[str, ...]
    description: str
    blocks: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class BuilderField:
    alias: str
    name: str
    editor: str = "text"
    required: bool = False
    default: Any = ""
    help_text: str = ""
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContentBlockType:
    alias: str
    name: str
    icon: str
    category: str
    description: str
    fields: tuple[BuilderField, ...]
    sample: dict[str, Any]


@dataclass(frozen=True)
class ContentBlock:
    block_id: str
    block_type: str
    title: str
    settings: dict[str, Any]
    order: int = 0


class ArcHubContentBuilderService:
    """Registry, serializer, preview renderer, and public renderer for blocks."""

    def __init__(self) -> None:
        self._types = {item.alias: item for item in self._default_block_types()}
        self._blueprints = {item.alias: item for item in self._default_blueprints()}

    def list_block_types(self) -> list[ContentBlockType]:
        return sorted(self._types.values(), key=lambda item: (item.category, item.name))

    def get_block_type(self, alias: str) -> ContentBlockType | None:
        return self._types.get(alias.strip())

    def block_type_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "alias": item.alias,
                "name": item.name,
                "icon": item.icon,
                "category": item.category,
                "description": item.description,
                "fields": [field.__dict__ for field in item.fields],
                "sample": self.sample_block(item.alias),
            }
            for item in self.list_block_types()
        ]

    def block_type_catalog_json(self) -> str:
        return json.dumps(self.block_type_catalog(), ensure_ascii=False)

    def list_blueprints(self, content_type_alias: str = "") -> list[ContentBlueprint]:
        content_type_alias = content_type_alias.strip()
        items = self._blueprints.values()
        if content_type_alias:
            items = [
                item
                for item in items
                if not item.content_type_aliases or content_type_alias in item.content_type_aliases
            ]
        return sorted(items, key=lambda item: item.name)

    def blueprint_catalog(self, content_type_alias: str = "") -> list[dict[str, Any]]:
        return [
            {
                "alias": item.alias,
                "name": item.name,
                "content_type_aliases": list(item.content_type_aliases),
                "description": item.description,
                "blocks": self.serialize_blocks(self.parse_blocks(list(item.blocks), strict=True)),
            }
            for item in self.list_blueprints(content_type_alias)
        ]

    def blueprint_catalog_json(self, content_type_alias: str = "") -> str:
        return json.dumps(self.blueprint_catalog(content_type_alias), ensure_ascii=False)

    def sample_block(self, alias: str) -> dict[str, Any]:
        block_type = self.get_block_type(alias)
        if block_type is None:
            raise ValueError(f"Unknown Content Builder block type: {alias}")
        return {
            "id": secrets.token_urlsafe(6),
            "type": block_type.alias,
            "title": block_type.name,
            "settings": dict(block_type.sample),
        }

    def parse_blocks(self, value: Any, *, strict: bool = False) -> list[ContentBlock]:
        raw_blocks = self._raw_blocks(value, strict=strict)
        blocks: list[ContentBlock] = []
        for index, item in enumerate(raw_blocks):
            if not isinstance(item, dict):
                if strict:
                    raise ValueError(f"Content Builder block #{index + 1} must be an object")
                continue
            alias = str(item.get("type") or item.get("block_type") or "").strip()
            block_type = self.get_block_type(alias)
            if block_type is None:
                if strict:
                    raise ValueError(f"Unknown Content Builder block type: {alias or '<empty>'}")
                continue
            settings = item.get("settings")
            if not isinstance(settings, dict):
                settings = {
                    key: val
                    for key, val in item.items()
                    if key not in {"id", "block_id", "type", "block_type", "title", "order"}
                }
            clean_settings = self.normalize_settings(block_type.alias, settings, strict=strict)
            title = str(item.get("title") or block_type.name).strip() or block_type.name
            blocks.append(
                ContentBlock(
                    block_id=str(item.get("id") or item.get("block_id") or secrets.token_urlsafe(6)),
                    block_type=block_type.alias,
                    title=title,
                    settings=clean_settings,
                    order=self._safe_int(item.get("order"), index),
                )
            )
        return sorted(blocks, key=lambda block: (block.order, block.title.casefold()))

    def normalize_settings(
        self,
        block_type_alias: str,
        settings: dict[str, Any],
        *,
        strict: bool = False,
    ) -> dict[str, Any]:
        block_type = self.get_block_type(block_type_alias)
        if block_type is None:
            if strict:
                raise ValueError(f"Unknown Content Builder block type: {block_type_alias}")
            return {}

        clean: dict[str, Any] = {}
        missing: list[str] = []
        for field in block_type.fields:
            value = settings.get(field.alias, field.default)
            normalized = self._normalize_field(field, value)
            if field.required and not self._has_value(normalized):
                missing.append(field.name)
            clean[field.alias] = normalized
        if missing and strict:
            raise ValueError(f"{block_type.name}: required fields: {', '.join(missing)}")
        return clean

    def serialize_blocks(self, blocks: list[ContentBlock]) -> list[dict[str, Any]]:
        return [
            {
                "id": block.block_id,
                "type": block.block_type,
                "title": block.title,
                "order": block.order,
                "settings": block.settings,
            }
            for block in blocks
        ]

    def to_json(self, blocks: list[ContentBlock] | list[dict[str, Any]]) -> str:
        if blocks and isinstance(blocks[0], ContentBlock):
            data: Any = self.serialize_blocks(blocks)  # type: ignore[arg-type]
        else:
            data = blocks
        return json.dumps(data, ensure_ascii=False, indent=2)

    def render_blocks(self, blocks: list[ContentBlock]) -> str:
        if not blocks:
            return ""
        rendered = "\n".join(self.render_block(block) for block in blocks)
        return f'<div class="archub-builder-content">\n{rendered}\n</div>'

    def render_block(self, block: ContentBlock) -> str:
        renderer = getattr(self, f"_render_{block.block_type}", None)
        if callable(renderer):
            result = renderer(block)
            return str(result) if result is not None else ""
        return self._render_generic(block)

    def summary(self, blocks: list[ContentBlock]) -> dict[str, Any]:
        categories: dict[str, int] = {}
        words = 0
        issues = self.audit_blocks(blocks)
        for block in blocks:
            block_type_obj = self.get_block_type(block.block_type)
            category = block_type_obj.category if block_type_obj else "Custom"
            categories[category] = categories.get(category, 0) + 1
            words += len(re.findall(r"\w+", json.dumps(block.settings, ensure_ascii=False)))
        return {
            "blocks": len(blocks),
            "categories": categories,
            "estimated_words": words,
            "has_cta": any(block.block_type in {"cta", "hero", "download_card"} for block in blocks),
            "has_api": any(block.block_type == "api_tool" for block in blocks),
            "has_rag": any(block.block_type == "rag_reference" for block in blocks),
            "audit_score": self.audit_score(issues),
            "audit_issues": len(issues),
        }

    def audit_blocks(self, blocks: list[ContentBlock]) -> list[BuilderAuditIssue]:
        issues: list[BuilderAuditIssue] = []
        if not blocks:
            return [
                BuilderAuditIssue(
                    severity="warning",
                    block_id="content",
                    block_type="page",
                    message="Content Builder has no blocks.",
                )
            ]

        if not any(block.block_type == "hero" for block in blocks):
            issues.append(
                BuilderAuditIssue(
                    severity="info",
                    block_id="content",
                    block_type="page",
                    message="No hero block is present; this is fine for articles but weak for landing pages.",
                )
            )
        if not any(block.block_type in {"cta", "download_card"} for block in blocks):
            issues.append(
                BuilderAuditIssue(
                    severity="warning",
                    block_id="content",
                    block_type="page",
                    message="No conversion block found: add CTA or Download Card where appropriate.",
                )
            )

        for block in blocks:
            s = block.settings
            if block.block_type == "hero" and len(str(s.get("title") or "").strip()) < 8:
                issues.append(self._issue(block, "warning", "Hero title is too short."))
            if block.block_type == "media" and not str(s.get("alt_text") or "").strip():
                issues.append(self._issue(block, "warning", "Media block should include alt text."))
            if block.block_type == "download_card" and not str(s.get("file_url") or "").startswith("/"):
                issues.append(self._issue(block, "warning", "Download URL should be an internal absolute path."))
            if block.block_type == "api_tool" and not str(s.get("endpoint") or "").startswith("/"):
                issues.append(self._issue(block, "error", "API endpoint must start with '/'."))
            if block.block_type == "rag_reference" and not str(s.get("corpus_key") or "").strip():
                issues.append(self._issue(block, "error", "RAG Reference must include corpus_key."))
            if block.block_type == "rich_text" and len(re.sub(r"<[^>]+>", "", str(s.get("body") or "")).strip()) < 20:
                issues.append(self._issue(block, "warning", "Rich Text body is very short."))
        return issues

    @staticmethod
    def audit_score(issues: list[BuilderAuditIssue]) -> int:
        score = 100
        for issue in issues:
            if issue.severity == "error":
                score -= 25
            elif issue.severity == "warning":
                score -= 10
            else:
                score -= 3
        return max(0, score)

    @staticmethod
    def _issue(block: ContentBlock, severity: str, message: str) -> BuilderAuditIssue:
        return BuilderAuditIssue(
            severity=severity,
            block_id=block.block_id,
            block_type=block.block_type,
            message=message,
        )

    @staticmethod
    def _raw_blocks(value: Any, *, strict: bool) -> list[Any]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            try:
                data = json.loads(value)
            except json.JSONDecodeError as exc:
                if strict:
                    raise ValueError(f"Content Builder JSON is invalid: {exc.msg}") from exc
                return []
        elif isinstance(value, dict):
            data = value.get("blocks", [])
        else:
            data = value
        if isinstance(data, dict):
            data = data.get("blocks", [])
        if not isinstance(data, list):
            if strict:
                raise ValueError("Content Builder payload must be a JSON list or an object with blocks")
            return []
        return data

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _normalize_field(cls, field: BuilderField, value: Any) -> Any:
        editor = field.editor
        if editor == "checkbox":
            return cls._truthy(value)
        if editor == "number":
            try:
                return float(str(value).strip())
            except (TypeError, ValueError):
                return 0.0
        if editor == "items":
            return cls._normalize_items(value)
        if editor == "list":
            return cls._normalize_list(value)
        if editor in {"richtext", "embed"}:
            return cls._safe_html(str(value or ""))
        return str(value or "").strip()

    @staticmethod
    def _has_value(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (list, tuple, set)):
            return bool(value)
        return bool(str(value or "").strip())

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y", "да"}

    @staticmethod
    def _safe_html(value: str) -> str:
        clean = _SCRIPT_RE.sub("", value)
        clean = _EVENT_ATTR_RE.sub("", clean)
        clean = _JS_URL_RE.sub(r'\1="#"', clean)
        return clean.strip()

    @classmethod
    def _normalize_list(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value or "").strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = []
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
        return [item.strip() for item in re.split(r"[\n,]+", text) if item.strip()]

    @classmethod
    def _normalize_items(cls, value: Any) -> list[dict[str, str]]:
        if isinstance(value, str) and value.strip().startswith("["):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = value.splitlines()
        if isinstance(value, list):
            items: list[dict[str, str]] = []
            for item in value:
                if isinstance(item, dict):
                    clean = {
                        str(key): cls._safe_html(str(val or "")) if str(key) == "body" else str(val or "").strip()
                        for key, val in item.items()
                    }
                    if any(clean.values()):
                        items.append(clean)
                else:
                    parsed = cls._item_from_line(str(item))
                    if parsed:
                        items.append(parsed)
            return items
        result: list[dict[str, str]] = []
        for line in str(value or "").splitlines():
            parsed = cls._item_from_line(line)
            if parsed is not None:
                result.append(parsed)
        return result

    @staticmethod
    def _item_from_line(line: str) -> dict[str, str] | None:
        parts = [part.strip() for part in line.split("|")]
        if not any(parts):
            return None
        keys = ("title", "text", "icon", "url", "meta")
        return {key: parts[idx] for idx, key in enumerate(keys[: len(parts)]) if parts[idx]}

    @staticmethod
    def _e(value: Any) -> str:
        return html.escape(str(value or ""), quote=True)

    @staticmethod
    def _attr_url(value: Any) -> str:
        url = str(value or "").strip()
        if not url or url.lower().startswith("javascript:"):
            return "#"
        return html.escape(url, quote=True)

    @classmethod
    def _rich(cls, value: Any) -> str:
        return cls._safe_html(str(value or ""))

    @classmethod
    def _items(cls, block: ContentBlock) -> list[dict[str, str]]:
        value = block.settings.get("items")
        return value if isinstance(value, list) else []

    def _render_hero(self, block: ContentBlock) -> str:
        s = block.settings
        image = str(s.get("image_url") or "").strip()
        image_html = ""
        if image:
            image_html = (
                f'<img class="archub-block__media" src="{self._attr_url(image)}" '
                f'alt="{self._e(s.get("title"))}">'
            )
        cta_html = ""
        if s.get("cta_label") and s.get("cta_url"):
            cta_html = (
                f'<a class="btn" href="{self._attr_url(s.get("cta_url"))}">'
                f'{self._e(s.get("cta_label"))}</a>'
            )
        compact = " archub-block--compact" if s.get("compact") else ""
        return (
            f'<section class="archub-block archub-block--hero{compact}">'
            f'<div class="archub-block__copy">'
            f'<span class="badge">{self._e(s.get("eyebrow"))}</span>'
            f'<h2>{self._e(s.get("title"))}</h2>'
            f'<p>{self._e(s.get("subtitle"))}</p>{cta_html}</div>{image_html}</section>'
        )

    def _render_rich_text(self, block: ContentBlock) -> str:
        return f'<section class="archub-block archub-block--text">{self._rich(block.settings.get("body"))}</section>'

    def _render_cta(self, block: ContentBlock) -> str:
        s = block.settings
        button = ""
        if s.get("button_label") and s.get("button_url"):
            button = (
                f'<a class="btn" href="{self._attr_url(s.get("button_url"))}">'
                f'{self._e(s.get("button_label"))}</a>'
            )
        return (
            f'<section class="archub-block archub-block--cta archub-block--{self._e(s.get("tone"))}">'
            f'<h2>{self._e(s.get("title"))}</h2><p>{self._e(s.get("text"))}</p>{button}</section>'
        )

    def _render_feature_grid(self, block: ContentBlock) -> str:
        items = "".join(
            '<article class="archub-feature">'
            f'<span>{self._e(item.get("icon") or "✦")}</span>'
            f'<h3>{self._e(item.get("title"))}</h3>'
            f'<p>{self._e(item.get("text"))}</p>'
            "</article>"
            for item in self._items(block)
        )
        return (
            f'<section class="archub-block archub-block--features">'
            f'<h2>{self._e(block.settings.get("title"))}</h2>'
            f'<div class="archub-feature-grid">{items}</div></section>'
        )

    def _render_faq(self, block: ContentBlock) -> str:
        items = "".join(
            f'<details class="archub-faq"><summary>{self._e(item.get("title"))}</summary>'
            f'<p>{self._e(item.get("text"))}</p></details>'
            for item in self._items(block)
        )
        return (
            f'<section class="archub-block archub-block--faq">'
            f'<h2>{self._e(block.settings.get("title"))}</h2>{items}</section>'
        )

    def _render_quote(self, block: ContentBlock) -> str:
        return (
            '<blockquote class="archub-block archub-block--quote">'
            f'<p>{self._e(block.settings.get("quote"))}</p>'
            f'<cite>{self._e(block.settings.get("attribution"))}</cite>'
            "</blockquote>"
        )

    def _render_media(self, block: ContentBlock) -> str:
        s = block.settings
        return (
            '<figure class="archub-block archub-block--media">'
            f'<img src="{self._attr_url(s.get("media_url"))}" alt="{self._e(s.get("alt_text"))}">'
            f'<figcaption>{self._e(s.get("caption"))}</figcaption>'
            "</figure>"
        )

    def _render_api_tool(self, block: ContentBlock) -> str:
        s = block.settings
        method = self._e(str(s.get("method") or "GET").upper())
        return (
            '<section class="archub-block archub-block--api">'
            f'<span class="badge">{method}</span><h2>{self._e(s.get("title"))}</h2>'
            f'<code>{self._e(s.get("endpoint"))}</code><p>{self._e(s.get("description"))}</p>'
            f'<pre>{self._e(s.get("payload_example"))}</pre></section>'
        )

    def _render_rag_reference(self, block: ContentBlock) -> str:
        s = block.settings
        return (
            '<section class="archub-block archub-block--rag">'
            f'<span class="badge">RAG · {self._e(s.get("corpus_key"))}</span>'
            f'<h2>{self._e(s.get("title"))}</h2>'
            f'<p>{self._e(s.get("query_hint"))}</p>'
            f'<small>{self._e(s.get("tags"))}</small></section>'
        )

    def _render_expert_cards(self, block: ContentBlock) -> str:
        ids = "".join(f'<li><code>{self._e(item)}</code></li>' for item in block.settings.get("expert_ids", []))
        return (
            '<section class="archub-block archub-block--experts">'
            f'<h2>{self._e(block.settings.get("title"))}</h2><ul>{ids}</ul></section>'
        )

    def _render_pricing_table(self, block: ContentBlock) -> str:
        rows = "".join(
            '<article class="archub-price">'
            f'<h3>{self._e(item.get("title"))}</h3>'
            f'<strong>{self._e(item.get("price"))}</strong>'
            f'<span>{self._e(item.get("tokens"))}</span>'
            f'<p>{self._e(item.get("text"))}</p>'
            "</article>"
            for item in self._items(block)
        )
        return (
            '<section class="archub-block archub-block--pricing">'
            f'<h2>{self._e(block.settings.get("title"))}</h2>'
            f'<div class="archub-price-grid">{rows}</div></section>'
        )

    def _render_steps(self, block: ContentBlock) -> str:
        items = "".join(
            f'<li><strong>{self._e(item.get("title"))}</strong><span>{self._e(item.get("text"))}</span></li>'
            for item in self._items(block)
        )
        return (
            '<section class="archub-block archub-block--steps">'
            f'<h2>{self._e(block.settings.get("title"))}</h2><ol>{items}</ol></section>'
        )

    def _render_download_card(self, block: ContentBlock) -> str:
        s = block.settings
        return (
            '<section class="archub-block archub-block--download">'
            f'<h2>{self._e(s.get("title"))}</h2><p>{self._e(s.get("description"))}</p>'
            f'<a class="btn" href="{self._attr_url(s.get("file_url"))}" download>{self._e(s.get("button_label"))}</a>'
            "</section>"
        )

    def _render_embed(self, block: ContentBlock) -> str:
        return (
            '<section class="archub-block archub-block--embed">'
            f'<h2>{self._e(block.settings.get("title"))}</h2>{self._rich(block.settings.get("html"))}</section>'
        )

    def _render_metrics(self, block: ContentBlock) -> str:
        items = "".join(
            '<article class="archub-metric">'
            f'<strong>{self._e(item.get("title"))}</strong>'
            f'<span>{self._e(item.get("text"))}</span>'
            "</article>"
            for item in self._items(block)
        )
        return (
            '<section class="archub-block archub-block--metrics">'
            f'<h2>{self._e(block.settings.get("title"))}</h2>{items}</section>'
        )

    def _render_generic(self, block: ContentBlock) -> str:
        payload = self._e(json.dumps(block.settings, ensure_ascii=False, indent=2))
        return (
            '<section class="archub-block archub-block--generic">'
            f'<h2>{self._e(block.title)}</h2><pre>{payload}</pre></section>'
        )

    @staticmethod
    def _default_block_types() -> tuple[ContentBlockType, ...]:
        return (
            ContentBlockType(
                alias="hero",
                name="Hero",
                icon="H",
                category="Layout",
                description="First-screen lead section with copy, media, and CTA.",
                fields=(
                    BuilderField("eyebrow", "Eyebrow", default="ArcHub"),
                    BuilderField("title", "Title", required=True, default="New ArcHub page"),
                    BuilderField("subtitle", "Subtitle", "textarea"),
                    BuilderField("cta_label", "CTA label", default="Open"),
                    BuilderField("cta_url", "CTA URL", "url", default="/consultations"),
                    BuilderField("image_url", "Image URL", "url"),
                    BuilderField("alignment", "Alignment", "select", default="left", options=("left", "center")),
                    BuilderField("compact", "Compact", "checkbox", default=False),
                ),
                sample={
                    "eyebrow": "ArcHub CMS",
                    "title": "Editable bot experience",
                    "subtitle": "Publish pages, expert materials, API tools, and RAG corpus resources from one CMS.",
                    "cta_label": "Start consultation",
                    "cta_url": "/consultations",
                    "image_url": "",
                    "alignment": "left",
                    "compact": False,
                },
            ),
            ContentBlockType(
                alias="rich_text",
                name="Rich Text",
                icon="T",
                category="Content",
                description="Long-form editorial HTML content.",
                fields=(BuilderField("body", "Body", "richtext", True, default="<p>Editable rich text.</p>"),),
                sample={"body": "<p>Editable rich text block with links, headings, and inline formatting.</p>"},
            ),
            ContentBlockType(
                alias="cta",
                name="Call To Action",
                icon="A",
                category="Marketing",
                description="Compact conversion block with a button.",
                fields=(
                    BuilderField("title", "Title", required=True, default="Ready to continue?"),
                    BuilderField("text", "Text", "textarea"),
                    BuilderField("button_label", "Button label", default="Continue"),
                    BuilderField("button_url", "Button URL", "url", default="/experts"),
                    BuilderField("tone", "Tone", "select", default="primary", options=("primary", "neutral", "warning")),
                ),
                sample={
                    "title": "Ready to continue?",
                    "text": "Open a consultation and keep the conversation context in ArcHub.",
                    "button_label": "Choose expert",
                    "button_url": "/experts",
                    "tone": "primary",
                },
            ),
            ContentBlockType(
                alias="feature_grid",
                name="Feature Grid",
                icon="G",
                category="Content",
                description="Responsive cards for capabilities, advantages, or content sections.",
                fields=(
                    BuilderField("title", "Title", default="Capabilities"),
                    BuilderField("items", "Items", "items"),
                ),
                sample={
                    "title": "CMS capabilities",
                    "items": [
                        {"icon": "CMS", "title": "Drafts", "text": "Edit and publish versioned content."},
                        {"icon": "RAG", "title": "Corpora", "text": "Curate expert-specific knowledge materials."},
                        {"icon": "API", "title": "Tools", "text": "Describe backend APIs used by AI experts."},
                    ],
                },
            ),
            ContentBlockType(
                alias="faq",
                name="FAQ",
                icon="?",
                category="Support",
                description="Frequently asked questions with expandable answers.",
                fields=(
                    BuilderField("title", "Title", default="FAQ"),
                    BuilderField("items", "Questions", "items"),
                ),
                sample={
                    "title": "FAQ",
                    "items": [
                        {"title": "Can I edit RAG materials?", "text": "Yes, publish RAG materials in ArcHub CMS."},
                        {"title": "Can experts use backend APIs?", "text": "Yes, API tools are cataloged as content blocks."},
                    ],
                },
            ),
            ContentBlockType(
                alias="quote",
                name="Quote",
                icon="Q",
                category="Content",
                description="Pull quote or testimonial.",
                fields=(
                    BuilderField("quote", "Quote", "textarea", True),
                    BuilderField("attribution", "Attribution"),
                ),
                sample={"quote": "Content and runtime knowledge should be governed in one place.", "attribution": "ArcHub"},
            ),
            ContentBlockType(
                alias="media",
                name="Media",
                icon="M",
                category="Media",
                description="Image with alt text and caption.",
                fields=(
                    BuilderField("media_url", "Media URL", "url", True),
                    BuilderField("alt_text", "Alt text"),
                    BuilderField("caption", "Caption"),
                    BuilderField("layout", "Layout", "select", default="wide", options=("wide", "inline")),
                ),
                sample={"media_url": "/static/favicon.svg", "alt_text": "ArcHub media", "caption": "Managed media asset."},
            ),
            ContentBlockType(
                alias="api_tool",
                name="API Tool",
                icon="API",
                category="Runtime",
                description="Catalog entry for a backend API capability available to AI experts.",
                fields=(
                    BuilderField("title", "Title", required=True, default="Natal chart PDF"),
                    BuilderField("endpoint", "Endpoint", required=True, default="/api/v1/reports/natal-pdf"),
                    BuilderField("method", "Method", "select", default="POST", options=("GET", "POST", "PUT", "DELETE")),
                    BuilderField("description", "Description", "textarea"),
                    BuilderField("payload_example", "Payload example", "code"),
                ),
                sample={
                    "title": "Natal chart PDF",
                    "endpoint": "/api/v1/reports/natal-pdf",
                    "method": "POST",
                    "description": "Generates a downloadable natal chart report.",
                    "payload_example": '{"profile_id": "...", "school": "vedic"}',
                },
            ),
            ContentBlockType(
                alias="rag_reference",
                name="RAG Reference",
                icon="RAG",
                category="Runtime",
                description="RAG corpus hint for expert answers and editorial pages.",
                fields=(
                    BuilderField("title", "Title", default="Knowledge source"),
                    BuilderField("corpus_key", "Corpus key", required=True, default="vedic"),
                    BuilderField("query_hint", "Query hint", "textarea"),
                    BuilderField("tags", "Tags"),
                ),
                sample={
                    "title": "Vedic natal interpretation",
                    "corpus_key": "vedic",
                    "query_hint": "Use lagna, graha, bhava, dasha, and varga materials first.",
                    "tags": "jyotish, natal, dasha",
                },
            ),
            ContentBlockType(
                alias="expert_cards",
                name="Expert Cards",
                icon="E",
                category="Runtime",
                description="References to AI experts by stable expert IDs.",
                fields=(
                    BuilderField("title", "Title", default="Recommended experts"),
                    BuilderField("expert_ids", "Expert IDs", "list", default="exp_indubala"),
                ),
                sample={"title": "Recommended experts", "expert_ids": ["exp_indubala", "exp_numerology"]},
            ),
            ContentBlockType(
                alias="pricing_table",
                name="Pricing Table",
                icon="$",
                category="Commerce",
                description="Token subscription and package table.",
                fields=(
                    BuilderField("title", "Title", default="Token plans"),
                    BuilderField("items", "Plans", "items"),
                ),
                sample={
                    "title": "Token plans",
                    "items": [
                        {"title": "Starter", "tokens": "1 000 tokens", "price": "Free", "text": "For testing."},
                        {"title": "Expert", "tokens": "25 000 tokens", "price": "$19", "text": "For active consultations."},
                    ],
                },
            ),
            ContentBlockType(
                alias="steps",
                name="Steps",
                icon="1",
                category="Content",
                description="Ordered process, onboarding, or workflow.",
                fields=(
                    BuilderField("title", "Title", default="How it works"),
                    BuilderField("items", "Steps", "items"),
                ),
                sample={
                    "title": "How it works",
                    "items": [
                        {"title": "Create profile", "text": "Save birth data in the bot web interface."},
                        {"title": "Ask expert", "text": "The expert checks RAG and backend APIs before LLM synthesis."},
                    ],
                },
            ),
            ContentBlockType(
                alias="download_card",
                name="Download Card",
                icon="D",
                category="Media",
                description="Downloadable file card for reports, PDFs, and exports.",
                fields=(
                    BuilderField("title", "Title", required=True, default="Download report"),
                    BuilderField("description", "Description", "textarea"),
                    BuilderField("file_url", "File URL", "url", required=True),
                    BuilderField("button_label", "Button label", default="Download"),
                ),
                sample={
                    "title": "Download report",
                    "description": "Prepared PDF report from the backend.",
                    "file_url": "/static/reports/example.pdf",
                    "button_label": "Download PDF",
                },
            ),
            ContentBlockType(
                alias="embed",
                name="Embed",
                icon="<>",
                category="Integration",
                description="Safe embed block for widgets and external HTML snippets.",
                fields=(
                    BuilderField("title", "Title"),
                    BuilderField("html", "HTML", "embed"),
                ),
                sample={"title": "Embedded widget", "html": "<div>External widget placeholder</div>"},
            ),
            ContentBlockType(
                alias="metrics",
                name="Metrics",
                icon="#",
                category="Analytics",
                description="KPI strip for product, runtime, or content metrics.",
                fields=(
                    BuilderField("title", "Title", default="Metrics"),
                    BuilderField("items", "Metrics", "items"),
                ),
                sample={
                    "title": "Runtime coverage",
                    "items": [
                        {"title": "3000+", "text": "Backend API capabilities"},
                        {"title": "RAG", "text": "Expert-specific corpora"},
                        {"title": "CMS", "text": "Versioned runtime content"},
                    ],
                },
            ),
        )

    @staticmethod
    def _default_blueprints() -> tuple[ContentBlueprint, ...]:
        return (
            ContentBlueprint(
                alias="bot_landing_full",
                name="Bot Landing Full Funnel",
                content_type_aliases=("bot_landing", "page"),
                description="Hero, capabilities, API/RAG runtime proof, FAQ and CTA for a bot product page.",
                blocks=(
                    {
                        "type": "hero",
                        "title": "Hero",
                        "settings": {
                            "eyebrow": "ArcHub CMS",
                            "title": "AI expert consultation platform",
                            "subtitle": "Editable landing page with runtime APIs and expert-specific RAG corpus materials.",
                            "cta_label": "Choose expert",
                            "cta_url": "/experts",
                        },
                    },
                    {
                        "type": "feature_grid",
                        "title": "Feature Grid",
                        "settings": {
                            "title": "Platform capabilities",
                            "items": [
                                {"icon": "CMS", "title": "Published content", "text": "Versioned pages and bot resources."},
                                {"icon": "RAG", "title": "Expert corpora", "text": "Separate knowledge bases per consultant."},
                                {"icon": "API", "title": "Backend tools", "text": "Structured API capabilities before LLM synthesis."},
                            ],
                        },
                    },
                    {
                        "type": "api_tool",
                        "title": "API Tool",
                        "settings": {
                            "title": "Natal chart PDF",
                            "endpoint": "/api/v1/reports/natal-pdf",
                            "method": "POST",
                            "description": "Generates a downloadable report from a saved astro profile.",
                            "payload_example": '{"profile_id": "...", "school": "vedic"}',
                        },
                    },
                    {
                        "type": "rag_reference",
                        "title": "RAG Reference",
                        "settings": {
                            "title": "Expert knowledge corpus",
                            "corpus_key": "vedic",
                            "query_hint": "Use the expert-specific corpus before LLM synthesis.",
                            "tags": "jyotish, natal, reports",
                        },
                    },
                    {
                        "type": "faq",
                        "title": "FAQ",
                        "settings": {
                            "title": "FAQ",
                            "items": [
                                {"title": "Can content be edited?", "text": "Yes, editors publish pages and runtime resources in ArcHub."},
                                {"title": "Can experts produce files?", "text": "Yes, API tools can be represented as downloadable report flows."},
                            ],
                        },
                    },
                    {
                        "type": "cta",
                        "title": "CTA",
                        "settings": {
                            "title": "Start a consultation",
                            "text": "The expert will use profile data, RAG, APIs and then final LLM synthesis.",
                            "button_label": "Open experts",
                            "button_url": "/experts",
                        },
                    },
                ),
            ),
            ContentBlueprint(
                alias="rag_article",
                name="RAG Knowledge Article",
                content_type_aliases=("knowledge_article", "page"),
                description="Editorial article with knowledge source marker, FAQ and related expert CTA.",
                blocks=(
                    {
                        "type": "rich_text",
                        "title": "Article Body",
                        "settings": {
                            "body": "<h2>Core concept</h2><p>Explain the concept with source-grounded terminology.</p>",
                        },
                    },
                    {
                        "type": "rag_reference",
                        "title": "RAG Source",
                        "settings": {
                            "title": "RAG source",
                            "corpus_key": "vedic",
                            "query_hint": "Tie this article to the matching expert corpus material.",
                            "tags": "knowledge, corpus",
                        },
                    },
                    {
                        "type": "faq",
                        "title": "FAQ",
                        "settings": {
                            "title": "FAQ",
                            "items": [
                                {"title": "How is this used by the expert?", "text": "Published materials can be exported into expert-specific RAG indexes."},
                                {"title": "Can it be versioned?", "text": "Yes, every save/publish creates a content version."},
                            ],
                        },
                    },
                    {
                        "type": "cta",
                        "title": "CTA",
                        "settings": {
                            "title": "Ask an AI expert",
                            "text": "Use this article as grounded context in a consultation.",
                            "button_label": "Open consultation",
                            "button_url": "/consultations",
                        },
                    },
                ),
            ),
            ContentBlueprint(
                alias="expert_profile",
                name="Expert Profile",
                content_type_aliases=("expert_page", "page"),
                description="Public expert page with profile intro, expertise cards, RAG marker and CTA.",
                blocks=(
                    {
                        "type": "hero",
                        "title": "Expert Hero",
                        "settings": {
                            "eyebrow": "AI expert",
                            "title": "Expert consultation",
                            "subtitle": "A focused consultant page with school, corpus and capabilities.",
                            "cta_label": "Start chat",
                            "cta_url": "/experts",
                        },
                    },
                    {
                        "type": "feature_grid",
                        "title": "Expertise",
                        "settings": {
                            "title": "Expertise",
                            "items": [
                                {"icon": "1", "title": "School", "text": "Clearly stated astrology or numerology school."},
                                {"icon": "2", "title": "RAG", "text": "Separate corpus aligned to this expert."},
                                {"icon": "3", "title": "Tools", "text": "Backend API tools used before LLM synthesis."},
                            ],
                        },
                    },
                    {
                        "type": "expert_cards",
                        "title": "Expert IDs",
                        "settings": {"title": "Related experts", "expert_ids": ["exp_indubala"]},
                    },
                    {
                        "type": "cta",
                        "title": "CTA",
                        "settings": {
                            "title": "Continue with this expert",
                            "text": "Open a consultation with saved profile context.",
                            "button_label": "Open experts",
                            "button_url": "/experts",
                        },
                    },
                ),
            ),
            ContentBlueprint(
                alias="download_report",
                name="Downloadable Report",
                content_type_aliases=("page", "bot_landing"),
                description="Page pattern for PDF/report generation via backend API and chat download.",
                blocks=(
                    {
                        "type": "hero",
                        "title": "Report Hero",
                        "settings": {
                            "eyebrow": "Reports",
                            "title": "Generate a downloadable report",
                            "subtitle": "Backend API creates the file; ArcHub presents it as managed content.",
                            "cta_label": "Open profile",
                            "cta_url": "/astro-profile",
                        },
                    },
                    {
                        "type": "api_tool",
                        "title": "Report API",
                        "settings": {
                            "title": "Report generation API",
                            "endpoint": "/api/v1/reports",
                            "method": "POST",
                            "description": "Creates report artifacts from saved profile and selected school.",
                            "payload_example": '{"profile_id": "...", "report_type": "natal"}',
                        },
                    },
                    {
                        "type": "download_card",
                        "title": "Download Card",
                        "settings": {
                            "title": "Download PDF",
                            "description": "Attach generated report artifact to the chat or public page.",
                            "file_url": "/static/reports/example.pdf",
                            "button_label": "Download PDF",
                        },
                    },
                ),
            ),
        )


@cache
def get_archub_content_builder_service() -> ArcHubContentBuilderService:
    return ArcHubContentBuilderService()
