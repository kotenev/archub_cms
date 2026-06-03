"""ArcHub CMS storage and content model.

The design intentionally mirrors the useful Umbraco concepts that fit this
FastAPI platform: document types, a hierarchical content tree, draft/published
state, version history, and a read-only published-content surface.
"""
from __future__ import annotations

__all__ = [
    "ArcHubCMSService",
    "ContentActivity",
    "ContentAuditIssue",
    "ContentBlueprint",
    "ContentField",
    "ContentComposition",
    "ContentDataType",
    "ContentDomain",
    "ContentLock",
    "ContentNode",
    "ContentAccessRule",
    "ContentPermissionRule",
    "ContentPreviewToken",
    "ContentRedirect",
    "ContentSegment",
    "ContentTemplate",
    "ContentType",
    "ContentVariant",
    "ContentVersion",
    "ContentWebhook",
    "ContentWorkflow",
    "MediaAsset",
    "WebhookDelivery",
    "get_archub_cms_service",
]

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

logger = logging.getLogger("archub_cms")

_ROOT_NODE_ID = "root"
_PUBLIC_ROOT = "/cms"
_STATUS_DRAFT = "draft"
_STATUS_PUBLISHED = "published"
_STATUS_UNPUBLISHED = "unpublished"
_STATUS_TRASHED = "trashed"
_WORKFLOW_STATES = {
    "draft",
    "in_review",
    "approved",
    "changes_requested",
    "scheduled",
    "published",
    "unpublished",
    "archived",
    "trashed",
}
_MANAGED_CONTENT_ALIASES = ("ai_expert", "rag_material", "bot_resource")
_RESOURCE_SUFFIXES = {".json", ".md", ".txt", ".yaml", ".yml"}
_DEFAULT_RUNTIME_EXPORT_DIR = "data/archub_runtime"
_VALID_SCHOOLS = {"vedic", "western", "tarot", "numerology", "chinese", "human_design"}
_CMS_LINK_RE = re.compile(r"""(?:href=\\?["']|]\()(?P<path>/cms(?:/[^"')\s#?\\]*)?)""")
_CULTURE_RE = re.compile(r"^[a-z]{2}(?:-[a-z0-9]{2,8})?$", re.IGNORECASE)
_SEGMENT_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_CONTENT_PERMISSION_ACTIONS = (
    "browse",
    "create",
    "update",
    "publish",
    "delete",
    "workflow",
    "model",
    "media",
    "settings",
    "admin",
)
_PUBLIC_ACCESS_POLICIES = ("public", "authenticated", "members")
_HOSTNAME_RE = re.compile(r"^(?:\*|\*\.[a-z0-9][a-z0-9.-]{0,252}|localhost|[a-z0-9][a-z0-9.-]{0,252})$")
_PACKAGE_SCHEMA_VERSION = "archub.package.v1"


@dataclass(frozen=True)
class ContentActivity:
    activity_id: int
    node_id: str
    action: str
    actor: str
    summary: str
    metadata: dict[str, Any]
    created_at: float
    node_name: str
    route_path: str
    content_type_alias: str


@dataclass(frozen=True)
class ContentBlueprint:
    blueprint_id: str
    content_type_alias: str
    name: str
    description: str
    payload: dict[str, Any]
    created_at: float
    updated_at: float
    updated_by: str


@dataclass(frozen=True)
class ContentWebhook:
    webhook_id: str
    name: str
    target_url: str
    events: tuple[str, ...]
    active: bool
    timeout_seconds: float
    max_attempts: int
    secret_set: bool
    created_at: float
    updated_at: float
    created_by: str
    updated_by: str


@dataclass(frozen=True)
class WebhookDelivery:
    delivery_id: int
    webhook_id: str
    webhook_name: str
    target_url: str
    event_type: str
    aggregate_id: str
    payload: dict[str, Any]
    status: str
    attempts: int
    next_attempt_at: float
    last_error: str
    created_at: float
    updated_at: float
    delivered_at: float | None


@dataclass(frozen=True)
class ContentAuditIssue:
    node_id: str
    route_path: str
    content_type_alias: str
    severity: str
    message: str


@dataclass(frozen=True)
class ContentField:
    alias: str
    name: str
    editor: str = "text"
    required: bool = False
    help_text: str = ""
    default: str = ""
    data_type_alias: str = ""
    config: dict[str, Any] = dataclass_field(default_factory=dict)
    validation: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(frozen=True)
class ContentDataType:
    alias: str
    name: str
    editor: str
    description: str
    config: dict[str, Any]
    validation: dict[str, Any]
    created_at: float
    updated_at: float
    updated_by: str


@dataclass(frozen=True)
class ContentDomain:
    domain_id: str
    hostname: str
    root_node_id: str
    root_name: str
    root_route_path: str
    culture: str
    is_default: bool
    secure: bool
    sort_order: int
    created_at: float
    updated_at: float
    updated_by: str


@dataclass(frozen=True)
class ContentComposition:
    alias: str
    name: str
    description: str
    fields: tuple[ContentField, ...]
    created_at: float
    updated_at: float
    updated_by: str


@dataclass(frozen=True)
class ContentLock:
    node_id: str
    owner: str
    token: str
    note: str
    acquired_at: float
    expires_at: float
    node_name: str
    route_path: str
    content_type_alias: str


@dataclass(frozen=True)
class ContentPermissionRule:
    rule_id: str
    subject: str
    scope_node_id: str
    actions: tuple[str, ...]
    include_descendants: bool
    note: str
    created_at: float
    updated_at: float
    updated_by: str
    node_name: str
    route_path: str
    content_type_alias: str


@dataclass(frozen=True)
class ContentAccessRule:
    node_id: str
    policy: str
    member_groups: tuple[str, ...]
    include_descendants: bool
    login_path: str
    denied_path: str
    note: str
    updated_at: float
    updated_by: str
    node_name: str
    route_path: str
    content_type_alias: str


@dataclass(frozen=True)
class ContentTemplate:
    alias: str
    name: str
    view: str
    description: str
    allowed_content_type_aliases: tuple[str, ...]
    config: dict[str, Any]
    created_at: float
    updated_at: float
    updated_by: str


@dataclass(frozen=True)
class ContentPreviewToken:
    token_hash: str
    node_id: str
    node_name: str
    route_path: str
    content_type_alias: str
    created_by: str
    created_at: float
    expires_at: float
    revoked_at: float | None
    revoked_by: str
    note: str

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > _now()


@dataclass(frozen=True)
class ContentType:
    alias: str
    name: str
    icon: str
    description: str
    fields: tuple[ContentField, ...]
    allowed_child_aliases: tuple[str, ...]
    composition_aliases: tuple[str, ...] = ()
    allow_at_root: bool = False
    is_element: bool = False
    template: str = "page"
    created_at: float = 0.0
    updated_at: float = 0.0

    def field(self, alias: str) -> ContentField | None:
        for item in self.fields:
            if item.alias == alias:
                return item
        return None


@dataclass(frozen=True)
class ContentNode:
    node_id: str
    parent_id: str | None
    content_type_alias: str
    name: str
    slug: str
    route_path: str
    level: int
    status: str
    draft: dict[str, Any]
    published: dict[str, Any]
    sort_order: int
    created_at: float
    updated_at: float
    published_at: float | None
    created_by: str
    updated_by: str

    @property
    def is_root(self) -> bool:
        return self.node_id == _ROOT_NODE_ID

    @property
    def is_published(self) -> bool:
        return self.status == _STATUS_PUBLISHED and bool(self.published)


@dataclass(frozen=True)
class ContentVersion:
    version_id: int
    node_id: str
    version_no: int
    status: str
    payload: dict[str, Any]
    created_at: float
    created_by: str
    note: str


@dataclass(frozen=True)
class ContentVariant:
    node_id: str
    culture: str
    status: str
    draft: dict[str, Any]
    published: dict[str, Any]
    created_at: float
    updated_at: float
    published_at: float | None
    updated_by: str


@dataclass(frozen=True)
class ContentSegment:
    node_id: str
    segment: str
    status: str
    draft: dict[str, Any]
    published: dict[str, Any]
    created_at: float
    updated_at: float
    published_at: float | None
    updated_by: str


@dataclass(frozen=True)
class MediaAsset:
    asset_id: str
    filename: str
    original_name: str
    content_type: str
    url: str
    folder: str
    alt_text: str
    tags: tuple[str, ...]
    metadata: dict[str, Any]
    created_at: float
    created_by: str


@dataclass(frozen=True)
class ContentRedirect:
    redirect_id: str
    source_path: str
    target_path: str
    status_code: int
    active: bool
    note: str
    created_at: float
    updated_at: float
    created_by: str
    updated_by: str


@dataclass(frozen=True)
class ContentWorkflow:
    node_id: str
    state: str
    assigned_to: str
    scheduled_publish_at: float | None
    scheduled_unpublish_at: float | None
    note: str
    updated_at: float
    updated_by: str


def _now() -> float:
    return time.time()


def _iso_datetime(ts: float | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(float(ts), UTC).isoformat().replace("+00:00", "Z")


def _json_loads_dict(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _json_loads_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _json_dict_from_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        return _json_loads_dict(value)
    return {}


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _slugify(value: str, fallback: str = "content") -> str:
    slug = value.strip().lower().replace("ё", "е")
    slug = re.sub(r"[^0-9a-zа-я]+", "-", slug, flags=re.IGNORECASE)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or fallback


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y", "да"}


def _csv(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _lines(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _normalize_culture(value: str) -> str:
    culture = str(value or "").strip().replace("_", "-").lower()
    if not culture:
        return ""
    if not _CULTURE_RE.fullmatch(culture):
        raise ValueError("Culture must look like ru, en, en-us or pt-br")
    return culture


def _normalize_segment(value: str) -> str:
    segment = str(value or "").strip().replace(" ", "-").lower()
    segment = re.sub(r"[^a-z0-9_-]+", "-", segment).strip("-_")
    if not segment:
        raise ValueError("Segment is required")
    if not _SEGMENT_RE.fullmatch(segment):
        raise ValueError("Segment must match [a-z][a-z0-9_-]{0,63}")
    return segment


def _markdown_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def _relative_source_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve())).replace(os.sep, "/")
    except ValueError:
        return str(path)


def _runtime_export_dir(export_dir: Path | str | None = None) -> Path:
    return Path(export_dir or os.getenv("ARCHUB_RUNTIME_EXPORT_DIR", _DEFAULT_RUNTIME_EXPORT_DIR))


def _normalize_corpus_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    safe = re.sub(r"[^a-zа-я0-9_ -]+", "", raw).strip().replace(" ", "_")
    safe = safe.replace("-", "_")
    aliases = {
        "bazi": "chinese",
        "бацзы": "chinese",
        "hd": "human_design",
        "human-design": "human_design",
        "human_design": "human_design",
        "indubala": "vedic",
        "jyotish": "vedic",
        "vedic_jyotish": "vedic",
    }
    return aliases.get(safe, safe)


def _search_tokens(query: str) -> list[str]:
    return re.findall(r"[0-9A-Za-zА-Яа-яЁё_]{3,}", query.casefold())


def _token_in_text(token: str, text: str) -> bool:
    if token in text:
        return True
    return bool(len(token) >= 5 and token[:4] in text)


def _plain_text(value: Any) -> str:
    return re.sub(r"<[^>]+>", " ", str(value or "")).strip()


def _internal_cms_links(payload: dict[str, Any]) -> set[str]:
    text = _json_dumps(payload)
    return {
        match.group("path").rstrip("/") or _PUBLIC_ROOT
        for match in _CMS_LINK_RE.finditer(text)
    }


def _content_tags(payload: dict[str, Any]) -> tuple[str, ...]:
    raw = payload.get("tags") or payload.get("tag") or ""
    if isinstance(raw, (list, tuple, set)):
        values = [str(item) for item in raw]
    else:
        values = re.split(r"[,;\n]+", str(raw))
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        tag = value.strip()
        key = tag.casefold()
        if tag and key not in seen:
            seen.add(key)
            out.append(tag)
    return tuple(out)


def _content_title(node: ContentNode, payload: dict[str, Any]) -> str:
    return str(payload.get("title") or payload.get("hero_title") or node.name).strip()


def _content_summary(payload: dict[str, Any], limit: int = 220) -> str:
    text = str(
        payload.get("seo_description")
        or payload.get("summary")
        or payload.get("excerpt")
        or payload.get("headline")
        or payload.get("hero_text")
        or _plain_text(payload.get("body"))
        or ""
    ).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dumps(payload), encoding="utf-8")


def _markdown_file(path: Path, *, title: str, body: str, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front_matter = "\n".join(f"{key}: {value}" for key, value in metadata.items() if str(value).strip())
    text = f"---\n{front_matter}\n---\n\n# {title}\n\n{body.strip()}\n"
    path.write_text(text, encoding="utf-8")


def _route_for(parent_route: str | None, slug: str) -> str:
    if not slug:
        return _PUBLIC_ROOT
    base = (parent_route or _PUBLIC_ROOT).rstrip("/")
    return f"{base}/{slug}"


def _field_from_dict(item: dict[str, Any]) -> ContentField:
    return ContentField(
        alias=str(item.get("alias") or "").strip(),
        name=str(item.get("name") or "").strip(),
        editor=str(item.get("editor") or "").strip(),
        required=bool(item.get("required")),
        help_text=str(item.get("help_text") or item.get("help") or "").strip(),
        default=str(item.get("default") or ""),
        data_type_alias=str(item.get("data_type_alias") or item.get("dataTypeAlias") or "").strip(),
        config=_json_dict_from_value(item.get("config")),
        validation=_json_dict_from_value(item.get("validation")),
    )


def _fields_from_schema(raw: str | None) -> tuple[ContentField, ...]:
    raw_fields = _json_loads_list(str(raw or "[]"))
    return tuple(
        field for field in (_field_from_dict(item) for item in raw_fields if isinstance(item, dict))
        if field.alias and field.name
    )


def _composition_from_row(row: sqlite3.Row) -> ContentComposition:
    return ContentComposition(
        alias=str(row["alias"]),
        name=str(row["name"]),
        description=str(row["description"] or ""),
        fields=_fields_from_schema(str(row["schema_json"] or "[]")),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        updated_by=str(row["updated_by"] or ""),
    )


def _data_type_from_row(row: sqlite3.Row) -> ContentDataType:
    return ContentDataType(
        alias=str(row["alias"] or ""),
        name=str(row["name"] or ""),
        editor=str(row["editor"] or "text"),
        description=str(row["description"] or ""),
        config=_json_loads_dict(str(row["config_json"] or "{}")),
        validation=_json_loads_dict(str(row["validation_json"] or "{}")),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        updated_by=str(row["updated_by"] or ""),
    )


def _domain_from_row(row: sqlite3.Row) -> ContentDomain:
    return ContentDomain(
        domain_id=str(row["domain_id"] or ""),
        hostname=str(row["hostname"] or ""),
        root_node_id=str(row["root_node_id"] or ""),
        root_name=str(row["root_name"] or ""),
        root_route_path=str(row["root_route_path"] or ""),
        culture=str(row["culture"] or ""),
        is_default=bool(row["is_default"]),
        secure=bool(row["secure"]),
        sort_order=int(row["sort_order"] or 0),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        updated_by=str(row["updated_by"] or ""),
    )


def _template_from_row(row: sqlite3.Row) -> ContentTemplate:
    aliases = tuple(
        str(item).strip()
        for item in _json_loads_list(str(row["allowed_content_type_aliases_json"] or "[]"))
        if str(item).strip()
    )
    return ContentTemplate(
        alias=str(row["alias"] or ""),
        name=str(row["name"] or ""),
        view=str(row["view"] or "archub_public.html"),
        description=str(row["description"] or ""),
        allowed_content_type_aliases=aliases,
        config=_json_loads_dict(str(row["config_json"] or "{}")),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        updated_by=str(row["updated_by"] or ""),
    )


def _preview_token_from_row(row: sqlite3.Row) -> ContentPreviewToken:
    return ContentPreviewToken(
        token_hash=str(row["token_hash"] or ""),
        node_id=str(row["node_id"] or ""),
        node_name=str(row["node_name"] or ""),
        route_path=str(row["route_path"] or ""),
        content_type_alias=str(row["content_type_alias"] or ""),
        created_by=str(row["created_by"] or ""),
        created_at=float(row["created_at"] or 0.0),
        expires_at=float(row["expires_at"] or 0.0),
        revoked_at=float(row["revoked_at"]) if row["revoked_at"] is not None else None,
        revoked_by=str(row["revoked_by"] or ""),
        note=str(row["note"] or ""),
    )


def _type_from_row(row: sqlite3.Row) -> ContentType:
    fields = _fields_from_schema(str(row["schema_json"] or "[]"))
    allowed = tuple(
        str(item) for item in _json_loads_list(str(row["allowed_child_aliases_json"] or "[]"))
        if str(item)
    )
    composition_aliases = tuple(
        str(item) for item in _json_loads_list(str(row["composition_aliases_json"] or "[]"))
        if str(item)
    )
    return ContentType(
        alias=str(row["alias"]),
        name=str(row["name"]),
        icon=str(row["icon"] or ""),
        description=str(row["description"] or ""),
        fields=fields,
        allowed_child_aliases=allowed,
        composition_aliases=composition_aliases,
        allow_at_root=bool(row["allow_at_root"]),
        is_element=bool(row["is_element"]),
        template=str(row["template"] or "page"),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
    )


def _node_from_row(row: sqlite3.Row) -> ContentNode:
    return ContentNode(
        node_id=str(row["node_id"]),
        parent_id=str(row["parent_id"]) if row["parent_id"] is not None else None,
        content_type_alias=str(row["content_type_alias"]),
        name=str(row["name"]),
        slug=str(row["slug"] or ""),
        route_path=str(row["route_path"]),
        level=int(row["level"] or 0),
        status=str(row["status"] or _STATUS_DRAFT),
        draft=_json_loads_dict(str(row["draft_json"] or "{}")),
        published=_json_loads_dict(str(row["published_json"] or "{}")),
        sort_order=int(row["sort_order"] or 0),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        published_at=float(row["published_at"]) if row["published_at"] is not None else None,
        created_by=str(row["created_by"] or ""),
        updated_by=str(row["updated_by"] or ""),
    )


def _redirect_from_row(row: sqlite3.Row) -> ContentRedirect:
    return ContentRedirect(
        redirect_id=str(row["redirect_id"]),
        source_path=str(row["source_path"]),
        target_path=str(row["target_path"]),
        status_code=int(row["status_code"] or 301),
        active=bool(row["active"]),
        note=str(row["note"] or ""),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        created_by=str(row["created_by"] or ""),
        updated_by=str(row["updated_by"] or ""),
    )


def _workflow_from_row(row: sqlite3.Row) -> ContentWorkflow:
    return ContentWorkflow(
        node_id=str(row["node_id"]),
        state=str(row["state"] or "draft"),
        assigned_to=str(row["assigned_to"] or ""),
        scheduled_publish_at=(
            float(row["scheduled_publish_at"]) if row["scheduled_publish_at"] is not None else None
        ),
        scheduled_unpublish_at=(
            float(row["scheduled_unpublish_at"]) if row["scheduled_unpublish_at"] is not None else None
        ),
        note=str(row["note"] or ""),
        updated_at=float(row["updated_at"] or 0.0),
        updated_by=str(row["updated_by"] or ""),
    )


def _activity_from_row(row: sqlite3.Row) -> ContentActivity:
    metadata = _json_loads_dict(str(row["metadata_json"] or "{}"))
    return ContentActivity(
        activity_id=int(row["activity_id"] or 0),
        node_id=str(row["node_id"] or ""),
        action=str(row["action"] or ""),
        actor=str(row["actor"] or ""),
        summary=str(row["summary"] or ""),
        metadata=metadata,
        created_at=float(row["created_at"] or 0.0),
        node_name=str(row["node_name"] or metadata.get("node_name") or ""),
        route_path=str(row["node_route_path"] or metadata.get("route_path") or ""),
        content_type_alias=str(
            row["node_content_type_alias"] or metadata.get("content_type_alias") or ""
        ),
    )


def _blueprint_from_row(row: sqlite3.Row) -> ContentBlueprint:
    return ContentBlueprint(
        blueprint_id=str(row["blueprint_id"] or ""),
        content_type_alias=str(row["content_type_alias"] or ""),
        name=str(row["name"] or ""),
        description=str(row["description"] or ""),
        payload=_json_loads_dict(str(row["payload_json"] or "{}")),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        updated_by=str(row["updated_by"] or ""),
    )


def _webhook_from_row(row: sqlite3.Row) -> ContentWebhook:
    return ContentWebhook(
        webhook_id=str(row["webhook_id"]),
        name=str(row["name"]),
        target_url=str(row["target_url"]),
        events=tuple(str(item) for item in _json_loads_list(str(row["events_json"] or "[]"))),
        active=bool(row["active"]),
        timeout_seconds=float(row["timeout_seconds"] or 5.0),
        max_attempts=max(1, int(row["max_attempts"] or 5)),
        secret_set=bool(str(row["secret"] or "")),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        created_by=str(row["created_by"] or ""),
        updated_by=str(row["updated_by"] or ""),
    )


def _delivery_from_row(row: sqlite3.Row) -> WebhookDelivery:
    return WebhookDelivery(
        delivery_id=int(row["delivery_id"] or 0),
        webhook_id=str(row["webhook_id"] or ""),
        webhook_name=str(row["webhook_name"] or ""),
        target_url=str(row["target_url"] or ""),
        event_type=str(row["event_type"] or ""),
        aggregate_id=str(row["aggregate_id"] or ""),
        payload=_json_loads_dict(str(row["payload_json"] or "{}")),
        status=str(row["status"] or "pending"),
        attempts=int(row["attempts"] or 0),
        next_attempt_at=float(row["next_attempt_at"] or 0.0),
        last_error=str(row["last_error"] or ""),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        delivered_at=float(row["delivered_at"]) if row["delivered_at"] is not None else None,
    )


def _variant_from_row(row: sqlite3.Row) -> ContentVariant:
    return ContentVariant(
        node_id=str(row["node_id"] or ""),
        culture=str(row["culture"] or ""),
        status=str(row["status"] or _STATUS_DRAFT),
        draft=_json_loads_dict(str(row["draft_json"] or "{}")),
        published=_json_loads_dict(str(row["published_json"] or "{}")),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        published_at=float(row["published_at"]) if row["published_at"] is not None else None,
        updated_by=str(row["updated_by"] or ""),
    )


def _segment_from_row(row: sqlite3.Row) -> ContentSegment:
    return ContentSegment(
        node_id=str(row["node_id"] or ""),
        segment=str(row["segment"] or ""),
        status=str(row["status"] or _STATUS_DRAFT),
        draft=_json_loads_dict(str(row["draft_json"] or "{}")),
        published=_json_loads_dict(str(row["published_json"] or "{}")),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        published_at=float(row["published_at"]) if row["published_at"] is not None else None,
        updated_by=str(row["updated_by"] or ""),
    )


def _lock_from_row(row: sqlite3.Row) -> ContentLock:
    return ContentLock(
        node_id=str(row["node_id"] or ""),
        owner=str(row["owner"] or ""),
        token=str(row["token"] or ""),
        note=str(row["note"] or ""),
        acquired_at=float(row["acquired_at"] or 0.0),
        expires_at=float(row["expires_at"] or 0.0),
        node_name=str(row["node_name"] or ""),
        route_path=str(row["route_path"] or ""),
        content_type_alias=str(row["content_type_alias"] or ""),
    )


def _permission_rule_from_row(row: sqlite3.Row) -> ContentPermissionRule:
    actions = tuple(
        str(item)
        for item in _json_loads_list(str(row["actions_json"] or "[]"))
        if str(item).strip()
    )
    return ContentPermissionRule(
        rule_id=str(row["rule_id"] or ""),
        subject=str(row["subject"] or ""),
        scope_node_id=str(row["scope_node_id"] or ""),
        actions=actions,
        include_descendants=bool(row["include_descendants"]),
        note=str(row["note"] or ""),
        created_at=float(row["created_at"] or 0.0),
        updated_at=float(row["updated_at"] or 0.0),
        updated_by=str(row["updated_by"] or ""),
        node_name=str(row["node_name"] or ""),
        route_path=str(row["route_path"] or ""),
        content_type_alias=str(row["content_type_alias"] or ""),
    )


def _access_rule_from_row(row: sqlite3.Row) -> ContentAccessRule:
    groups = tuple(
        str(item).strip().lower()
        for item in _json_loads_list(str(row["member_groups_json"] or "[]"))
        if str(item).strip()
    )
    return ContentAccessRule(
        node_id=str(row["node_id"] or ""),
        policy=str(row["policy"] or "public"),
        member_groups=groups,
        include_descendants=bool(row["include_descendants"]),
        login_path=str(row["login_path"] or "/login"),
        denied_path=str(row["denied_path"] or ""),
        note=str(row["note"] or ""),
        updated_at=float(row["updated_at"] or 0.0),
        updated_by=str(row["updated_by"] or ""),
        node_name=str(row["node_name"] or ""),
        route_path=str(row["route_path"] or ""),
        content_type_alias=str(row["content_type_alias"] or ""),
    )


class ArcHubCMSService:
    """SQLite-backed ArcHub CMS application service."""

    _lock = threading.Lock()

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_db()
        self._seed_defaults()

    def _ensure_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_data_types (
                        alias TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        editor TEXT NOT NULL DEFAULT 'text',
                        description TEXT NOT NULL DEFAULT '',
                        config_json TEXT NOT NULL DEFAULT '{}',
                        validation_json TEXT NOT NULL DEFAULT '{}',
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_templates (
                        alias TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        view TEXT NOT NULL DEFAULT 'archub_public.html',
                        description TEXT NOT NULL DEFAULT '',
                        allowed_content_type_aliases_json TEXT NOT NULL DEFAULT '[]',
                        config_json TEXT NOT NULL DEFAULT '{}',
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_types (
                        alias TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        icon TEXT NOT NULL DEFAULT '',
                        description TEXT NOT NULL DEFAULT '',
                        schema_json TEXT NOT NULL DEFAULT '[]',
                        allowed_child_aliases_json TEXT NOT NULL DEFAULT '[]',
                        composition_aliases_json TEXT NOT NULL DEFAULT '[]',
                        allow_at_root INTEGER NOT NULL DEFAULT 0,
                        is_element INTEGER NOT NULL DEFAULT 0,
                        template TEXT NOT NULL DEFAULT 'page',
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    )
                """)
                self._ensure_column(
                    conn,
                    "archub_content_types",
                    "composition_aliases_json",
                    "TEXT NOT NULL DEFAULT '[]'",
                )
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_compositions (
                        alias TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        schema_json TEXT NOT NULL DEFAULT '[]',
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_blueprints (
                        blueprint_id TEXT PRIMARY KEY,
                        content_type_alias TEXT NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        payload_json TEXT NOT NULL DEFAULT '{}',
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_nodes (
                        node_id TEXT PRIMARY KEY,
                        parent_id TEXT,
                        content_type_alias TEXT NOT NULL,
                        name TEXT NOT NULL,
                        slug TEXT NOT NULL,
                        route_path TEXT NOT NULL UNIQUE,
                        level INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'draft',
                        draft_json TEXT NOT NULL DEFAULT '{}',
                        published_json TEXT,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        published_at REAL,
                        created_by TEXT NOT NULL DEFAULT '',
                        updated_by TEXT NOT NULL DEFAULT '',
                        trashed_at REAL,
                        trashed_by TEXT NOT NULL DEFAULT '',
                        trashed_original_parent_id TEXT,
                        trashed_original_route_path TEXT NOT NULL DEFAULT '',
                        trashed_original_slug TEXT NOT NULL DEFAULT '',
                        trashed_original_sort_order INTEGER,
                        trashed_original_status TEXT NOT NULL DEFAULT ''
                    )
                """)
                for column_name, definition in (
                    ("trashed_at", "REAL"),
                    ("trashed_by", "TEXT NOT NULL DEFAULT ''"),
                    ("trashed_original_parent_id", "TEXT"),
                    ("trashed_original_route_path", "TEXT NOT NULL DEFAULT ''"),
                    ("trashed_original_slug", "TEXT NOT NULL DEFAULT ''"),
                    ("trashed_original_sort_order", "INTEGER"),
                    ("trashed_original_status", "TEXT NOT NULL DEFAULT ''"),
                ):
                    self._ensure_column(conn, "archub_content_nodes", column_name, definition)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_versions (
                        version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        node_id TEXT NOT NULL,
                        version_no INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        created_by TEXT NOT NULL DEFAULT '',
                        note TEXT NOT NULL DEFAULT '',
                        UNIQUE(node_id, version_no)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_variants (
                        node_id TEXT NOT NULL,
                        culture TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'draft',
                        draft_json TEXT NOT NULL DEFAULT '{}',
                        published_json TEXT,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        published_at REAL,
                        updated_by TEXT NOT NULL DEFAULT '',
                        PRIMARY KEY(node_id, culture)
                    )
                """)
                self._ensure_content_segment_tables(conn)
                self._ensure_delivery_context_tables(conn)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_media_assets (
                        asset_id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        original_name TEXT NOT NULL,
                        content_type TEXT NOT NULL,
                        url TEXT NOT NULL,
                        folder TEXT NOT NULL DEFAULT '',
                        alt_text TEXT NOT NULL DEFAULT '',
                        tags_json TEXT NOT NULL DEFAULT '[]',
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        created_at REAL NOT NULL,
                        created_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_dictionary_items (
                        item_key TEXT PRIMARY KEY,
                        group_name TEXT NOT NULL DEFAULT '',
                        values_json TEXT NOT NULL DEFAULT '{}',
                        updated_at REAL NOT NULL,
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_redirect_rules (
                        redirect_id TEXT PRIMARY KEY,
                        source_path TEXT NOT NULL UNIQUE,
                        target_path TEXT NOT NULL,
                        status_code INTEGER NOT NULL DEFAULT 301,
                        active INTEGER NOT NULL DEFAULT 1,
                        note TEXT NOT NULL DEFAULT '',
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        created_by TEXT NOT NULL DEFAULT '',
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_workflows (
                        node_id TEXT PRIMARY KEY,
                        state TEXT NOT NULL DEFAULT 'draft',
                        assigned_to TEXT NOT NULL DEFAULT '',
                        scheduled_publish_at REAL,
                        scheduled_unpublish_at REAL,
                        note TEXT NOT NULL DEFAULT '',
                        updated_at REAL NOT NULL,
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_activity (
                        activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        node_id TEXT NOT NULL DEFAULT '',
                        action TEXT NOT NULL,
                        actor TEXT NOT NULL DEFAULT '',
                        summary TEXT NOT NULL DEFAULT '',
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        created_at REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_locks (
                        node_id TEXT PRIMARY KEY,
                        owner TEXT NOT NULL,
                        token TEXT NOT NULL,
                        note TEXT NOT NULL DEFAULT '',
                        acquired_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_permissions (
                        rule_id TEXT PRIMARY KEY,
                        subject TEXT NOT NULL,
                        scope_node_id TEXT NOT NULL DEFAULT '',
                        actions_json TEXT NOT NULL DEFAULT '[]',
                        include_descendants INTEGER NOT NULL DEFAULT 1,
                        note TEXT NOT NULL DEFAULT '',
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_content_access (
                        node_id TEXT PRIMARY KEY,
                        policy TEXT NOT NULL DEFAULT 'public',
                        member_groups_json TEXT NOT NULL DEFAULT '[]',
                        include_descendants INTEGER NOT NULL DEFAULT 1,
                        login_path TEXT NOT NULL DEFAULT '/login',
                        denied_path TEXT NOT NULL DEFAULT '',
                        note TEXT NOT NULL DEFAULT '',
                        updated_at REAL NOT NULL,
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_webhooks (
                        webhook_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        target_url TEXT NOT NULL,
                        events_json TEXT NOT NULL DEFAULT '[]',
                        secret TEXT NOT NULL DEFAULT '',
                        active INTEGER NOT NULL DEFAULT 1,
                        timeout_seconds REAL NOT NULL DEFAULT 5.0,
                        max_attempts INTEGER NOT NULL DEFAULT 5,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        created_by TEXT NOT NULL DEFAULT '',
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archub_webhook_deliveries (
                        delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        webhook_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        aggregate_id TEXT NOT NULL DEFAULT '',
                        payload_json TEXT NOT NULL DEFAULT '{}',
                        status TEXT NOT NULL DEFAULT 'pending',
                        attempts INTEGER NOT NULL DEFAULT 0,
                        next_attempt_at REAL NOT NULL,
                        last_error TEXT NOT NULL DEFAULT '',
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        delivered_at REAL
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_nodes_parent_sort
                    ON archub_content_nodes(parent_id, sort_order, name)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_compositions_updated
                    ON archub_content_compositions(updated_at DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_data_types_editor_updated
                    ON archub_data_types(editor, updated_at DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_templates_view_updated
                    ON archub_templates(view, updated_at DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_blueprints_type_updated
                    ON archub_content_blueprints(content_type_alias, updated_at DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_nodes_route_status
                    ON archub_content_nodes(route_path, status)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_versions_node
                    ON archub_content_versions(node_id, version_no DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_variants_status_culture
                    ON archub_content_variants(status, culture)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_variants_node_updated
                    ON archub_content_variants(node_id, updated_at DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_redirect_active_source
                    ON archub_redirect_rules(active, source_path)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_workflows_state_schedule
                    ON archub_content_workflows(state, scheduled_publish_at, scheduled_unpublish_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_activity_node_created
                    ON archub_content_activity(node_id, created_at DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_activity_action_created
                    ON archub_content_activity(action, created_at DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_locks_expires_owner
                    ON archub_content_locks(expires_at, owner)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_permissions_subject_scope
                    ON archub_content_permissions(subject, scope_node_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_access_policy
                    ON archub_content_access(policy, include_descendants)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_webhooks_active
                    ON archub_webhooks(active, updated_at DESC)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_webhook_deliveries_status_next
                    ON archub_webhook_deliveries(status, next_attempt_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archub_webhook_deliveries_webhook_created
                    ON archub_webhook_deliveries(webhook_id, created_at DESC)
                """)
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        columns = {
            str(row["name"])
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    @staticmethod
    def _ensure_content_segment_tables(conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS archub_content_segments (
                node_id TEXT NOT NULL,
                segment TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                draft_json TEXT NOT NULL DEFAULT '{}',
                published_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                published_at REAL,
                updated_by TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(node_id, segment)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archub_segments_status_segment
            ON archub_content_segments(status, segment)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archub_segments_node_updated
            ON archub_content_segments(node_id, updated_at DESC)
        """)

    @staticmethod
    def _ensure_delivery_context_tables(conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS archub_content_domains (
                domain_id TEXT PRIMARY KEY,
                hostname TEXT NOT NULL UNIQUE,
                root_node_id TEXT NOT NULL DEFAULT 'root',
                culture TEXT NOT NULL DEFAULT '',
                is_default INTEGER NOT NULL DEFAULT 0,
                secure INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                updated_by TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS archub_preview_tokens (
                token_hash TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                created_by TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                revoked_at REAL,
                revoked_by TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archub_domains_default_sort
            ON archub_content_domains(is_default, sort_order, hostname)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archub_domains_root
            ON archub_content_domains(root_node_id, culture)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archub_preview_tokens_node
            ON archub_preview_tokens(node_id, expires_at DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_archub_preview_tokens_active
            ON archub_preview_tokens(expires_at, revoked_at)
        """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _seed_defaults(self) -> None:
        now = _now()
        data_types = (
            ContentDataType(
                alias="short_text",
                name="Short text",
                editor="text",
                description="Single-line text input for titles and labels.",
                config={"rows": 1},
                validation={"max_length": 120},
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
            ContentDataType(
                alias="long_text",
                name="Long text",
                editor="textarea",
                description="Multi-line text area for summaries and excerpts.",
                config={"rows": 4},
                validation={"max_length": 500},
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
            ContentDataType(
                alias="rich_text",
                name="Rich text",
                editor="richtext",
                description="HTML rich text body editor.",
                config={"toolbar": "basic"},
                validation={"min_length": 0},
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
            ContentDataType(
                alias="true_false",
                name="True/false",
                editor="checkbox",
                description="Boolean toggle.",
                config={},
                validation={},
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
            ContentDataType(
                alias="content_builder_blocks",
                name="Content Builder blocks",
                editor="builder",
                description="Structured page block JSON for ArcHub Content Builder.",
                config={"service": "archub_content_builder"},
                validation={},
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
        )
        templates = (
            ContentTemplate(
                alias="root",
                name="Site root",
                view="archub_public.html",
                description="Public root template.",
                allowed_content_type_aliases=(),
                config={"cache_seconds": 60, "layout": "root"},
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
            ContentTemplate(
                alias="page",
                name="Standard page",
                view="archub_public.html",
                description="Default page template for public CMS pages.",
                allowed_content_type_aliases=(),
                config={"cache_seconds": 60, "layout": "page"},
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
            ContentTemplate(
                alias="landing",
                name="Landing page",
                view="archub_public.html",
                description="Landing template with hero and Content Builder blocks.",
                allowed_content_type_aliases=(),
                config={"cache_seconds": 60, "layout": "landing"},
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
            ContentTemplate(
                alias="article",
                name="Article",
                view="archub_public.html",
                description="Long-form article template for knowledge and RAG materials.",
                allowed_content_type_aliases=(),
                config={"cache_seconds": 60, "layout": "article"},
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
            ContentTemplate(
                alias="expert",
                name="Expert profile",
                view="archub_public.html",
                description="Public expert profile template.",
                allowed_content_type_aliases=(),
                config={"cache_seconds": 30, "layout": "expert"},
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
        )
        compositions = (
            ContentComposition(
                alias="seo_metadata",
                name="SEO metadata",
                description="Reusable SEO title, description and robots controls.",
                fields=(
                    ContentField("seo_title", "SEO title", "text"),
                    ContentField("seo_description", "SEO description", "textarea"),
                    ContentField("robots_meta", "Robots meta", "text", default="index,follow"),
                ),
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
            ContentComposition(
                alias="taxonomy",
                name="Taxonomy",
                description="Reusable tags and editorial category fields.",
                fields=(
                    ContentField("tags", "Tags", "text", help_text="Через запятую"),
                    ContentField("category", "Category", "text"),
                ),
                created_at=now,
                updated_at=now,
                updated_by="system",
            ),
        )
        defaults = (
            ContentType(
                alias="site_root",
                name="Site root",
                icon="◎",
                description="Корневой узел дерева ArcHub.",
                allow_at_root=True,
                allowed_child_aliases=(
                    "page",
                    "bot_landing",
                    "knowledge_article",
                    "expert_page",
                    "ai_expert",
                    "rag_material",
                    "bot_resource",
                ),
                template="root",
                fields=(
                    ContentField("title", "Title", "text", True, default="ArcHub"),
                    ContentField("description", "Description", "textarea"),
                ),
            ),
            ContentType(
                alias="page",
                name="Page",
                icon="▣",
                description="Обычная страница с SEO-полями и rich text телом.",
                allow_at_root=True,
                allowed_child_aliases=("page", "knowledge_article", "expert_page", "rag_material"),
                template="page",
                fields=(
                    ContentField("title", "Title", "text", True),
                    ContentField("summary", "Summary", "textarea"),
                    ContentField("body", "Body", "richtext"),
                    ContentField(
                        "builder_blocks",
                        "Content Builder",
                        "builder",
                        help_text="JSON blocks rendered by the ArcHub Content Builder service.",
                        default="[]",
                    ),
                    ContentField("seo_title", "SEO title", "text"),
                    ContentField("seo_description", "SEO description", "textarea"),
                ),
            ),
            ContentType(
                alias="bot_landing",
                name="Bot landing",
                icon="◉",
                description="Лендинг продукта, эксперта или сценария бота.",
                allow_at_root=True,
                allowed_child_aliases=("page", "knowledge_article"),
                template="landing",
                fields=(
                    ContentField("title", "Title", "text", True),
                    ContentField("hero_title", "Hero title", "text", True),
                    ContentField("hero_text", "Hero text", "textarea"),
                    ContentField("cta_label", "CTA label", "text"),
                    ContentField("cta_url", "CTA URL", "text"),
                    ContentField("body", "Body", "richtext"),
                    ContentField(
                        "builder_blocks",
                        "Content Builder",
                        "builder",
                        help_text="JSON blocks rendered after the landing hero.",
                        default="[]",
                    ),
                ),
            ),
            ContentType(
                alias="knowledge_article",
                name="Knowledge article",
                icon="✧",
                description="Статья базы знаний, которую позже можно подключить к RAG.",
                allow_at_root=False,
                allowed_child_aliases=(),
                template="article",
                fields=(
                    ContentField("title", "Title", "text", True),
                    ContentField("excerpt", "Excerpt", "textarea"),
                    ContentField("body", "Body", "richtext", True),
                    ContentField(
                        "builder_blocks",
                        "Content Builder",
                        "builder",
                        help_text="Optional structured content blocks for the article.",
                        default="[]",
                    ),
                    ContentField("tags", "Tags", "text", help_text="Через запятую"),
                ),
            ),
            ContentType(
                alias="expert_page",
                name="Expert page",
                icon="◇",
                description="Публичная CMS-страница ИИ-эксперта.",
                allow_at_root=False,
                allowed_child_aliases=(),
                template="expert",
                fields=(
                    ContentField("title", "Title", "text", True),
                    ContentField("expert_id", "Expert ID", "text", True),
                    ContentField("headline", "Headline", "textarea"),
                    ContentField("body", "Body", "richtext"),
                    ContentField(
                        "builder_blocks",
                        "Content Builder",
                        "builder",
                        help_text="Editorial blocks for the public expert page.",
                        default="[]",
                    ),
                    ContentField("featured", "Featured", "checkbox"),
                ),
            ),
            ContentType(
                alias="ai_expert",
                name="AI expert",
                icon="☉",
                description=(
                    "Runtime-профиль ИИ-консультанта: персона, школа, цена, "
                    "system prompt и привязка к RAG-корпусу."
                ),
                allow_at_root=True,
                allowed_child_aliases=("rag_material", "knowledge_article"),
                template="expert",
                fields=(
                    ContentField("expert_id", "Expert ID", "text", True),
                    ContentField("avatar", "Avatar", "text", default="🔮"),
                    ContentField("school", "School", "text", True, default="western"),
                    ContentField("title", "Title", "text", True),
                    ContentField("bio", "Bio", "textarea"),
                    ContentField("tags", "Tags", "text", help_text="Через запятую"),
                    ContentField("price_per_message", "Token price", "text", True, default="40"),
                    ContentField("currency", "Currency", "text", True, default="ток."),
                    ContentField("greeting", "Greeting", "textarea"),
                    ContentField("sample_questions", "Sample questions", "textarea", help_text="Один вопрос на строку"),
                    ContentField("system_prompt", "System prompt", "richtext", True),
                    ContentField("rag_school", "RAG corpus", "text"),
                    ContentField("online", "Online", "checkbox", default="1"),
                    ContentField("visible", "Visible", "checkbox", default="1"),
                ),
            ),
            ContentType(
                alias="rag_material",
                name="RAG material",
                icon="※",
                description=(
                    "Опубликованный материал корпуса RAG конкретного ИИ-эксперта. "
                    "Runtime использует только опубликованные активные записи."
                ),
                allow_at_root=True,
                allowed_child_aliases=(),
                template="article",
                fields=(
                    ContentField("title", "Title", "text", True),
                    ContentField("corpus_key", "Corpus key", "text", True),
                    ContentField("source_path", "Source path", "text"),
                    ContentField("body", "Body", "richtext", True),
                    ContentField("tags", "Tags", "text", help_text="Через запятую"),
                    ContentField("active", "Active in RAG", "checkbox", default="1"),
                ),
            ),
            ContentType(
                alias="bot_resource",
                name="Bot resource",
                icon="▤",
                description=(
                    "Публикуемый ресурс web/Telegram-бота: YAML/JSON/Markdown "
                    "тексты, help-материалы, сценарии и справочные данные."
                ),
                allow_at_root=True,
                allowed_child_aliases=(),
                template="article",
                fields=(
                    ContentField("title", "Title", "text", True),
                    ContentField("resource_key", "Resource key", "text", True),
                    ContentField("resource_group", "Resource group", "text"),
                    ContentField("source_path", "Source path", "text"),
                    ContentField("format", "Format", "text", default="text"),
                    ContentField("body", "Body", "richtext", True),
                    ContentField("locale", "Locale", "text", default="ru"),
                    ContentField("active", "Active", "checkbox", default="1"),
                ),
            ),
        )
        with self._lock:
            conn = self._connect()
            try:
                for item in data_types:
                    conn.execute(
                        """
                        INSERT INTO archub_data_types (
                            alias, name, editor, description, config_json,
                            validation_json, created_at, updated_at, updated_by
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(alias) DO UPDATE SET
                            name = excluded.name,
                            editor = excluded.editor,
                            description = excluded.description,
                            config_json = excluded.config_json,
                            validation_json = excluded.validation_json,
                            updated_at = excluded.updated_at,
                            updated_by = excluded.updated_by
                        """,
                        (
                            item.alias,
                            item.name,
                            item.editor,
                            item.description,
                            _json_dumps(item.config),
                            _json_dumps(item.validation),
                            item.created_at,
                            item.updated_at,
                            item.updated_by,
                        ),
                    )
                for item in templates:
                    conn.execute(
                        """
                        INSERT INTO archub_templates (
                            alias, name, view, description,
                            allowed_content_type_aliases_json, config_json,
                            created_at, updated_at, updated_by
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(alias) DO UPDATE SET
                            name = excluded.name,
                            view = excluded.view,
                            description = excluded.description,
                            allowed_content_type_aliases_json = excluded.allowed_content_type_aliases_json,
                            config_json = excluded.config_json,
                            updated_at = excluded.updated_at,
                            updated_by = excluded.updated_by
                        """,
                        (
                            item.alias,
                            item.name,
                            item.view,
                            item.description,
                            _json_dumps(list(item.allowed_content_type_aliases)),
                            _json_dumps(item.config),
                            item.created_at,
                            item.updated_at,
                            item.updated_by,
                        ),
                    )
                for item in compositions:
                    conn.execute(
                        """
                        INSERT INTO archub_content_compositions (
                            alias, name, description, schema_json, created_at,
                            updated_at, updated_by
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(alias) DO UPDATE SET
                            name = excluded.name,
                            description = excluded.description,
                            schema_json = excluded.schema_json,
                            updated_at = excluded.updated_at,
                            updated_by = excluded.updated_by
                        """,
                        (
                            item.alias,
                            item.name,
                            item.description,
                            _json_dumps([field.__dict__ for field in item.fields]),
                            item.created_at,
                            item.updated_at,
                            item.updated_by,
                        ),
                    )
                for item in defaults:
                    composition_json = _json_dumps(list(item.composition_aliases))
                    schema_json = _json_dumps([field.__dict__ for field in item.fields])
                    allowed_json = _json_dumps(list(item.allowed_child_aliases))
                    existing = conn.execute(
                        "SELECT alias FROM archub_content_types WHERE alias = ?",
                        (item.alias,),
                    ).fetchone()
                    if existing is None:
                        conn.execute(
                            """
                            INSERT INTO archub_content_types (
                                alias, name, icon, description, schema_json,
                                allowed_child_aliases_json, composition_aliases_json,
                                allow_at_root, is_element, template, created_at,
                                updated_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item.alias,
                                item.name,
                                item.icon,
                                item.description,
                                schema_json,
                                allowed_json,
                                composition_json,
                                int(item.allow_at_root),
                                int(item.is_element),
                                item.template,
                                now,
                                now,
                            ),
                        )
                    else:
                        conn.execute(
                            """
                            UPDATE archub_content_types
                            SET name = ?, icon = ?, description = ?, schema_json = ?,
                                allowed_child_aliases_json = ?,
                                composition_aliases_json = ?, allow_at_root = ?,
                                is_element = ?, template = ?, updated_at = ?
                            WHERE alias = ?
                            """,
                            (
                                item.name,
                                item.icon,
                                item.description,
                                schema_json,
                                allowed_json,
                                composition_json,
                                int(item.allow_at_root),
                                int(item.is_element),
                                item.template,
                                now,
                                item.alias,
                            ),
                        )

                root = conn.execute(
                    "SELECT node_id FROM archub_content_nodes WHERE node_id = ?",
                    (_ROOT_NODE_ID,),
                ).fetchone()
                if root is None:
                    payload = {"title": "ArcHub", "description": "CMS root"}
                    conn.execute(
                        """
                        INSERT INTO archub_content_nodes (
                            node_id, parent_id, content_type_alias, name, slug,
                            route_path, level, status, draft_json, published_json,
                            sort_order, created_at, updated_at, published_at,
                            created_by, updated_by
                        )
                        VALUES (?, NULL, ?, ?, ?, ?, 0, ?, ?, ?, 0, ?, ?, ?, ?, ?)
                        """,
                        (
                            _ROOT_NODE_ID,
                            "site_root",
                            "ArcHub",
                            "",
                            _PUBLIC_ROOT,
                            _STATUS_PUBLISHED,
                            _json_dumps(payload),
                            _json_dumps(payload),
                            now,
                            now,
                            now,
                            "system",
                            "system",
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO archub_content_versions (
                            node_id, version_no, status, payload_json, created_at,
                            created_by, note
                        )
                        VALUES (?, 1, ?, ?, ?, ?, ?)
                        """,
                        (
                            _ROOT_NODE_ID,
                            _STATUS_PUBLISHED,
                            _json_dumps(payload),
                            now,
                            "system",
                            "Seed root",
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

    def stats(self) -> dict[str, int]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT status, COUNT(*) AS c FROM archub_content_nodes GROUP BY status"
                ).fetchall()
                counts = {str(row["status"]): int(row["c"]) for row in rows}
                data_types = conn.execute("SELECT COUNT(*) AS c FROM archub_data_types").fetchone()
                templates = conn.execute("SELECT COUNT(*) AS c FROM archub_templates").fetchone()
                types = conn.execute("SELECT COUNT(*) AS c FROM archub_content_types").fetchone()
                compositions = conn.execute("SELECT COUNT(*) AS c FROM archub_content_compositions").fetchone()
                blueprints = conn.execute("SELECT COUNT(*) AS c FROM archub_content_blueprints").fetchone()
                versions = conn.execute("SELECT COUNT(*) AS c FROM archub_content_versions").fetchone()
                variants = conn.execute("SELECT COUNT(*) AS c FROM archub_content_variants").fetchone()
                segments = conn.execute("SELECT COUNT(*) AS c FROM archub_content_segments").fetchone()
                domains = conn.execute("SELECT COUNT(*) AS c FROM archub_content_domains").fetchone()
                preview_tokens = conn.execute(
                    """
                    SELECT COUNT(*) AS c FROM archub_preview_tokens
                    WHERE expires_at > ? AND revoked_at IS NULL
                    """,
                    (_now(),),
                ).fetchone()
                media = conn.execute("SELECT COUNT(*) AS c FROM archub_media_assets").fetchone()
                redirects = conn.execute("SELECT COUNT(*) AS c FROM archub_redirect_rules").fetchone()
                workflows = conn.execute("SELECT COUNT(*) AS c FROM archub_content_workflows").fetchone()
                activity = conn.execute("SELECT COUNT(*) AS c FROM archub_content_activity").fetchone()
                locks = conn.execute(
                    "SELECT COUNT(*) AS c FROM archub_content_locks WHERE expires_at > ?",
                    (_now(),),
                ).fetchone()
                permission_rules = conn.execute(
                    "SELECT COUNT(*) AS c FROM archub_content_permissions"
                ).fetchone()
                access_rules = conn.execute(
                    "SELECT COUNT(*) AS c FROM archub_content_access WHERE policy != 'public'"
                ).fetchone()
                webhooks = conn.execute("SELECT COUNT(*) AS c FROM archub_webhooks").fetchone()
                webhook_pending = conn.execute(
                    """
                    SELECT COUNT(*) AS c FROM archub_webhook_deliveries
                    WHERE status IN ('pending', 'retry')
                    """
                ).fetchone()
            finally:
                conn.close()
        return {
            "data_types": int(data_types["c"] if data_types else 0),
            "templates": int(templates["c"] if templates else 0),
            "content_types": int(types["c"] if types else 0),
            "compositions": int(compositions["c"] if compositions else 0),
            "blueprints": int(blueprints["c"] if blueprints else 0),
            "nodes": sum(counts.values()),
            "draft": counts.get(_STATUS_DRAFT, 0),
            "published": counts.get(_STATUS_PUBLISHED, 0),
            "unpublished": counts.get(_STATUS_UNPUBLISHED, 0),
            "trashed": counts.get(_STATUS_TRASHED, 0),
            "versions": int(versions["c"] if versions else 0),
            "variants": int(variants["c"] if variants else 0),
            "segments": int(segments["c"] if segments else 0),
            "domains": int(domains["c"] if domains else 0),
            "preview_tokens": int(preview_tokens["c"] if preview_tokens else 0),
            "media": int(media["c"] if media else 0),
            "redirects": int(redirects["c"] if redirects else 0),
            "workflows": int(workflows["c"] if workflows else 0),
            "activity": int(activity["c"] if activity else 0),
            "locks": int(locks["c"] if locks else 0),
            "permission_rules": int(permission_rules["c"] if permission_rules else 0),
            "access_rules": int(access_rules["c"] if access_rules else 0),
            "webhooks": int(webhooks["c"] if webhooks else 0),
            "webhook_pending": int(webhook_pending["c"] if webhook_pending else 0),
        }

    def list_data_types(self, *, limit: int = 200) -> list[ContentDataType]:
        limit = max(1, min(limit, 1000))
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT * FROM archub_data_types
                    ORDER BY name, alias
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [_data_type_from_row(row) for row in rows]
            finally:
                conn.close()

    def get_data_type(self, alias: str) -> ContentDataType | None:
        clean_alias = alias.strip()
        if not clean_alias:
            return None
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM archub_data_types WHERE alias = ?",
                    (clean_alias,),
                ).fetchone()
                return _data_type_from_row(row) if row is not None else None
            finally:
                conn.close()

    def upsert_data_type(
        self,
        *,
        alias: str,
        name: str,
        editor: str,
        description: str = "",
        config: dict[str, Any] | None = None,
        validation: dict[str, Any] | None = None,
        updated_by: str,
    ) -> ContentDataType:
        clean_alias = self._validate_schema_alias(alias, label="Data type alias")
        clean_name = name.strip()
        clean_editor = editor.strip() or "text"
        if not clean_name:
            raise ValueError("Data type name is required")
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT created_at FROM archub_data_types WHERE alias = ?",
                    (clean_alias,),
                ).fetchone()
                created_at = float(existing["created_at"]) if existing is not None else now
                conn.execute(
                    """
                    INSERT INTO archub_data_types (
                        alias, name, editor, description, config_json,
                        validation_json, created_at, updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(alias) DO UPDATE SET
                        name = excluded.name,
                        editor = excluded.editor,
                        description = excluded.description,
                        config_json = excluded.config_json,
                        validation_json = excluded.validation_json,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        clean_alias,
                        clean_name,
                        clean_editor,
                        description.strip(),
                        _json_dumps(config or {}),
                        _json_dumps(validation or {}),
                        created_at,
                        now,
                        updated_by,
                    ),
                )
                self._record_activity(
                    conn,
                    action="content_model.data_type_upserted",
                    actor=updated_by,
                    summary=f"Data type saved: {clean_name}",
                    metadata={
                        "data_type_alias": clean_alias,
                        "editor": clean_editor,
                    },
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM archub_data_types WHERE alias = ?",
                    (clean_alias,),
                ).fetchone()
                return _data_type_from_row(row)
            finally:
                conn.close()

    def list_templates(self, *, limit: int = 200) -> list[ContentTemplate]:
        limit = max(1, min(limit, 1000))
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT * FROM archub_templates
                    ORDER BY name, alias
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [_template_from_row(row) for row in rows]
            finally:
                conn.close()

    def get_template(self, alias: str) -> ContentTemplate | None:
        clean_alias = alias.strip()
        if not clean_alias:
            return None
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM archub_templates WHERE alias = ?",
                    (clean_alias,),
                ).fetchone()
                return _template_from_row(row) if row is not None else None
            finally:
                conn.close()

    def upsert_template(
        self,
        *,
        alias: str,
        name: str,
        view: str,
        description: str = "",
        allowed_content_type_aliases: Iterable[str] = (),
        config: dict[str, Any] | None = None,
        updated_by: str,
    ) -> ContentTemplate:
        clean_alias = self._validate_schema_alias(alias, label="Template alias")
        clean_name = name.strip()
        clean_view = view.strip() or "archub_public.html"
        if not clean_name:
            raise ValueError("Template name is required")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.html", clean_view):
            raise ValueError("Template view must be a local .html template name")
        clean_allowed = tuple(
            self._validate_schema_alias(item, label="Allowed content type alias")
            for item in allowed_content_type_aliases
            if str(item).strip()
        )
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                for content_type_alias in clean_allowed:
                    if conn.execute(
                        "SELECT alias FROM archub_content_types WHERE alias = ?",
                        (content_type_alias,),
                    ).fetchone() is None:
                        raise ValueError(f"Unknown content type for template: {content_type_alias}")
                existing = conn.execute(
                    "SELECT created_at FROM archub_templates WHERE alias = ?",
                    (clean_alias,),
                ).fetchone()
                created_at = float(existing["created_at"]) if existing is not None else now
                conn.execute(
                    """
                    INSERT INTO archub_templates (
                        alias, name, view, description,
                        allowed_content_type_aliases_json, config_json,
                        created_at, updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(alias) DO UPDATE SET
                        name = excluded.name,
                        view = excluded.view,
                        description = excluded.description,
                        allowed_content_type_aliases_json = excluded.allowed_content_type_aliases_json,
                        config_json = excluded.config_json,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        clean_alias,
                        clean_name,
                        clean_view,
                        description.strip(),
                        _json_dumps(list(clean_allowed)),
                        _json_dumps(config or {}),
                        created_at,
                        now,
                        updated_by,
                    ),
                )
                self._record_activity(
                    conn,
                    action="content_model.template_upserted",
                    actor=updated_by,
                    summary=f"Template saved: {clean_name}",
                    metadata={
                        "template_alias": clean_alias,
                        "view": clean_view,
                        "allowed_content_type_aliases": list(clean_allowed),
                    },
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM archub_templates WHERE alias = ?",
                    (clean_alias,),
                ).fetchone()
                return _template_from_row(row)
            finally:
                conn.close()

    def list_content_types(self) -> list[ContentType]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM archub_content_types ORDER BY is_element, name"
                ).fetchall()
                return [self._hydrate_content_type(conn, row) for row in rows]
            finally:
                conn.close()

    def get_content_type(self, alias: str) -> ContentType | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM archub_content_types WHERE alias = ?",
                    (alias,),
                ).fetchone()
                return self._hydrate_content_type(conn, row) if row is not None else None
            finally:
                conn.close()

    def list_content_compositions(self) -> list[ContentComposition]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM archub_content_compositions ORDER BY name"
                ).fetchall()
                return [_composition_from_row(row) for row in rows]
            finally:
                conn.close()

    def get_content_composition(self, alias: str) -> ContentComposition | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM archub_content_compositions WHERE alias = ?",
                    (alias,),
                ).fetchone()
                return _composition_from_row(row) if row is not None else None
            finally:
                conn.close()

    def list_content_blueprints(
        self,
        *,
        content_type_alias: str = "",
        limit: int = 100,
    ) -> list[ContentBlueprint]:
        clean_alias = content_type_alias.strip()
        limit = max(1, min(limit, 1000))
        with self._lock:
            conn = self._connect()
            try:
                if clean_alias:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_content_blueprints
                        WHERE content_type_alias = ?
                        ORDER BY updated_at DESC, name
                        LIMIT ?
                        """,
                        (clean_alias, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_content_blueprints
                        ORDER BY updated_at DESC, content_type_alias, name
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                return [_blueprint_from_row(row) for row in rows]
            finally:
                conn.close()

    def get_content_blueprint(self, blueprint_id: str) -> ContentBlueprint | None:
        clean_id = blueprint_id.strip()
        if not clean_id:
            return None
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM archub_content_blueprints WHERE blueprint_id = ?",
                    (clean_id,),
                ).fetchone()
                return _blueprint_from_row(row) if row is not None else None
            finally:
                conn.close()

    def upsert_content_blueprint(
        self,
        *,
        content_type_alias: str,
        name: str,
        payload: dict[str, Any],
        description: str = "",
        updated_by: str,
        blueprint_id: str = "",
    ) -> ContentBlueprint:
        clean_alias = content_type_alias.strip()
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Blueprint name is required")
        clean_id = blueprint_id.strip() or secrets.token_urlsafe(10)
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                type_row = self._get_content_type_row(conn, clean_alias)
                content_type = self._hydrate_content_type(conn, type_row)
                clean_payload = self._clean_blueprint_payload(content_type, payload)
                existing = conn.execute(
                    "SELECT created_at FROM archub_content_blueprints WHERE blueprint_id = ?",
                    (clean_id,),
                ).fetchone()
                created_at = float(existing["created_at"]) if existing is not None else now
                conn.execute(
                    """
                    INSERT INTO archub_content_blueprints (
                        blueprint_id, content_type_alias, name, description,
                        payload_json, created_at, updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(blueprint_id) DO UPDATE SET
                        content_type_alias = excluded.content_type_alias,
                        name = excluded.name,
                        description = excluded.description,
                        payload_json = excluded.payload_json,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        clean_id,
                        content_type.alias,
                        clean_name,
                        description.strip(),
                        _json_dumps(clean_payload),
                        created_at,
                        now,
                        updated_by,
                    ),
                )
                self._record_activity(
                    conn,
                    action="content_model.blueprint_upserted",
                    actor=updated_by,
                    summary=f"Content blueprint saved: {clean_name}",
                    metadata={
                        "blueprint_id": clean_id,
                        "content_type_alias": content_type.alias,
                        "fields": sorted(clean_payload),
                    },
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM archub_content_blueprints WHERE blueprint_id = ?",
                    (clean_id,),
                ).fetchone()
                return _blueprint_from_row(row)
            finally:
                conn.close()

    def delete_content_blueprint(self, blueprint_id: str, *, deleted_by: str) -> bool:
        clean_id = blueprint_id.strip()
        if not clean_id:
            return False
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM archub_content_blueprints WHERE blueprint_id = ?",
                    (clean_id,),
                ).fetchone()
                if row is None:
                    return False
                conn.execute(
                    "DELETE FROM archub_content_blueprints WHERE blueprint_id = ?",
                    (clean_id,),
                )
                self._record_activity(
                    conn,
                    action="content_model.blueprint_deleted",
                    actor=deleted_by,
                    summary=f"Content blueprint deleted: {row['name']}",
                    metadata={
                        "blueprint_id": clean_id,
                        "content_type_alias": str(row["content_type_alias"] or ""),
                    },
                )
                conn.commit()
                return True
            finally:
                conn.close()

    def upsert_content_composition(
        self,
        *,
        alias: str,
        name: str,
        description: str = "",
        fields: Iterable[dict[str, Any] | ContentField] = (),
        updated_by: str,
    ) -> ContentComposition:
        clean_alias = self._validate_schema_alias(alias, label="Composition alias")
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Composition name is required")
        clean_fields = self._normalize_content_fields(fields)
        if not clean_fields:
            raise ValueError("Composition must define at least one field")
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                clean_fields = self._resolve_content_field_data_types(conn, clean_fields)
                existing = conn.execute(
                    "SELECT alias, created_at FROM archub_content_compositions WHERE alias = ?",
                    (clean_alias,),
                ).fetchone()
                created_at = float(existing["created_at"]) if existing is not None else now
                conn.execute(
                    """
                    INSERT INTO archub_content_compositions (
                        alias, name, description, schema_json, created_at,
                        updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(alias) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description,
                        schema_json = excluded.schema_json,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        clean_alias,
                        clean_name,
                        description.strip(),
                        _json_dumps([field.__dict__ for field in clean_fields]),
                        created_at,
                        now,
                        updated_by,
                    ),
                )
                self._record_activity(
                    conn,
                    action="content_model.composition_upserted",
                    actor=updated_by,
                    summary=f"Composition saved: {clean_name}",
                    metadata={
                        "composition_alias": clean_alias,
                        "fields": [field.alias for field in clean_fields],
                    },
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM archub_content_compositions WHERE alias = ?",
                    (clean_alias,),
                ).fetchone()
                return _composition_from_row(row)
            finally:
                conn.close()

    def upsert_content_type(
        self,
        *,
        alias: str,
        name: str,
        icon: str = "□",
        description: str = "",
        fields: Iterable[dict[str, Any] | ContentField] = (),
        allowed_child_aliases: Iterable[str] = (),
        composition_aliases: Iterable[str] = (),
        allow_at_root: bool = False,
        is_element: bool = False,
        template: str = "page",
        updated_by: str,
    ) -> ContentType:
        clean_alias = self._validate_schema_alias(alias, label="Content type alias")
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Content type name is required")
        clean_fields = self._normalize_content_fields(fields)
        clean_allowed = tuple(
            self._validate_schema_alias(item, label="Allowed child alias")
            for item in allowed_child_aliases
            if str(item).strip()
        )
        clean_compositions = tuple(
            self._validate_schema_alias(item, label="Composition alias")
            for item in composition_aliases
            if str(item).strip()
        )
        clean_template = self._validate_schema_alias(template.strip() or "page", label="Template alias")
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                clean_fields = self._resolve_content_field_data_types(conn, clean_fields)
                template_row = conn.execute(
                    "SELECT * FROM archub_templates WHERE alias = ?",
                    (clean_template,),
                ).fetchone()
                if template_row is None:
                    raise ValueError(f"Unknown template: {clean_template}")
                template_model = _template_from_row(template_row)
                if (
                    template_model.allowed_content_type_aliases
                    and clean_alias not in template_model.allowed_content_type_aliases
                ):
                    raise ValueError(f"Template {clean_template} is not allowed for {clean_alias}")
                for composition_alias in clean_compositions:
                    if conn.execute(
                        "SELECT alias FROM archub_content_compositions WHERE alias = ?",
                        (composition_alias,),
                    ).fetchone() is None:
                        raise ValueError(f"Unknown composition: {composition_alias}")
                existing = conn.execute(
                    "SELECT alias, created_at FROM archub_content_types WHERE alias = ?",
                    (clean_alias,),
                ).fetchone()
                created_at = float(existing["created_at"]) if existing is not None else now
                conn.execute(
                    """
                    INSERT INTO archub_content_types (
                        alias, name, icon, description, schema_json,
                        allowed_child_aliases_json, composition_aliases_json,
                        allow_at_root, is_element, template, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(alias) DO UPDATE SET
                        name = excluded.name,
                        icon = excluded.icon,
                        description = excluded.description,
                        schema_json = excluded.schema_json,
                        allowed_child_aliases_json = excluded.allowed_child_aliases_json,
                        composition_aliases_json = excluded.composition_aliases_json,
                        allow_at_root = excluded.allow_at_root,
                        is_element = excluded.is_element,
                        template = excluded.template,
                        updated_at = excluded.updated_at
                    """,
                    (
                        clean_alias,
                        clean_name,
                        icon.strip() or "□",
                        description.strip(),
                        _json_dumps([field.__dict__ for field in clean_fields]),
                        _json_dumps(list(clean_allowed)),
                        _json_dumps(list(clean_compositions)),
                        int(allow_at_root),
                        int(is_element),
                        clean_template,
                        created_at,
                        now,
                    ),
                )
                self._record_activity(
                    conn,
                    action="content_model.type_upserted",
                    actor=updated_by,
                    summary=f"Content type saved: {clean_name}",
                    metadata={
                        "content_type_alias": clean_alias,
                        "fields": [field.alias for field in clean_fields],
                        "compositions": list(clean_compositions),
                        "allowed_child_aliases": list(clean_allowed),
                    },
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM archub_content_types WHERE alias = ?",
                    (clean_alias,),
                ).fetchone()
                return self._hydrate_content_type(conn, row)
            finally:
                conn.close()

    def content_model_report(self) -> dict[str, Any]:
        data_types = self.list_data_types()
        templates = self.list_templates()
        compositions = self.list_content_compositions()
        content_types = self.list_content_types()
        blueprints = self.list_content_blueprints(limit=200)
        return {
            "data_types": [self._data_type_payload(item) for item in data_types],
            "templates": [self._template_payload(item) for item in templates],
            "compositions": [self._composition_payload(item) for item in compositions],
            "content_types": [self._content_type_payload(item) for item in content_types],
            "blueprints": [self._blueprint_payload(item) for item in blueprints],
            "data_type_total": len(data_types),
            "template_total": len(templates),
            "composition_total": len(compositions),
            "content_type_total": len(content_types),
            "blueprint_total": len(blueprints),
            "composed_content_types": sum(1 for item in content_types if item.composition_aliases),
        }

    def list_tree(self, *, include_trashed: bool = False) -> list[ContentNode]:
        with self._lock:
            conn = self._connect()
            try:
                if include_trashed:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_content_nodes
                        ORDER BY level, parent_id IS NOT NULL, parent_id, sort_order, name
                        """
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_content_nodes
                        WHERE status != ?
                        ORDER BY level, parent_id IS NOT NULL, parent_id, sort_order, name
                        """,
                        (_STATUS_TRASHED,),
                    ).fetchall()
                nodes = [_node_from_row(row) for row in rows]
            finally:
                conn.close()

        by_parent: dict[str | None, list[ContentNode]] = {}
        for node in nodes:
            by_parent.setdefault(node.parent_id, []).append(node)

        ordered: list[ContentNode] = []

        def visit(parent_id: str | None) -> None:
            for node in sorted(by_parent.get(parent_id, ()), key=lambda n: (n.sort_order, n.name.lower())):
                ordered.append(node)
                visit(node.node_id)

        visit(None)
        return ordered

    def list_trashed_nodes(self, *, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM archub_content_nodes
                    WHERE status = ?
                    ORDER BY trashed_at DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (_STATUS_TRASHED, limit),
                ).fetchall()
                return [self._trash_payload(row) for row in rows]
            finally:
                conn.close()

    def get_node(self, node_id: str) -> ContentNode | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM archub_content_nodes WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
                return _node_from_row(row) if row is not None else None
            finally:
                conn.close()

    def allowed_child_types(self, parent_id: str | None) -> list[ContentType]:
        content_types = {item.alias: item for item in self.list_content_types()}
        if parent_id is None:
            return [item for item in content_types.values() if item.allow_at_root and not item.is_element]
        parent = self.get_node(parent_id)
        if parent is None:
            return []
        parent_type = content_types.get(parent.content_type_alias)
        if parent_type is None:
            return []
        if parent.node_id == _ROOT_NODE_ID:
            aliases = set(parent_type.allowed_child_aliases) | {
                item.alias for item in content_types.values() if item.allow_at_root
            }
            return [
                item for item in content_types.values()
                if item.alias in aliases and not item.is_element
            ]
        return [
            content_types[alias] for alias in parent_type.allowed_child_aliases
            if alias in content_types and not content_types[alias].is_element
        ]

    def create_node(
        self,
        *,
        parent_id: str | None,
        content_type_alias: str,
        name: str,
        slug: str,
        payload: dict[str, Any],
        created_by: str,
    ) -> ContentNode:
        name = name.strip()
        if not name:
            raise ValueError("Name is required")
        content_type = self.get_content_type(content_type_alias)
        if content_type is None:
            raise ValueError("Unknown content type")
        if content_type.is_element:
            raise ValueError("Element types cannot be created in the content tree")

        allowed = self.allowed_child_types(parent_id)
        if content_type.alias not in {item.alias for item in allowed}:
            raise ValueError("This content type is not allowed here")

        with self._lock:
            conn = self._connect()
            try:
                parent = self._get_node_row(conn, parent_id) if parent_id else None
                parent_route = str(parent["route_path"]) if parent is not None else _PUBLIC_ROOT
                level = int(parent["level"]) + 1 if parent is not None else 1
                sort_order = self._next_sort_order(conn, parent_id)
                final_slug = self._unique_slug(conn, parent_id, slug or name)
                route_path = _route_for(parent_route, final_slug)
                now = _now()
                node_id = secrets.token_urlsafe(10)
                clean_payload = self._clean_payload(content_type, payload)
                conn.execute(
                    """
                    INSERT INTO archub_content_nodes (
                        node_id, parent_id, content_type_alias, name, slug,
                        route_path, level, status, draft_json, published_json,
                        sort_order, created_at, updated_at, published_at,
                        created_by, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        node_id,
                        parent_id,
                        content_type.alias,
                        name,
                        final_slug,
                        route_path,
                        level,
                        _STATUS_DRAFT,
                        _json_dumps(clean_payload),
                        sort_order,
                        now,
                        now,
                        created_by,
                        created_by,
                    ),
                )
                self._add_version(
                    conn,
                    node_id=node_id,
                    status=_STATUS_DRAFT,
                    payload=clean_payload,
                    created_by=created_by,
                    note="Created draft",
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.created",
                    actor=created_by,
                    summary=f"Created {content_type.alias} draft: {name}",
                    metadata={
                        "node_name": name,
                        "route_path": route_path,
                        "content_type_alias": content_type.alias,
                        "parent_id": parent_id or "",
                    },
                )
                conn.commit()
                logger.info("ArcHub content created: %s %s", node_id, route_path)
                return _node_from_row(self._get_node_row(conn, node_id))
            finally:
                conn.close()

    def create_node_from_blueprint(
        self,
        *,
        blueprint_id: str,
        parent_id: str | None,
        name: str,
        slug: str = "",
        payload_overrides: dict[str, Any] | None = None,
        created_by: str,
    ) -> ContentNode:
        blueprint = self.get_content_blueprint(blueprint_id)
        if blueprint is None:
            raise ValueError("Content blueprint not found")
        payload = dict(blueprint.payload)
        if payload_overrides:
            payload.update(payload_overrides)
        node = self.create_node(
            parent_id=parent_id,
            content_type_alias=blueprint.content_type_alias,
            name=name or blueprint.name,
            slug=slug,
            payload=payload,
            created_by=created_by,
        )
        with self._lock:
            conn = self._connect()
            try:
                self._record_activity(
                    conn,
                    node_id=node.node_id,
                    action="content.created_from_blueprint",
                    actor=created_by,
                    summary=f"Created from blueprint: {blueprint.name}",
                    metadata={
                        "blueprint_id": blueprint.blueprint_id,
                        "content_type_alias": blueprint.content_type_alias,
                    },
                )
                conn.commit()
            finally:
                conn.close()
        return node

    def update_node(
        self,
        node_id: str,
        *,
        name: str,
        slug: str,
        payload: dict[str, Any],
        updated_by: str,
    ) -> ContentNode:
        if node_id == _ROOT_NODE_ID:
            slug = ""
        name = name.strip()
        if not name:
            raise ValueError("Name is required")
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                self._assert_content_lock(conn, node_id=node_id, actor=updated_by)
                content_type = self._get_content_type_row(conn, str(row["content_type_alias"]))
                parent = self._get_node_row(conn, str(row["parent_id"])) if row["parent_id"] else None
                parent_route = str(parent["route_path"]) if parent is not None else _PUBLIC_ROOT
                final_slug = "" if node_id == _ROOT_NODE_ID else self._unique_slug(
                    conn,
                    str(row["parent_id"]) if row["parent_id"] else None,
                    slug or name,
                    exclude_id=node_id,
                )
                route_path = _PUBLIC_ROOT if node_id == _ROOT_NODE_ID else _route_for(parent_route, final_slug)
                clean_payload = self._clean_payload(self._hydrate_content_type(conn, content_type), payload)
                now = _now()
                conn.execute(
                    """
                    UPDATE archub_content_nodes
                    SET name = ?, slug = ?, route_path = ?, draft_json = ?,
                        updated_at = ?, updated_by = ?,
                        status = CASE WHEN status = ? THEN ? ELSE status END
                    WHERE node_id = ?
                    """,
                    (
                        name,
                        final_slug,
                        route_path,
                        _json_dumps(clean_payload),
                        now,
                        updated_by,
                        _STATUS_UNPUBLISHED,
                        _STATUS_DRAFT,
                        node_id,
                    ),
                )
                self._refresh_descendant_routes(conn, node_id)
                self._add_version(
                    conn,
                    node_id=node_id,
                    status=_STATUS_DRAFT,
                    payload=clean_payload,
                    created_by=updated_by,
                    note="Saved draft",
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.updated",
                    actor=updated_by,
                    summary=f"Saved draft: {name}",
                    metadata={
                        "node_name": name,
                        "route_path": route_path,
                        "content_type_alias": str(row["content_type_alias"]),
                        "old_route_path": str(row["route_path"]),
                    },
                )
                conn.commit()
                logger.info("ArcHub content updated: %s", node_id)
                return _node_from_row(self._get_node_row(conn, node_id))
            finally:
                conn.close()

    def publish_node(self, node_id: str, *, published_by: str) -> ContentNode:
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                self._assert_content_lock(conn, node_id=node_id, actor=published_by)
                payload = _json_loads_dict(str(row["draft_json"] or "{}"))
                content_type_alias = str(row["content_type_alias"])
                errors = self._validate_payload_for_publish(content_type_alias, payload)
                if errors:
                    raise ValueError("Cannot publish: " + "; ".join(errors))
                now = _now()
                conn.execute(
                    """
                    UPDATE archub_content_nodes
                    SET status = ?, published_json = ?, published_at = ?,
                        updated_at = ?, updated_by = ?
                    WHERE node_id = ?
                    """,
                    (
                        _STATUS_PUBLISHED,
                        _json_dumps(payload),
                        now,
                        now,
                        published_by,
                        node_id,
                    ),
                )
                conn.execute(
                    """
                    UPDATE archub_content_workflows
                    SET state = ?, scheduled_publish_at = NULL,
                        updated_at = ?, updated_by = ?
                    WHERE node_id = ?
                    """,
                    (_STATUS_PUBLISHED, now, published_by, node_id),
                )
                self._add_version(
                    conn,
                    node_id=node_id,
                    status=_STATUS_PUBLISHED,
                    payload=payload,
                    created_by=published_by,
                    note="Published",
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.published",
                    actor=published_by,
                    summary=f"Published: {row['name']}",
                    metadata={
                        "node_name": str(row["name"]),
                        "route_path": str(row["route_path"]),
                        "content_type_alias": content_type_alias,
                    },
                )
                conn.commit()
                logger.info("ArcHub content published: %s", node_id)
                return _node_from_row(self._get_node_row(conn, node_id))
            finally:
                conn.close()

    def validate_node_draft(self, node_id: str) -> list[str]:
        node = self.get_node(node_id)
        if node is None:
            return ["Content node not found"]
        return self._validate_payload_for_publish(node.content_type_alias, node.draft)

    def unpublish_node(self, node_id: str, *, updated_by: str) -> ContentNode:
        if node_id == _ROOT_NODE_ID:
            raise ValueError("Root node cannot be unpublished")
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                self._assert_content_lock(conn, node_id=node_id, actor=updated_by)
                payload = _json_loads_dict(str(row["draft_json"] or "{}"))
                now = _now()
                conn.execute(
                    """
                    UPDATE archub_content_nodes
                    SET status = ?, published_json = NULL, published_at = NULL,
                        updated_at = ?, updated_by = ?
                    WHERE node_id = ?
                    """,
                    (_STATUS_UNPUBLISHED, now, updated_by, node_id),
                )
                conn.execute(
                    """
                    UPDATE archub_content_workflows
                    SET state = ?, scheduled_unpublish_at = NULL,
                        updated_at = ?, updated_by = ?
                    WHERE node_id = ?
                    """,
                    (_STATUS_UNPUBLISHED, now, updated_by, node_id),
                )
                self._add_version(
                    conn,
                    node_id=node_id,
                    status=_STATUS_UNPUBLISHED,
                    payload=payload,
                    created_by=updated_by,
                    note="Unpublished",
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.unpublished",
                    actor=updated_by,
                    summary=f"Unpublished: {row['name']}",
                    metadata={
                        "node_name": str(row["name"]),
                        "route_path": str(row["route_path"]),
                        "content_type_alias": str(row["content_type_alias"]),
                    },
                )
                conn.commit()
                logger.info("ArcHub content unpublished: %s", node_id)
                return _node_from_row(self._get_node_row(conn, node_id))
            finally:
                conn.close()

    def delete_node(self, node_id: str, *, deleted_by: str = "") -> None:
        if node_id == _ROOT_NODE_ID:
            raise ValueError("Root node cannot be deleted")
        with self._lock:
            conn = self._connect()
            try:
                child = conn.execute(
                    """
                    SELECT node_id FROM archub_content_nodes
                    WHERE parent_id = ? AND status != ?
                    LIMIT 1
                    """,
                    (node_id, _STATUS_TRASHED),
                ).fetchone()
                if child is not None:
                    raise ValueError("Delete child nodes first")
                row = self._get_node_row(conn, node_id)
                actor = deleted_by or str(row["updated_by"] or row["created_by"] or "")
                self._assert_content_lock(conn, node_id=node_id, actor=actor)
                if str(row["status"]) == _STATUS_TRASHED:
                    return
                now = _now()
                trash_slug = f"__trash__-{node_id}"
                trash_route = f"{_PUBLIC_ROOT}/__trash__/{node_id}"
                original_status = str(row["status"] or "")
                conn.execute(
                    """
                    UPDATE archub_content_nodes
                    SET parent_id = NULL,
                        slug = ?,
                        route_path = ?,
                        status = ?,
                        published_json = NULL,
                        published_at = NULL,
                        updated_at = ?,
                        updated_by = ?,
                        trashed_at = ?,
                        trashed_by = ?,
                        trashed_original_parent_id = ?,
                        trashed_original_route_path = ?,
                        trashed_original_slug = ?,
                        trashed_original_sort_order = ?,
                        trashed_original_status = ?
                    WHERE node_id = ?
                    """,
                    (
                        trash_slug,
                        trash_route,
                        _STATUS_TRASHED,
                        now,
                        actor,
                        now,
                        actor,
                        str(row["parent_id"]) if row["parent_id"] else None,
                        str(row["route_path"]),
                        str(row["slug"] or ""),
                        int(row["sort_order"] or 0),
                        original_status,
                        node_id,
                    ),
                )
                conn.execute(
                    """
                    UPDATE archub_content_workflows
                    SET state = ?, updated_at = ?, updated_by = ?
                    WHERE node_id = ?
                    """,
                    (_STATUS_TRASHED, now, actor, node_id),
                )
                conn.execute("DELETE FROM archub_content_locks WHERE node_id = ?", (node_id,))
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.deleted",
                    actor=actor,
                    summary=f"Moved to recycle bin: {row['name']}",
                    metadata={
                        "node_name": str(row["name"]),
                        "route_path": str(row["route_path"]),
                        "content_type_alias": str(row["content_type_alias"]),
                        "original_status": original_status,
                    },
                )
                conn.commit()
                logger.info("ArcHub content moved to recycle bin: %s", node_id)
            finally:
                conn.close()

    def restore_trashed_node(self, node_id: str, *, restored_by: str) -> ContentNode:
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                if str(row["status"]) != _STATUS_TRASHED:
                    raise ValueError("Content node is not in recycle bin")
                original_parent_id = str(row["trashed_original_parent_id"]) if row["trashed_original_parent_id"] else None
                original_slug = str(row["trashed_original_slug"] or "")
                original_route = str(row["trashed_original_route_path"] or "")
                if not original_route:
                    raise ValueError("Trashed node has no original route")
                if original_parent_id and conn.execute(
                    "SELECT node_id FROM archub_content_nodes WHERE node_id = ? AND status != ?",
                    (original_parent_id, _STATUS_TRASHED),
                ).fetchone() is None:
                    raise ValueError("Original parent is missing or trashed")
                conflict = conn.execute(
                    """
                    SELECT node_id FROM archub_content_nodes
                    WHERE route_path = ? AND node_id != ?
                    LIMIT 1
                    """,
                    (original_route, node_id),
                ).fetchone()
                if conflict is not None:
                    raise ValueError("Original route is already occupied")
                now = _now()
                conn.execute(
                    """
                    UPDATE archub_content_nodes
                    SET parent_id = ?,
                        slug = ?,
                        route_path = ?,
                        status = ?,
                        updated_at = ?,
                        updated_by = ?,
                        trashed_at = NULL,
                        trashed_by = '',
                        trashed_original_parent_id = NULL,
                        trashed_original_route_path = '',
                        trashed_original_slug = '',
                        trashed_original_sort_order = NULL,
                        trashed_original_status = ''
                    WHERE node_id = ?
                    """,
                    (
                        original_parent_id,
                        original_slug,
                        original_route,
                        _STATUS_DRAFT,
                        now,
                        restored_by,
                        node_id,
                    ),
                )
                self._add_version(
                    conn,
                    node_id=node_id,
                    status=_STATUS_DRAFT,
                    payload=_json_loads_dict(str(row["draft_json"] or "{}")),
                    created_by=restored_by,
                    note="Restored from recycle bin",
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.restored_from_trash",
                    actor=restored_by,
                    summary=f"Restored from recycle bin: {row['name']}",
                    metadata={
                        "node_name": str(row["name"]),
                        "route_path": original_route,
                        "content_type_alias": str(row["content_type_alias"]),
                    },
                )
                conn.commit()
                return _node_from_row(self._get_node_row(conn, node_id))
            finally:
                conn.close()

    def purge_trashed_node(self, node_id: str, *, purged_by: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                if str(row["status"]) != _STATUS_TRASHED:
                    raise ValueError("Only trashed nodes can be purged")
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.purged",
                    actor=purged_by,
                    summary=f"Purged from recycle bin: {row['name']}",
                    metadata={
                        "node_name": str(row["name"]),
                        "route_path": str(row["trashed_original_route_path"] or row["route_path"]),
                        "content_type_alias": str(row["content_type_alias"]),
                    },
                )
                conn.execute("DELETE FROM archub_content_workflows WHERE node_id = ?", (node_id,))
                conn.execute("DELETE FROM archub_content_variants WHERE node_id = ?", (node_id,))
                conn.execute("DELETE FROM archub_content_segments WHERE node_id = ?", (node_id,))
                conn.execute("DELETE FROM archub_content_versions WHERE node_id = ?", (node_id,))
                conn.execute("DELETE FROM archub_content_locks WHERE node_id = ?", (node_id,))
                conn.execute("DELETE FROM archub_content_access WHERE node_id = ?", (node_id,))
                conn.execute("DELETE FROM archub_content_nodes WHERE node_id = ?", (node_id,))
                conn.commit()
                logger.info("ArcHub content purged: %s", node_id)
            finally:
                conn.close()

    def list_versions(self, node_id: str, limit: int = 20) -> list[ContentVersion]:
        limit = max(1, min(int(limit or 20), 500))
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT * FROM archub_content_versions
                    WHERE node_id = ?
                    ORDER BY version_no DESC
                    LIMIT ?
                    """,
                    (node_id, limit),
                ).fetchall()
                return [
                    ContentVersion(
                        version_id=int(row["version_id"]),
                        node_id=str(row["node_id"]),
                        version_no=int(row["version_no"]),
                        status=str(row["status"]),
                        payload=_json_loads_dict(str(row["payload_json"] or "{}")),
                        created_at=float(row["created_at"] or 0.0),
                        created_by=str(row["created_by"] or ""),
                        note=str(row["note"] or ""),
                    )
                    for row in rows
                ]
            finally:
                conn.close()

    def cleanup_content_versions(
        self,
        *,
        node_id: str = "",
        keep_latest: int = 20,
        older_than_seconds: float | None = 60.0 * 60.0 * 24.0 * 90.0,
        actor: str = "system",
    ) -> dict[str, Any]:
        clean_node_id = node_id.strip()
        keep_count = max(1, min(int(keep_latest or 20), 500))
        retention_seconds = (
            None if older_than_seconds is None else max(0.0, float(older_than_seconds))
        )
        cutoff = None if retention_seconds is None else _now() - retention_seconds
        deleted_versions: list[dict[str, Any]] = []
        examined_nodes = 0
        with self._lock:
            conn = self._connect()
            try:
                if clean_node_id:
                    row = self._get_node_row(conn, clean_node_id)
                    node_rows = [{"node_id": str(row["node_id"])}]
                else:
                    node_rows = conn.execute(
                        "SELECT DISTINCT node_id FROM archub_content_versions"
                    ).fetchall()
                for node_row in node_rows:
                    current_node_id = str(node_row["node_id"])
                    examined_nodes += 1
                    versions = conn.execute(
                        """
                        SELECT version_id, node_id, version_no, status, created_at,
                               created_by, note
                        FROM archub_content_versions
                        WHERE node_id = ?
                        ORDER BY version_no DESC
                        """,
                        (current_node_id,),
                    ).fetchall()
                    for version in versions[keep_count:]:
                        created_at = float(version["created_at"] or 0.0)
                        if cutoff is not None and created_at > cutoff:
                            continue
                        deleted_versions.append(
                            {
                                "version_id": int(version["version_id"]),
                                "node_id": str(version["node_id"]),
                                "version_no": int(version["version_no"]),
                                "status": str(version["status"]),
                                "created_at": created_at,
                                "created_by": str(version["created_by"] or ""),
                                "note": str(version["note"] or ""),
                            }
                        )
                if deleted_versions:
                    conn.executemany(
                        "DELETE FROM archub_content_versions WHERE version_id = ?",
                        [(item["version_id"],) for item in deleted_versions],
                    )
                    self._record_activity(
                        conn,
                        node_id=clean_node_id,
                        action="content.versions.cleaned",
                        actor=actor,
                        summary=f"Cleaned {len(deleted_versions)} content versions",
                        metadata={
                            "node_id": clean_node_id,
                            "keep_latest": keep_count,
                            "older_than_seconds": retention_seconds,
                            "deleted_count": len(deleted_versions),
                            "examined_nodes": examined_nodes,
                        },
                    )
                conn.commit()
            finally:
                conn.close()
        return {
            "ok": True,
            "node_id": clean_node_id,
            "keep_latest": keep_count,
            "older_than_seconds": retention_seconds,
            "deleted_count": len(deleted_versions),
            "deleted_versions": deleted_versions[:100],
            "examined_nodes": examined_nodes,
        }

    def list_content_variants(self, node_id: str) -> list[ContentVariant]:
        if self.get_node(node_id) is None:
            raise ValueError("Content node not found")
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT * FROM archub_content_variants
                    WHERE node_id = ?
                    ORDER BY culture
                    """,
                    (node_id,),
                ).fetchall()
                return [_variant_from_row(row) for row in rows]
            finally:
                conn.close()

    def get_content_variant(self, node_id: str, culture: str) -> ContentVariant | None:
        clean_culture = _normalize_culture(culture)
        if not clean_culture:
            raise ValueError("Culture is required")
        with self._lock:
            conn = self._connect()
            try:
                self._get_node_row(conn, node_id)
                row = conn.execute(
                    """
                    SELECT * FROM archub_content_variants
                    WHERE node_id = ? AND culture = ?
                    """,
                    (node_id, clean_culture),
                ).fetchone()
                return _variant_from_row(row) if row is not None else None
            finally:
                conn.close()

    def upsert_content_variant(
        self,
        node_id: str,
        *,
        culture: str,
        payload: dict[str, Any],
        updated_by: str,
    ) -> ContentVariant:
        clean_culture = _normalize_culture(culture)
        if not clean_culture:
            raise ValueError("Culture is required")
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                self._assert_content_lock(conn, node_id=node_id, actor=updated_by)
                content_type = self._get_content_type_row(conn, str(row["content_type_alias"]))
                clean_payload = self._clean_payload(self._hydrate_content_type(conn, content_type), payload)
                now = _now()
                existing = conn.execute(
                    """
                    SELECT created_at FROM archub_content_variants
                    WHERE node_id = ? AND culture = ?
                    """,
                    (node_id, clean_culture),
                ).fetchone()
                created_at = float(existing["created_at"]) if existing is not None else now
                conn.execute(
                    """
                    INSERT INTO archub_content_variants (
                        node_id, culture, status, draft_json, published_json,
                        created_at, updated_at, published_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, NULL, ?, ?, NULL, ?)
                    ON CONFLICT(node_id, culture) DO UPDATE SET
                        status = CASE WHEN status = ? THEN ? ELSE status END,
                        draft_json = excluded.draft_json,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        node_id,
                        clean_culture,
                        _STATUS_DRAFT,
                        _json_dumps(clean_payload),
                        created_at,
                        now,
                        updated_by,
                        _STATUS_UNPUBLISHED,
                        _STATUS_DRAFT,
                    ),
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.variant_updated",
                    actor=updated_by,
                    summary=f"Saved {clean_culture} variant draft: {row['name']}",
                    metadata={
                        "culture": clean_culture,
                        "node_name": str(row["name"]),
                        "route_path": str(row["route_path"]),
                        "content_type_alias": str(row["content_type_alias"]),
                    },
                )
                conn.commit()
                variant = conn.execute(
                    """
                    SELECT * FROM archub_content_variants
                    WHERE node_id = ? AND culture = ?
                    """,
                    (node_id, clean_culture),
                ).fetchone()
                return _variant_from_row(variant)
            finally:
                conn.close()

    def publish_content_variant(
        self,
        node_id: str,
        *,
        culture: str,
        published_by: str,
    ) -> ContentVariant:
        clean_culture = _normalize_culture(culture)
        if not clean_culture:
            raise ValueError("Culture is required")
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                self._assert_content_lock(conn, node_id=node_id, actor=published_by)
                variant = conn.execute(
                    """
                    SELECT * FROM archub_content_variants
                    WHERE node_id = ? AND culture = ?
                    """,
                    (node_id, clean_culture),
                ).fetchone()
                if variant is None:
                    raise ValueError("Content variant not found")
                payload = _json_loads_dict(str(variant["draft_json"] or "{}"))
                content_type_alias = str(row["content_type_alias"])
                errors = self._validate_payload_for_publish(content_type_alias, payload)
                if errors:
                    raise ValueError("Cannot publish variant: " + "; ".join(errors))
                now = _now()
                conn.execute(
                    """
                    UPDATE archub_content_variants
                    SET status = ?, published_json = ?, published_at = ?,
                        updated_at = ?, updated_by = ?
                    WHERE node_id = ? AND culture = ?
                    """,
                    (
                        _STATUS_PUBLISHED,
                        _json_dumps(payload),
                        now,
                        now,
                        published_by,
                        node_id,
                        clean_culture,
                    ),
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.variant_published",
                    actor=published_by,
                    summary=f"Published {clean_culture} variant: {row['name']}",
                    metadata={
                        "culture": clean_culture,
                        "node_name": str(row["name"]),
                        "route_path": str(row["route_path"]),
                        "content_type_alias": content_type_alias,
                    },
                )
                conn.commit()
                published = conn.execute(
                    """
                    SELECT * FROM archub_content_variants
                    WHERE node_id = ? AND culture = ?
                    """,
                    (node_id, clean_culture),
                ).fetchone()
                return _variant_from_row(published)
            finally:
                conn.close()

    def list_content_segments(self, node_id: str) -> list[ContentSegment]:
        with self._lock:
            conn = self._connect()
            try:
                self._get_node_row(conn, node_id)
                rows = conn.execute(
                    """
                    SELECT * FROM archub_content_segments
                    WHERE node_id = ?
                    ORDER BY segment
                    """,
                    (node_id,),
                ).fetchall()
                return [_segment_from_row(row) for row in rows]
            finally:
                conn.close()

    def get_content_segment(self, node_id: str, segment: str) -> ContentSegment | None:
        clean_segment = _normalize_segment(segment)
        with self._lock:
            conn = self._connect()
            try:
                self._get_node_row(conn, node_id)
                row = conn.execute(
                    """
                    SELECT * FROM archub_content_segments
                    WHERE node_id = ? AND segment = ?
                    """,
                    (node_id, clean_segment),
                ).fetchone()
                return _segment_from_row(row) if row is not None else None
            finally:
                conn.close()

    def upsert_content_segment(
        self,
        node_id: str,
        *,
        segment: str,
        payload: dict[str, Any],
        updated_by: str,
    ) -> ContentSegment:
        clean_segment = _normalize_segment(segment)
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                self._assert_content_lock(conn, node_id=node_id, actor=updated_by)
                content_type = self._hydrate_content_type(
                    conn,
                    self._get_content_type_row(conn, str(row["content_type_alias"])),
                )
                clean_payload = self._clean_segment_payload(content_type, payload)
                existing = conn.execute(
                    """
                    SELECT created_at FROM archub_content_segments
                    WHERE node_id = ? AND segment = ?
                    """,
                    (node_id, clean_segment),
                ).fetchone()
                now = _now()
                created_at = float(existing["created_at"]) if existing is not None else now
                conn.execute(
                    """
                    INSERT INTO archub_content_segments (
                        node_id, segment, status, draft_json, published_json,
                        created_at, updated_at, published_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, NULL, ?, ?, NULL, ?)
                    ON CONFLICT(node_id, segment) DO UPDATE SET
                        status = CASE WHEN status = ? THEN ? ELSE status END,
                        draft_json = excluded.draft_json,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        node_id,
                        clean_segment,
                        _STATUS_DRAFT,
                        _json_dumps(clean_payload),
                        created_at,
                        now,
                        updated_by,
                        _STATUS_UNPUBLISHED,
                        _STATUS_DRAFT,
                    ),
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.segment_updated",
                    actor=updated_by,
                    summary=f"Saved {clean_segment} segment draft: {row['name']}",
                    metadata={"segment": clean_segment, "fields": sorted(clean_payload)},
                )
                conn.commit()
                segment_row = conn.execute(
                    """
                    SELECT * FROM archub_content_segments
                    WHERE node_id = ? AND segment = ?
                    """,
                    (node_id, clean_segment),
                ).fetchone()
                return _segment_from_row(segment_row)
            finally:
                conn.close()

    def publish_content_segment(
        self,
        node_id: str,
        *,
        segment: str,
        published_by: str,
    ) -> ContentSegment:
        clean_segment = _normalize_segment(segment)
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                self._assert_content_lock(conn, node_id=node_id, actor=published_by)
                segment_row = conn.execute(
                    """
                    SELECT * FROM archub_content_segments
                    WHERE node_id = ? AND segment = ?
                    """,
                    (node_id, clean_segment),
                ).fetchone()
                if segment_row is None:
                    raise ValueError("Content segment not found")
                payload = _json_loads_dict(str(segment_row["draft_json"] or "{}"))
                if not payload:
                    raise ValueError("Cannot publish empty segment override")
                now = _now()
                conn.execute(
                    """
                    UPDATE archub_content_segments
                    SET status = ?, published_json = ?, published_at = ?,
                        updated_at = ?, updated_by = ?
                    WHERE node_id = ? AND segment = ?
                    """,
                    (
                        _STATUS_PUBLISHED,
                        _json_dumps(payload),
                        now,
                        now,
                        published_by,
                        node_id,
                        clean_segment,
                    ),
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.segment_published",
                    actor=published_by,
                    summary=f"Published {clean_segment} segment: {row['name']}",
                    metadata={"segment": clean_segment, "fields": sorted(payload)},
                )
                conn.commit()
                published = conn.execute(
                    """
                    SELECT * FROM archub_content_segments
                    WHERE node_id = ? AND segment = ?
                    """,
                    (node_id, clean_segment),
                ).fetchone()
                return _segment_from_row(published)
            finally:
                conn.close()

    def list_content_domains(self, *, limit: int = 100) -> list[ContentDomain]:
        limit = max(1, min(limit, 500))
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT d.*, n.name AS root_name, n.route_path AS root_route_path
                    FROM archub_content_domains d
                    LEFT JOIN archub_content_nodes n ON n.node_id = d.root_node_id
                    ORDER BY d.is_default DESC, d.sort_order, d.hostname
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [_domain_from_row(row) for row in rows]
            finally:
                conn.close()

    def get_content_domain(self, domain_id: str) -> ContentDomain | None:
        clean_id = domain_id.strip()
        if not clean_id:
            return None
        with self._lock:
            conn = self._connect()
            try:
                row = self._domain_row(conn, clean_id, by="domain_id", required=False)
                return _domain_from_row(row) if row is not None else None
            finally:
                conn.close()

    def upsert_content_domain(
        self,
        *,
        hostname: str,
        root_node_id: str = _ROOT_NODE_ID,
        culture: str = "",
        is_default: bool = False,
        secure: bool = False,
        sort_order: int = 0,
        updated_by: str,
        domain_id: str = "",
    ) -> ContentDomain:
        clean_hostname = self._normalize_hostname(hostname)
        clean_culture = _normalize_culture(culture)
        clean_root_id = root_node_id.strip() or _ROOT_NODE_ID
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                root = self._get_node_row(conn, clean_root_id)
                if str(root["status"]) == _STATUS_TRASHED:
                    raise ValueError("Domain root cannot be trashed")
                existing = None
                clean_id = domain_id.strip()
                if clean_id:
                    existing = conn.execute(
                        "SELECT domain_id, created_at FROM archub_content_domains WHERE domain_id = ?",
                        (clean_id,),
                    ).fetchone()
                if existing is None:
                    existing = conn.execute(
                        "SELECT domain_id, created_at FROM archub_content_domains WHERE hostname = ?",
                        (clean_hostname,),
                    ).fetchone()
                clean_id = clean_id or (str(existing["domain_id"]) if existing is not None else secrets.token_urlsafe(10))
                created_at = float(existing["created_at"]) if existing is not None else now
                if is_default:
                    conn.execute("UPDATE archub_content_domains SET is_default = 0")
                conn.execute(
                    """
                    INSERT INTO archub_content_domains (
                        domain_id, hostname, root_node_id, culture, is_default,
                        secure, sort_order, created_at, updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(domain_id) DO UPDATE SET
                        hostname = excluded.hostname,
                        root_node_id = excluded.root_node_id,
                        culture = excluded.culture,
                        is_default = excluded.is_default,
                        secure = excluded.secure,
                        sort_order = excluded.sort_order,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        clean_id,
                        clean_hostname,
                        clean_root_id,
                        clean_culture,
                        int(is_default),
                        int(secure),
                        int(sort_order),
                        created_at,
                        now,
                        updated_by,
                    ),
                )
                self._record_activity(
                    conn,
                    node_id=clean_root_id,
                    action="domain.upserted",
                    actor=updated_by,
                    summary=f"Domain saved: {clean_hostname}",
                    metadata={
                        "domain_id": clean_id,
                        "hostname": clean_hostname,
                        "root_node_id": clean_root_id,
                        "culture": clean_culture,
                        "is_default": bool(is_default),
                    },
                )
                conn.commit()
                row = self._domain_row(conn, clean_id, by="domain_id")
                if row is None:
                    raise ValueError("Domain not found after save")
                return _domain_from_row(row)
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Domain hostname already exists: {clean_hostname}") from exc
            finally:
                conn.close()

    def delete_content_domain(self, domain_id: str, *, deleted_by: str) -> bool:
        clean_id = domain_id.strip()
        if not clean_id:
            return False
        with self._lock:
            conn = self._connect()
            try:
                row = self._domain_row(conn, clean_id, by="domain_id", required=False)
                if row is None:
                    return False
                conn.execute("DELETE FROM archub_content_domains WHERE domain_id = ?", (clean_id,))
                self._record_activity(
                    conn,
                    node_id=str(row["root_node_id"] or ""),
                    action="domain.deleted",
                    actor=deleted_by,
                    summary=f"Domain deleted: {row['hostname']}",
                    metadata={
                        "domain_id": clean_id,
                        "hostname": str(row["hostname"] or ""),
                    },
                )
                conn.commit()
                return True
            finally:
                conn.close()

    def resolve_content_domain(self, hostname: str) -> ContentDomain | None:
        candidates = self._domain_hostname_candidates(hostname)
        with self._lock:
            conn = self._connect()
            try:
                for candidate in candidates:
                    row = self._domain_row(conn, candidate, by="hostname", required=False)
                    if row is not None:
                        return _domain_from_row(row)
                row = conn.execute(
                    """
                    SELECT d.*, n.name AS root_name, n.route_path AS root_route_path
                    FROM archub_content_domains d
                    LEFT JOIN archub_content_nodes n ON n.node_id = d.root_node_id
                    WHERE d.is_default = 1
                    ORDER BY d.sort_order, d.hostname
                    LIMIT 1
                    """
                ).fetchone()
                return _domain_from_row(row) if row is not None else None
            finally:
                conn.close()

    def content_domain_report(self, *, limit: int = 100) -> dict[str, Any]:
        domains = self.list_content_domains(limit=limit)
        return {
            "total": len(domains),
            "default": next((item.hostname for item in domains if item.is_default), ""),
            "cultures": sorted({item.culture for item in domains if item.culture}),
            "items": [self._domain_payload(item) for item in domains],
        }

    def export_content_package(
        self,
        *,
        name: str = "ArcHub package",
        description: str = "",
        node_ids: Iterable[str] = (),
        include_descendants: bool = True,
        include_content_model: bool = True,
        include_domains: bool = True,
        include_media: bool = True,
        include_dictionary: bool = True,
        include_redirects: bool = True,
        include_public_access: bool = True,
        include_workflows: bool = True,
        exported_by: str = "system",
    ) -> dict[str, Any]:
        selected_nodes = self._content_package_nodes(
            node_ids=node_ids,
            include_descendants=include_descendants,
        )
        package = {
            "schema_version": _PACKAGE_SCHEMA_VERSION,
            "package_id": secrets.token_urlsafe(12),
            "name": name.strip() or "ArcHub package",
            "description": description.strip(),
            "exported_at": _now(),
            "exported_by": exported_by,
            "includes": {
                "descendants": include_descendants,
                "content_model": include_content_model,
                "domains": include_domains,
                "media": include_media,
                "dictionary": include_dictionary,
                "redirects": include_redirects,
                "public_access": include_public_access,
                "workflows": include_workflows,
            },
            "content_model": self.content_model_report() if include_content_model else {},
            "content": {
                "nodes": [self._node_package_payload(node) for node in selected_nodes],
                "total": len(selected_nodes),
            },
            "domains": self.content_domain_report(limit=1000) if include_domains else {"items": [], "total": 0},
            "media_assets": (
                [self._media_payload(item) for item in self.list_media_assets(limit=1000)]
                if include_media else []
            ),
            "dictionary_items": (
                self.list_dictionary_items(limit=1000)
                if include_dictionary else []
            ),
            "redirects": (
                [item.__dict__ for item in self.list_redirects(limit=1000)]
                if include_redirects else []
            ),
            "public_access": (
                [item.__dict__ for item in self.list_public_access_rules(limit=1000)]
                if include_public_access else []
            ),
            "workflows": self._workflow_package_items(limit=1000) if include_workflows else [],
        }
        package["summary"] = self.inspect_content_package(package)
        with self._lock:
            conn = self._connect()
            try:
                self._record_activity(
                    conn,
                    action="package.exported",
                    actor=exported_by,
                    summary=f"Exported content package: {package['name']}",
                    metadata={
                        "package_id": package["package_id"],
                        "nodes": len(selected_nodes),
                        "content_model": include_content_model,
                    },
                )
                conn.commit()
            finally:
                conn.close()
        return package

    def inspect_content_package(self, package: dict[str, Any]) -> dict[str, Any]:
        issues: list[dict[str, str]] = []
        if str(package.get("schema_version") or "") != _PACKAGE_SCHEMA_VERSION:
            issues.append({"severity": "error", "message": "Unsupported ArcHub package schema version"})
        content = package.get("content") if isinstance(package.get("content"), dict) else {}
        nodes = content.get("nodes") if isinstance(content, dict) else []
        if not isinstance(nodes, list):
            issues.append({"severity": "error", "message": "Package content.nodes must be an array"})
            nodes = []
        model = package.get("content_model") if isinstance(package.get("content_model"), dict) else {}
        model_types = {
            str(item.get("alias") or "")
            for item in model.get("content_types", [])
            if isinstance(item, dict)
        }
        existing_types = {item.alias for item in self.list_content_types()}
        available_types = model_types | existing_types
        node_ids = {str(item.get("node_id") or "") for item in nodes if isinstance(item, dict)}
        route_paths = [str(item.get("route_path") or "") for item in nodes if isinstance(item, dict)]
        duplicate_routes = sorted({path for path in route_paths if path and route_paths.count(path) > 1})
        for path in duplicate_routes:
            issues.append({"severity": "error", "message": f"Duplicate package route path: {path}"})
        for item in nodes:
            if not isinstance(item, dict):
                issues.append({"severity": "error", "message": "Package node must be an object"})
                continue
            alias = str(item.get("content_type_alias") or "")
            if alias not in available_types:
                issues.append({"severity": "error", "message": f"Missing content type for node: {alias}"})
            parent_id = str(item.get("parent_id") or "")
            if parent_id and parent_id not in node_ids and self.get_node(parent_id) is None:
                issues.append({"severity": "warning", "message": f"Parent node is not included: {parent_id}"})
        domains = self._package_items(package.get("domains"))
        packaged_segments = sum(
            len(self._package_items(item.get("segments")))
            for item in nodes
            if isinstance(item, dict)
        )
        return {
            "ok": not any(issue["severity"] == "error" for issue in issues),
            "issue_count": len(issues),
            "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
            "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
            "issues": issues,
            "counts": {
                "data_types": len(model.get("data_types", [])) if isinstance(model, dict) else 0,
                "templates": len(model.get("templates", [])) if isinstance(model, dict) else 0,
                "content_types": len(model.get("content_types", [])) if isinstance(model, dict) else 0,
                "nodes": len(nodes),
                "segments": packaged_segments,
                "domains": len(domains),
                "media_assets": len(self._package_items(package.get("media_assets"))),
                "dictionary_items": len(self._package_items(package.get("dictionary_items"))),
                "redirects": len(self._package_items(package.get("redirects"))),
                "public_access": len(self._package_items(package.get("public_access"))),
                "workflows": len(self._package_items(package.get("workflows"))),
            },
        }

    def plan_content_package_import(
        self,
        package: dict[str, Any],
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        inspection = self.inspect_content_package(package)
        content = package.get("content") if isinstance(package.get("content"), dict) else {}
        nodes = self._package_items(content.get("nodes") if isinstance(content, dict) else [])
        actions: list[dict[str, Any]] = []
        counts = {"create": 0, "update": 0, "skip": 0, "conflict": 0}
        if inspection["ok"]:
            with self._lock:
                conn = self._connect()
                try:
                    for item in sorted(nodes, key=lambda row: (_safe_int(row.get("level")), str(row.get("route_path") or ""))):
                        action = self._plan_package_node_import(conn, item, overwrite=overwrite)
                        counts[str(action["action"])] += 1
                        actions.append(action)
                finally:
                    conn.close()
        conflicts = [item for item in actions if item["action"] == "conflict"]
        return {
            "ok": inspection["ok"] and not conflicts,
            "overwrite": overwrite,
            "inspection": inspection,
            "counts": {
                **counts,
                "total": len(actions),
                "domains": len(self._package_items(package.get("domains"))),
                "dictionary_items": len(self._package_items(package.get("dictionary_items"))),
                "media_assets": len(self._package_items(package.get("media_assets"))),
                "redirects": len(self._package_items(package.get("redirects"))),
                "public_access": len(self._package_items(package.get("public_access"))),
                "workflows": len(self._package_items(package.get("workflows"))),
            },
            "actions": actions,
            "conflicts": conflicts,
        }

    def import_content_package(
        self,
        package: dict[str, Any],
        *,
        imported_by: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        plan = self.plan_content_package_import(package, overwrite=overwrite)
        inspection = plan["inspection"]
        if not inspection["ok"]:
            return {"ok": False, "inspection": inspection, "plan": plan, "imported": {}, "skipped": {}}
        if not plan["ok"]:
            return {"ok": False, "inspection": inspection, "plan": plan, "imported": {}, "skipped": {}}
        imported: dict[str, int] = {}
        skipped: dict[str, int] = {}
        self._import_package_content_model(package, imported_by=imported_by)
        content = package.get("content") if isinstance(package.get("content"), dict) else {}
        node_result = self._import_package_nodes(
            self._package_items(content.get("nodes") if isinstance(content, dict) else []),
            imported_by=imported_by,
            overwrite=overwrite,
        )
        imported.update(node_result["imported"])
        skipped.update(node_result["skipped"])
        id_map = node_result["id_map"]
        imported["domains"] = self._import_package_domains(package, id_map=id_map, imported_by=imported_by)
        imported["dictionary_items"] = self._import_package_dictionary(package, imported_by=imported_by)
        imported["media_assets"] = self._import_package_media(package, imported_by=imported_by)
        imported["redirects"] = self._import_package_redirects(package, imported_by=imported_by)
        imported["public_access"] = self._import_package_access(package, id_map=id_map, imported_by=imported_by)
        imported["workflows"] = self._import_package_workflows(package, id_map=id_map, imported_by=imported_by)
        with self._lock:
            conn = self._connect()
            try:
                self._record_activity(
                    conn,
                    action="package.imported",
                    actor=imported_by,
                    summary=f"Imported content package: {package.get('name') or package.get('package_id') or ''}",
                    metadata={
                        "package_id": str(package.get("package_id") or ""),
                        "imported": imported,
                        "skipped": skipped,
                        "overwrite": overwrite,
                    },
                )
                conn.commit()
            finally:
                conn.close()
        return {
            "ok": True,
            "inspection": inspection,
            "plan": plan,
            "imported": imported,
            "skipped": skipped,
        }

    def restore_version(
        self,
        node_id: str,
        version_no: int,
        *,
        updated_by: str,
    ) -> ContentNode:
        if version_no < 1:
            raise ValueError("Version number is invalid")
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                self._assert_content_lock(conn, node_id=node_id, actor=updated_by)
                version = conn.execute(
                    """
                    SELECT * FROM archub_content_versions
                    WHERE node_id = ? AND version_no = ?
                    """,
                    (node_id, version_no),
                ).fetchone()
                if version is None:
                    raise ValueError("Content version not found")
                content_type = self._get_content_type_row(conn, str(row["content_type_alias"]))
                payload = self._clean_payload(
                    self._hydrate_content_type(conn, content_type),
                    _json_loads_dict(str(version["payload_json"] or "{}")),
                )
                now = _now()
                conn.execute(
                    """
                    UPDATE archub_content_nodes
                    SET draft_json = ?, updated_at = ?, updated_by = ?,
                        status = CASE WHEN status = ? THEN ? ELSE status END
                    WHERE node_id = ?
                    """,
                    (
                        _json_dumps(payload),
                        now,
                        updated_by,
                        _STATUS_UNPUBLISHED,
                        _STATUS_DRAFT,
                        node_id,
                    ),
                )
                self._add_version(
                    conn,
                    node_id=node_id,
                    status=_STATUS_DRAFT,
                    payload=payload,
                    created_by=updated_by,
                    note=f"Restored version {version_no}",
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.restored",
                    actor=updated_by,
                    summary=f"Restored version {version_no}: {row['name']}",
                    metadata={
                        "node_name": str(row["name"]),
                        "route_path": str(row["route_path"]),
                        "content_type_alias": str(row["content_type_alias"]),
                        "version_no": version_no,
                    },
                )
                conn.commit()
                logger.info("ArcHub content restored: %s version %s", node_id, version_no)
                return _node_from_row(self._get_node_row(conn, node_id))
            finally:
                conn.close()

    def duplicate_node(self, node_id: str, *, created_by: str) -> ContentNode:
        if node_id == _ROOT_NODE_ID:
            raise ValueError("Root node cannot be duplicated")
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                content_type = self._get_content_type_row(conn, str(row["content_type_alias"]))
                parent_id = str(row["parent_id"]) if row["parent_id"] else None
                parent = self._get_node_row(conn, parent_id) if parent_id else None
                parent_route = str(parent["route_path"]) if parent is not None else _PUBLIC_ROOT
                payload = self._clean_payload(
                    self._hydrate_content_type(conn, content_type),
                    _json_loads_dict(str(row["draft_json"] or "{}")),
                )
                now = _now()
                name = f"{str(row['name']).strip()} Copy"
                slug = self._unique_slug(conn, parent_id, f"{row['slug'] or row['name']!s}-copy")
                route_path = _route_for(parent_route, slug)
                duplicate_id = secrets.token_urlsafe(10)
                sort_order = self._next_sort_order(conn, parent_id)
                conn.execute(
                    """
                    INSERT INTO archub_content_nodes (
                        node_id, parent_id, content_type_alias, name, slug,
                        route_path, level, status, draft_json, published_json,
                        sort_order, created_at, updated_at, published_at,
                        created_by, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        duplicate_id,
                        parent_id,
                        str(row["content_type_alias"]),
                        name,
                        slug,
                        route_path,
                        int(row["level"] or 1),
                        _STATUS_DRAFT,
                        _json_dumps(payload),
                        sort_order,
                        now,
                        now,
                        created_by,
                        created_by,
                    ),
                )
                self._add_version(
                    conn,
                    node_id=duplicate_id,
                    status=_STATUS_DRAFT,
                    payload=payload,
                    created_by=created_by,
                    note=f"Duplicated from {node_id}",
                )
                self._record_activity(
                    conn,
                    node_id=duplicate_id,
                    action="content.duplicated",
                    actor=created_by,
                    summary=f"Duplicated from {row['name']}",
                    metadata={
                        "node_name": name,
                        "route_path": route_path,
                        "content_type_alias": str(row["content_type_alias"]),
                        "source_node_id": node_id,
                    },
                )
                conn.commit()
                logger.info("ArcHub content duplicated: %s -> %s", node_id, duplicate_id)
                return _node_from_row(self._get_node_row(conn, duplicate_id))
            finally:
                conn.close()

    def create_preview_token(
        self,
        node_id: str,
        *,
        created_by: str,
        ttl_seconds: float = 3600,
        note: str = "",
    ) -> dict[str, Any]:
        ttl = max(60, min(int(float(ttl_seconds or 3600)), 60 * 60 * 24 * 30))
        token = secrets.token_urlsafe(32)
        token_hash = self._preview_token_hash(token)
        now = _now()
        expires_at = now + ttl
        with self._lock:
            conn = self._connect()
            try:
                row = self._get_node_row(conn, node_id)
                if str(row["status"]) == _STATUS_TRASHED:
                    raise ValueError("Trashed content cannot be previewed")
                conn.execute(
                    """
                    INSERT INTO archub_preview_tokens (
                        token_hash, node_id, created_by, created_at,
                        expires_at, revoked_at, revoked_by, note
                    )
                    VALUES (?, ?, ?, ?, ?, NULL, '', ?)
                    """,
                    (
                        token_hash,
                        node_id,
                        created_by,
                        now,
                        expires_at,
                        note.strip(),
                    ),
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.preview_token_created",
                    actor=created_by,
                    summary=f"Created preview token: {row['name']}",
                    metadata={
                        "token_hash": token_hash,
                        "expires_at": expires_at,
                        "ttl_seconds": ttl,
                    },
                )
                conn.commit()
                stored = self._preview_token_row(conn, token_hash)
                if stored is None:
                    raise ValueError("Preview token not found after creation")
                payload = self._preview_token_payload(_preview_token_from_row(stored))
                payload["token"] = token
                payload["preview_url"] = f"/cms/api/preview/{token}"
                return payload
            finally:
                conn.close()

    def resolve_preview_token(
        self,
        token: str,
        *,
        include_children: bool = False,
        max_depth: int = 4,
    ) -> dict[str, Any] | None:
        clean_token = token.strip()
        if not clean_token:
            return None
        token_hash = self._preview_token_hash(clean_token)
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                token_row = conn.execute(
                    """
                    SELECT * FROM archub_preview_tokens
                    WHERE token_hash = ? AND expires_at > ? AND revoked_at IS NULL
                    """,
                    (token_hash, now),
                ).fetchone()
                if token_row is None:
                    return None
                node_row = conn.execute(
                    """
                    SELECT * FROM archub_content_nodes
                    WHERE node_id = ? AND status != ?
                    """,
                    (str(token_row["node_id"]), _STATUS_TRASHED),
                ).fetchone()
                if node_row is None:
                    return None
                stored = self._preview_token_row(conn, token_hash)
                if stored is None:
                    return None
                token_payload = self._preview_token_payload(
                    _preview_token_from_row(stored)
                )
                node = _node_from_row(node_row)
                return {
                    "preview": True,
                    "token": token_payload,
                    "content": self._draft_node_payload(
                        conn,
                        node,
                        include_children=include_children,
                        max_depth=max(0, min(max_depth, 8)),
                    ),
                }
            finally:
                conn.close()

    def list_preview_tokens(
        self,
        *,
        node_id: str = "",
        include_expired: bool = False,
        limit: int = 100,
    ) -> list[ContentPreviewToken]:
        clean_node_id = node_id.strip()
        limit = max(1, min(limit, 1000))
        clauses = ["1 = 1"]
        params: list[Any] = []
        if clean_node_id:
            clauses.append("t.node_id = ?")
            params.append(clean_node_id)
        if not include_expired:
            clauses.append("t.expires_at > ?")
            clauses.append("t.revoked_at IS NULL")
            params.append(_now())
        params.append(limit)
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    f"""
                    SELECT t.*, n.name AS node_name, n.route_path, n.content_type_alias
                    FROM archub_preview_tokens t
                    LEFT JOIN archub_content_nodes n ON n.node_id = t.node_id
                    WHERE {' AND '.join(clauses)}
                    ORDER BY t.created_at DESC
                    LIMIT ?
                    """,
                    tuple(params),
                ).fetchall()
                return [_preview_token_from_row(row) for row in rows]
            finally:
                conn.close()

    def get_preview_token(self, token_hash: str) -> ContentPreviewToken | None:
        clean_hash = token_hash.strip()
        if not clean_hash:
            return None
        with self._lock:
            conn = self._connect()
            try:
                row = self._preview_token_row(conn, clean_hash, required=False)
                return _preview_token_from_row(row) if row is not None else None
            finally:
                conn.close()

    def preview_tokens_report(
        self,
        *,
        node_id: str = "",
        include_expired: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]:
        tokens = self.list_preview_tokens(
            node_id=node_id,
            include_expired=include_expired,
            limit=limit,
        )
        now = _now()
        active = [item for item in tokens if item.revoked_at is None and item.expires_at > now]
        expired = [item for item in tokens if item.revoked_at is None and item.expires_at <= now]
        revoked = [item for item in tokens if item.revoked_at is not None]
        return {
            "total": len(tokens),
            "active": len(active),
            "expired": len(expired),
            "revoked": len(revoked),
            "items": [self._preview_token_payload(item) for item in tokens],
        }

    def revoke_preview_token(self, token_hash: str, *, revoked_by: str) -> bool:
        clean_hash = token_hash.strip()
        if not clean_hash:
            return False
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                row = self._preview_token_row(conn, clean_hash, required=False)
                if row is None:
                    return False
                if row["revoked_at"] is not None:
                    return True
                conn.execute(
                    """
                    UPDATE archub_preview_tokens
                    SET revoked_at = ?, revoked_by = ?
                    WHERE token_hash = ?
                    """,
                    (now, revoked_by, clean_hash),
                )
                self._record_activity(
                    conn,
                    node_id=str(row["node_id"] or ""),
                    action="content.preview_token_revoked",
                    actor=revoked_by,
                    summary=f"Revoked preview token: {row['node_name'] or row['node_id']}",
                    metadata={"token_hash": clean_hash},
                )
                conn.commit()
                return True
            finally:
                conn.close()

    def get_published_by_path(self, route_path: str) -> ContentNode | None:
        route_path = self._normalize_public_path(route_path)
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT * FROM archub_content_nodes
                    WHERE route_path = ? AND status = ?
                    """,
                    (route_path, _STATUS_PUBLISHED),
                ).fetchone()
                return _node_from_row(row) if row is not None else None
            finally:
                conn.close()

    def published_children(self, parent_id: str) -> list[ContentNode]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT * FROM archub_content_nodes
                    WHERE parent_id = ? AND status = ?
                    ORDER BY sort_order, name
                    """,
                    (parent_id, _STATUS_PUBLISHED),
                ).fetchall()
                return [_node_from_row(row) for row in rows]
            finally:
                conn.close()

    def published_content_payload(
        self,
        route_path: str,
        *,
        include_children: bool = False,
        culture: str = "",
        segment: str = "",
    ) -> dict[str, Any] | None:
        node = self.get_published_by_path(route_path)
        if node is None:
            return None
        return self._public_node_payload(
            node,
            include_children=include_children,
            culture=culture,
            segment=segment,
        )

    def published_content_tree(
        self,
        *,
        max_depth: int = 8,
        culture: str = "",
        segment: str = "",
        root_node_id: str = _ROOT_NODE_ID,
    ) -> dict[str, Any]:
        root = self.get_node(root_node_id.strip() or _ROOT_NODE_ID)
        if root is None or not root.is_published:
            return {}
        return self._public_node_payload(
            root,
            include_children=True,
            max_depth=max(1, max_depth),
            culture=culture,
            segment=segment,
        )

    def published_sitemap(self, *, base_url: str = "") -> list[dict[str, str]]:
        base = base_url.rstrip("/")
        items: list[dict[str, str]] = []
        for node in self.list_tree():
            if not node.is_published:
                continue
            priority = "1.0" if node.is_root else "0.8" if node.level <= 1 else "0.6"
            items.append(
                {
                    "loc": f"{base}{node.route_path}" if base else node.route_path,
                    "lastmod": _iso_datetime(node.published_at or node.updated_at),
                    "priority": priority,
                }
            )
        return items

    def published_feed(self, *, base_url: str = "", limit: int = 25) -> list[dict[str, Any]]:
        base = base_url.rstrip("/")
        nodes = [
            node for node in self.list_tree()
            if node.is_published and not node.is_root
        ]
        nodes.sort(key=lambda node: (node.published_at or 0.0, node.updated_at), reverse=True)
        items: list[dict[str, Any]] = []
        for node in nodes[: max(1, min(limit, 100))]:
            payload = node.published
            items.append(
                {
                    "title": _content_title(node, payload),
                    "description": _content_summary(payload),
                    "link": f"{base}{node.route_path}" if base else node.route_path,
                    "guid": node.node_id,
                    "published_at": node.published_at or node.updated_at,
                    "published_at_iso": _iso_datetime(node.published_at or node.updated_at),
                    "tags": list(_content_tags(payload)),
                    "content_type_alias": node.content_type_alias,
                }
            )
        return items

    def published_search(
        self,
        query: str = "",
        *,
        content_type_alias: str = "",
        tag: str = "",
        limit: int = 20,
        culture: str = "",
        segment: str = "",
    ) -> list[dict[str, Any]]:
        tokens = _search_tokens(query)
        tag_key = tag.strip().casefold()
        scored: list[tuple[int, float, str, ContentNode]] = []
        for node in self.list_tree():
            if not node.is_published or node.is_root:
                continue
            if content_type_alias and node.content_type_alias != content_type_alias:
                continue
            payload, _resolved_culture, _culture_fallback, _resolved_segment, _segment_fallback = (
                self._delivery_payload(node, culture=culture, segment=segment)
            )
            tags = _content_tags(payload)
            if tag_key and tag_key not in {item.casefold() for item in tags}:
                continue
            title = _content_title(node, payload)
            summary = _content_summary(payload)
            text = " ".join(
                (
                    title,
                    summary,
                    node.name,
                    node.slug,
                    node.route_path,
                    node.content_type_alias,
                    _json_dumps(payload),
                )
            ).casefold()
            if not tokens:
                score = 1
            else:
                title_text = title.casefold()
                summary_text = summary.casefold()
                score = sum(
                    (5 if _token_in_text(token, title_text) else 0)
                    + (3 if _token_in_text(token, summary_text) else 0)
                    + (1 if _token_in_text(token, text) else 0)
                    for token in tokens
                )
            if score > 0:
                scored.append((score, node.published_at or node.updated_at, node.route_path, node))
        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return [
            self._public_search_payload(node, score=score, culture=culture, segment=segment)
            for score, _ts, _path, node in scored[: max(1, min(limit, 100))]
        ]

    def published_tag_index(self) -> list[dict[str, Any]]:
        tags: dict[str, dict[str, Any]] = {}
        for node in self.list_tree():
            if not node.is_published or node.is_root:
                continue
            for tag in _content_tags(node.published):
                key = tag.casefold()
                row = tags.setdefault(
                    key,
                    {
                        "tag": tag,
                        "slug": _slugify(tag, fallback="tag"),
                        "count": 0,
                        "content_types": {},
                    },
                )
                row["count"] += 1
                content_types = row["content_types"]
                content_types[node.content_type_alias] = content_types.get(node.content_type_alias, 0) + 1
        return sorted(tags.values(), key=lambda item: (-int(item["count"]), str(item["tag"]).casefold()))

    def published_by_tag(self, tag: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.published_search(tag=tag, limit=limit)

    def list_redirects(self, *, active_only: bool = False, limit: int = 200) -> list[ContentRedirect]:
        limit = max(1, min(limit, 1000))
        with self._lock:
            conn = self._connect()
            try:
                if active_only:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_redirect_rules
                        WHERE active = 1
                        ORDER BY source_path
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_redirect_rules
                        ORDER BY active DESC, source_path
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                return [_redirect_from_row(row) for row in rows]
            finally:
                conn.close()

    def resolve_redirect(self, source_path: str) -> ContentRedirect | None:
        source = self._normalize_public_path(source_path).rstrip("/") or _PUBLIC_ROOT
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT * FROM archub_redirect_rules
                    WHERE source_path = ? AND active = 1
                    LIMIT 1
                    """,
                    (source,),
                ).fetchone()
                return _redirect_from_row(row) if row is not None else None
            finally:
                conn.close()

    def upsert_redirect(
        self,
        *,
        source_path: str,
        target_path: str,
        status_code: int = 301,
        active: bool = True,
        note: str = "",
        updated_by: str,
    ) -> ContentRedirect:
        source = self._normalize_public_path(source_path).rstrip("/") or _PUBLIC_ROOT
        target = target_path.strip()
        if target.startswith("/"):
            target = self._normalize_public_path(target).rstrip("/") or _PUBLIC_ROOT
        if not target:
            raise ValueError("Redirect target path is required")
        if source == target:
            raise ValueError("Redirect source and target must be different")
        if status_code not in {301, 302, 307, 308}:
            raise ValueError("Redirect status code must be 301, 302, 307 or 308")
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT redirect_id FROM archub_redirect_rules WHERE source_path = ?",
                    (source,),
                ).fetchone()
                if existing is None:
                    redirect_id = secrets.token_urlsafe(10)
                    conn.execute(
                        """
                        INSERT INTO archub_redirect_rules (
                            redirect_id, source_path, target_path, status_code,
                            active, note, created_at, updated_at, created_by, updated_by
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            redirect_id,
                            source,
                            target,
                            status_code,
                            int(active),
                            note.strip(),
                            now,
                            now,
                            updated_by,
                            updated_by,
                        ),
                    )
                else:
                    redirect_id = str(existing["redirect_id"])
                    conn.execute(
                        """
                        UPDATE archub_redirect_rules
                        SET target_path = ?, status_code = ?, active = ?, note = ?,
                            updated_at = ?, updated_by = ?
                        WHERE redirect_id = ?
                        """,
                        (target, status_code, int(active), note.strip(), now, updated_by, redirect_id),
                    )
                self._record_activity(
                    conn,
                    action="redirect.upserted",
                    actor=updated_by,
                    summary=f"Redirect {source} -> {target}",
                    metadata={
                        "redirect_id": redirect_id,
                        "source_path": source,
                        "target_path": target,
                        "status_code": status_code,
                        "active": active,
                    },
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM archub_redirect_rules WHERE redirect_id = ?",
                    (redirect_id,),
                ).fetchone()
                return _redirect_from_row(row)
            finally:
                conn.close()

    def content_reference_graph(self) -> dict[str, Any]:
        nodes = self.list_tree()
        by_path = {node.route_path.rstrip("/") or _PUBLIC_ROOT: node for node in nodes}
        redirect_sources = {item.source_path for item in self.list_redirects(active_only=True, limit=1000)}
        edges: list[dict[str, Any]] = []
        node_rows = [
            {
                "node_id": node.node_id,
                "name": node.name,
                "route_path": node.route_path,
                "content_type_alias": node.content_type_alias,
                "status": node.status,
            }
            for node in nodes
        ]
        for node in nodes:
            payload = node.published if node.is_published else node.draft
            for link in sorted(_internal_cms_links(payload)):
                target_path = link.rstrip("/") or _PUBLIC_ROOT
                target = by_path.get(target_path)
                edges.append(
                    {
                        "source_id": node.node_id,
                        "source_path": node.route_path,
                        "source_name": node.name,
                        "target_id": target.node_id if target else "",
                        "target_path": target_path,
                        "target_name": target.name if target else "",
                        "resolved_by_redirect": target_path in redirect_sources,
                        "broken": target is None and target_path not in redirect_sources,
                    }
                )
        return {
            "nodes": node_rows,
            "edges": edges,
            "broken_count": sum(1 for edge in edges if edge["broken"]),
        }

    def content_references(self, node_id: str) -> dict[str, Any]:
        node = self.get_node(node_id)
        if node is None:
            raise ValueError("Content node not found")
        graph = self.content_reference_graph()
        path = node.route_path.rstrip("/") or _PUBLIC_ROOT
        return {
            "node": {
                "node_id": node.node_id,
                "name": node.name,
                "route_path": node.route_path,
                "content_type_alias": node.content_type_alias,
                "status": node.status,
            },
            "outgoing": [edge for edge in graph["edges"] if edge["source_id"] == node_id],
            "incoming": [
                edge for edge in graph["edges"]
                if edge["target_id"] == node_id or edge["target_path"] == path
            ],
        }

    def list_activity(
        self,
        *,
        node_id: str = "",
        action: str = "",
        actor: str = "",
        limit: int = 100,
    ) -> list[ContentActivity]:
        limit = max(1, min(limit, 1000))
        filters: list[str] = []
        params: list[Any] = []
        if node_id.strip():
            filters.append("a.node_id = ?")
            params.append(node_id.strip())
        if action.strip():
            filters.append("a.action = ?")
            params.append(action.strip())
        if actor.strip():
            filters.append("a.actor = ?")
            params.append(actor.strip())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    f"""
                    SELECT a.*, n.name AS node_name,
                           n.route_path AS node_route_path,
                           n.content_type_alias AS node_content_type_alias
                    FROM archub_content_activity a
                    LEFT JOIN archub_content_nodes n ON n.node_id = a.node_id
                    {where}
                    ORDER BY a.created_at DESC, a.activity_id DESC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                return [_activity_from_row(row) for row in rows]
            finally:
                conn.close()

    def get_content_lock(self, node_id: str, *, now: float | None = None) -> ContentLock | None:
        now = _now() if now is None else now
        with self._lock:
            conn = self._connect()
            try:
                row = self._active_lock_row(conn, node_id=node_id, now=now)
                return _lock_from_row(row) if row is not None else None
            finally:
                conn.close()

    def list_content_locks(self, *, active_only: bool = True, limit: int = 100) -> list[ContentLock]:
        limit = max(1, min(limit, 1000))
        with self._lock:
            conn = self._connect()
            try:
                if active_only:
                    rows = conn.execute(
                        """
                        SELECT l.*, n.name AS node_name, n.route_path, n.content_type_alias
                        FROM archub_content_locks l
                        LEFT JOIN archub_content_nodes n ON n.node_id = l.node_id
                        WHERE l.expires_at > ?
                        ORDER BY l.expires_at, n.route_path
                        LIMIT ?
                        """,
                        (_now(), limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT l.*, n.name AS node_name, n.route_path, n.content_type_alias
                        FROM archub_content_locks l
                        LEFT JOIN archub_content_nodes n ON n.node_id = l.node_id
                        ORDER BY l.expires_at DESC, n.route_path
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                return [_lock_from_row(row) for row in rows]
            finally:
                conn.close()

    def acquire_content_lock(
        self,
        node_id: str,
        *,
        owner: str,
        ttl_seconds: float = 1800.0,
        note: str = "",
        force: bool = False,
    ) -> ContentLock:
        clean_owner = owner.strip()
        if not clean_owner:
            raise ValueError("Lock owner is required")
        ttl = max(60.0, min(float(ttl_seconds or 1800.0), 86400.0))
        now = _now()
        expires_at = now + ttl
        with self._lock:
            conn = self._connect()
            try:
                self._get_node_row(conn, node_id)
                existing = self._active_lock_row(conn, node_id=node_id, now=now)
                if existing is not None and str(existing["owner"]) != clean_owner and not force:
                    raise ValueError(f"Content is locked by {existing['owner']}")
                token = str(existing["token"]) if existing is not None and str(existing["owner"]) == clean_owner else secrets.token_urlsafe(16)
                conn.execute(
                    """
                    INSERT INTO archub_content_locks (
                        node_id, owner, token, note, acquired_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        owner = excluded.owner,
                        token = excluded.token,
                        note = excluded.note,
                        acquired_at = excluded.acquired_at,
                        expires_at = excluded.expires_at
                    """,
                    (node_id, clean_owner, token, note.strip(), now, expires_at),
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.locked",
                    actor=clean_owner,
                    summary=f"Locked content for editing: {node_id}",
                    metadata={
                        "ttl_seconds": ttl,
                        "expires_at": expires_at,
                        "force": force,
                    },
                )
                conn.commit()
                row = self._active_lock_row(conn, node_id=node_id, now=now)
                return _lock_from_row(row)
            finally:
                conn.close()

    def release_content_lock(self, node_id: str, *, owner: str, force: bool = False) -> None:
        clean_owner = owner.strip()
        if not clean_owner:
            raise ValueError("Lock owner is required")
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT * FROM archub_content_locks WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
                if existing is None:
                    return
                if str(existing["owner"]) != clean_owner and not force:
                    raise ValueError(f"Content is locked by {existing['owner']}")
                conn.execute("DELETE FROM archub_content_locks WHERE node_id = ?", (node_id,))
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="content.unlocked",
                    actor=clean_owner,
                    summary=f"Released content lock: {node_id}",
                    metadata={"force": force},
                )
                conn.commit()
            finally:
                conn.close()

    def available_permission_actions(self) -> tuple[str, ...]:
        return _CONTENT_PERMISSION_ACTIONS

    def list_content_permissions(
        self,
        *,
        subject: str = "",
        node_id: str = "",
        limit: int = 100,
    ) -> list[ContentPermissionRule]:
        clean_subject = self._normalize_permission_subject(subject) if subject.strip() else ""
        clean_node_id = node_id.strip()
        limit = max(1, min(limit, 1000))
        filters: list[str] = []
        params: list[Any] = []
        if clean_subject:
            filters.append("p.subject = ?")
            params.append(clean_subject)
        if clean_node_id:
            filters.append("p.scope_node_id = ?")
            params.append(clean_node_id)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    f"""
                    SELECT p.*, n.name AS node_name,
                           n.route_path AS route_path,
                           n.content_type_alias AS content_type_alias
                    FROM archub_content_permissions p
                    LEFT JOIN archub_content_nodes n ON n.node_id = p.scope_node_id
                    {where}
                    ORDER BY p.updated_at DESC, p.subject, n.route_path
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                return [_permission_rule_from_row(row) for row in rows]
            finally:
                conn.close()

    def grant_content_permission(
        self,
        *,
        subject: str,
        actions: Iterable[str],
        scope_node_id: str = "",
        include_descendants: bool = True,
        note: str = "",
        updated_by: str,
        rule_id: str = "",
    ) -> ContentPermissionRule:
        clean_subject = self._normalize_permission_subject(subject)
        clean_actions = self._normalize_permission_actions(actions)
        clean_scope = scope_node_id.strip()
        if not clean_actions:
            raise ValueError("At least one permission action is required")
        now = _now()
        clean_rule_id = rule_id.strip() or secrets.token_urlsafe(12)
        with self._lock:
            conn = self._connect()
            try:
                if clean_scope:
                    self._get_node_row(conn, clean_scope)
                existing = conn.execute(
                    "SELECT created_at FROM archub_content_permissions WHERE rule_id = ?",
                    (clean_rule_id,),
                ).fetchone()
                created_at = float(existing["created_at"]) if existing is not None else now
                conn.execute(
                    """
                    INSERT INTO archub_content_permissions (
                        rule_id, subject, scope_node_id, actions_json,
                        include_descendants, note, created_at, updated_at,
                        updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(rule_id) DO UPDATE SET
                        subject = excluded.subject,
                        scope_node_id = excluded.scope_node_id,
                        actions_json = excluded.actions_json,
                        include_descendants = excluded.include_descendants,
                        note = excluded.note,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        clean_rule_id,
                        clean_subject,
                        clean_scope,
                        _json_dumps(list(clean_actions)),
                        int(include_descendants),
                        note.strip(),
                        created_at,
                        now,
                        updated_by,
                    ),
                )
                self._record_activity(
                    conn,
                    action="permissions.granted",
                    actor=updated_by,
                    summary=f"Granted ArcHub permissions to {clean_subject}",
                    metadata={
                        "rule_id": clean_rule_id,
                        "subject": clean_subject,
                        "scope_node_id": clean_scope,
                        "actions": list(clean_actions),
                        "include_descendants": include_descendants,
                    },
                )
                conn.commit()
                row = self._permission_rule_row(conn, clean_rule_id)
                return _permission_rule_from_row(row)
            finally:
                conn.close()

    def revoke_content_permission(self, rule_id: str, *, revoked_by: str) -> bool:
        clean_rule_id = rule_id.strip()
        if not clean_rule_id:
            return False
        with self._lock:
            conn = self._connect()
            try:
                row = self._permission_rule_row(conn, clean_rule_id, required=False)
                if row is None:
                    return False
                conn.execute("DELETE FROM archub_content_permissions WHERE rule_id = ?", (clean_rule_id,))
                self._record_activity(
                    conn,
                    action="permissions.revoked",
                    actor=revoked_by,
                    summary=f"Revoked ArcHub permissions from {row['subject']}",
                    metadata={
                        "rule_id": clean_rule_id,
                        "subject": str(row["subject"] or ""),
                    },
                )
                conn.commit()
                return True
            finally:
                conn.close()

    def has_any_content_permission(self, username: str) -> bool:
        subjects = self._permission_subject_candidates(username)
        if not subjects:
            return False
        placeholders = ",".join("?" for _ in subjects)
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    f"""
                    SELECT 1
                    FROM archub_content_permissions
                    WHERE subject IN ({placeholders})
                    LIMIT 1
                    """,
                    tuple(subjects),
                ).fetchone()
                return row is not None
            finally:
                conn.close()

    def can_user_perform(
        self,
        *,
        username: str,
        is_admin: bool,
        action: str,
        node_id: str = "",
    ) -> bool:
        if is_admin:
            return True
        clean_action = self._normalize_permission_action(action)
        subjects = self._permission_subject_candidates(username)
        if not subjects:
            return False
        placeholders = ",".join("?" for _ in subjects)
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    f"""
                    SELECT *
                    FROM archub_content_permissions
                    WHERE subject IN ({placeholders})
                    """,
                    tuple(subjects),
                ).fetchall()
                for row in rows:
                    actions = set(_json_loads_list(str(row["actions_json"] or "[]")))
                    if "admin" not in actions and clean_action not in actions:
                        continue
                    if not node_id.strip():
                        return True
                    if self._permission_scope_matches(conn, row, node_id.strip()):
                        return True
                return False
            finally:
                conn.close()

    def content_permissions_report(self, *, limit: int = 100) -> dict[str, Any]:
        rules = self.list_content_permissions(limit=limit)
        return {
            "actions": list(_CONTENT_PERMISSION_ACTIONS),
            "items": [rule.__dict__ for rule in rules],
            "total": len(rules),
            "subjects": sorted({rule.subject for rule in rules}),
        }

    def available_public_access_policies(self) -> tuple[str, ...]:
        return _PUBLIC_ACCESS_POLICIES

    def list_public_access_rules(self, *, limit: int = 100) -> list[ContentAccessRule]:
        limit = max(1, min(limit, 1000))
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT a.*, n.name AS node_name,
                           n.route_path AS route_path,
                           n.content_type_alias AS content_type_alias
                    FROM archub_content_access a
                    LEFT JOIN archub_content_nodes n ON n.node_id = a.node_id
                    ORDER BY a.updated_at DESC, n.route_path
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [_access_rule_from_row(row) for row in rows]
            finally:
                conn.close()

    def set_public_access_rule(
        self,
        node_id: str,
        *,
        policy: str,
        member_groups: Iterable[str] = (),
        include_descendants: bool = True,
        login_path: str = "/login",
        denied_path: str = "",
        note: str = "",
        updated_by: str,
    ) -> ContentAccessRule | None:
        clean_policy = policy.strip().lower().replace("-", "_") or "public"
        if clean_policy not in _PUBLIC_ACCESS_POLICIES:
            raise ValueError(f"Unknown public access policy: {policy}")
        clean_groups = tuple(
            sorted({str(item).strip().lower() for item in member_groups if str(item).strip()})
        )
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                self._get_node_row(conn, node_id)
                if clean_policy == "public":
                    conn.execute("DELETE FROM archub_content_access WHERE node_id = ?", (node_id,))
                    self._record_activity(
                        conn,
                        node_id=node_id,
                        action="access.public",
                        actor=updated_by,
                        summary=f"Removed public access protection: {node_id}",
                        metadata={"node_id": node_id},
                    )
                    conn.commit()
                    return None
                if clean_policy == "members" and not clean_groups:
                    raise ValueError("Members access requires at least one member group")
                conn.execute(
                    """
                    INSERT INTO archub_content_access (
                        node_id, policy, member_groups_json, include_descendants,
                        login_path, denied_path, note, updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        policy = excluded.policy,
                        member_groups_json = excluded.member_groups_json,
                        include_descendants = excluded.include_descendants,
                        login_path = excluded.login_path,
                        denied_path = excluded.denied_path,
                        note = excluded.note,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        node_id,
                        clean_policy,
                        _json_dumps(list(clean_groups)),
                        int(include_descendants),
                        login_path.strip() or "/login",
                        denied_path.strip(),
                        note.strip(),
                        now,
                        updated_by,
                    ),
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="access.protected",
                    actor=updated_by,
                    summary=f"Updated public access protection: {node_id}",
                    metadata={
                        "node_id": node_id,
                        "policy": clean_policy,
                        "member_groups": list(clean_groups),
                        "include_descendants": include_descendants,
                    },
                )
                conn.commit()
                row = self._access_rule_row_for_node(conn, node_id)
                return _access_rule_from_row(row)
            finally:
                conn.close()

    def remove_public_access_rule(self, node_id: str, *, updated_by: str) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT node_id FROM archub_content_access WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
                if existing is None:
                    return False
                conn.execute("DELETE FROM archub_content_access WHERE node_id = ?", (node_id,))
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="access.public",
                    actor=updated_by,
                    summary=f"Removed public access protection: {node_id}",
                    metadata={"node_id": node_id},
                )
                conn.commit()
                return True
            finally:
                conn.close()

    def get_public_access_rule(self, node_id: str, *, inherited: bool = True) -> ContentAccessRule | None:
        clean_node_id = node_id.strip()
        if not clean_node_id:
            return None
        with self._lock:
            conn = self._connect()
            try:
                self._get_node_row(conn, clean_node_id)
                if not inherited:
                    row = self._access_rule_row_for_node(conn, clean_node_id, required=False)
                    return _access_rule_from_row(row) if row is not None else None
                row = self._effective_access_rule_row(conn, clean_node_id)
                return _access_rule_from_row(row) if row is not None else None
            finally:
                conn.close()

    def public_access_report(self, *, limit: int = 100) -> dict[str, Any]:
        rules = self.list_public_access_rules(limit=limit)
        return {
            "policies": list(_PUBLIC_ACCESS_POLICIES),
            "items": [rule.__dict__ for rule in rules],
            "protected": sum(1 for rule in rules if rule.policy != "public"),
            "total": len(rules),
        }

    def can_access_public_content(
        self,
        node_id: str,
        *,
        username: str = "",
        authenticated: bool = False,
        member_groups: Iterable[str] = (),
    ) -> bool:
        rule = self.get_public_access_rule(node_id)
        if rule is None or rule.policy == "public":
            return True
        if rule.policy == "authenticated":
            return authenticated
        if rule.policy == "members":
            if not authenticated:
                return False
            subjects = {str(item).strip().lower() for item in member_groups if str(item).strip()}
            clean_username = username.strip().lower()
            if clean_username:
                subjects.update({clean_username, f"user:{clean_username}"})
            return bool(subjects.intersection(rule.member_groups))
        return False

    def list_webhooks(self, *, active_only: bool = False, limit: int = 100) -> list[ContentWebhook]:
        limit = max(1, min(limit, 1000))
        with self._lock:
            conn = self._connect()
            try:
                if active_only:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_webhooks
                        WHERE active = 1
                        ORDER BY name
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_webhooks
                        ORDER BY active DESC, name
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                return [_webhook_from_row(row) for row in rows]
            finally:
                conn.close()

    def upsert_webhook(
        self,
        *,
        name: str,
        target_url: str,
        events: Iterable[str],
        secret: str = "",
        active: bool = True,
        timeout_seconds: float = 5.0,
        max_attempts: int = 5,
        updated_by: str,
        webhook_id: str = "",
    ) -> ContentWebhook:
        clean_name = name.strip()
        clean_url = target_url.strip()
        clean_events = self._normalize_webhook_events(events)
        if not clean_name:
            raise ValueError("Webhook name is required")
        if not clean_url.startswith(("http://", "https://")):
            raise ValueError("Webhook target URL must start with http:// or https://")
        timeout = max(0.5, min(float(timeout_seconds or 5.0), 60.0))
        attempts = max(1, min(int(max_attempts or 5), 25))
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                existing = None
                if webhook_id.strip():
                    existing = conn.execute(
                        "SELECT * FROM archub_webhooks WHERE webhook_id = ?",
                        (webhook_id.strip(),),
                    ).fetchone()
                if existing is None:
                    existing = conn.execute(
                        "SELECT * FROM archub_webhooks WHERE name = ?",
                        (clean_name,),
                    ).fetchone()

                final_id = str(existing["webhook_id"]) if existing is not None else secrets.token_urlsafe(10)
                final_secret = secret.strip()
                if existing is not None and not final_secret:
                    final_secret = str(existing["secret"] or "")

                conn.execute(
                    """
                    INSERT INTO archub_webhooks (
                        webhook_id, name, target_url, events_json, secret, active,
                        timeout_seconds, max_attempts, created_at, updated_at,
                        created_by, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(webhook_id) DO UPDATE SET
                        name = excluded.name,
                        target_url = excluded.target_url,
                        events_json = excluded.events_json,
                        secret = excluded.secret,
                        active = excluded.active,
                        timeout_seconds = excluded.timeout_seconds,
                        max_attempts = excluded.max_attempts,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        final_id,
                        clean_name,
                        clean_url,
                        _json_dumps(list(clean_events)),
                        final_secret,
                        int(active),
                        timeout,
                        attempts,
                        now,
                        now,
                        updated_by,
                        updated_by,
                    ),
                )
                self._record_activity(
                    conn,
                    action="webhook.upserted",
                    actor=updated_by,
                    summary=f"Webhook saved: {clean_name}",
                    metadata={
                        "webhook_id": final_id,
                        "name": clean_name,
                        "target_url": clean_url,
                        "events": list(clean_events),
                        "active": active,
                    },
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM archub_webhooks WHERE webhook_id = ?",
                    (final_id,),
                ).fetchone()
                return _webhook_from_row(row)
            finally:
                conn.close()

    def list_webhook_deliveries(
        self,
        *,
        status: str = "",
        webhook_id: str = "",
        event_type: str = "",
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        limit = max(1, min(limit, 1000))
        filters: list[str] = []
        params: list[Any] = []
        if status.strip():
            filters.append("d.status = ?")
            params.append(status.strip())
        if webhook_id.strip():
            filters.append("d.webhook_id = ?")
            params.append(webhook_id.strip())
        if event_type.strip():
            filters.append("d.event_type = ?")
            params.append(event_type.strip())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    f"""
                    SELECT d.*, w.name AS webhook_name, w.target_url AS target_url
                    FROM archub_webhook_deliveries d
                    LEFT JOIN archub_webhooks w ON w.webhook_id = d.webhook_id
                    {where}
                    ORDER BY d.created_at DESC, d.delivery_id DESC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                return [_delivery_from_row(row) for row in rows]
            finally:
                conn.close()

    def webhook_report(self, *, limit: int = 100) -> dict[str, Any]:
        deliveries = self.list_webhook_deliveries(limit=limit)
        webhooks = self.list_webhooks(limit=limit)
        statuses = {
            status: sum(1 for item in deliveries if item.status == status)
            for status in ("pending", "retry", "delivered", "failed")
        }
        return {
            "webhooks": [item.__dict__ for item in webhooks],
            "deliveries": [item.__dict__ for item in deliveries],
            "total": len(webhooks),
            "active": sum(1 for item in webhooks if item.active),
            "statuses": statuses,
            "pending": statuses["pending"] + statuses["retry"],
            "failed": statuses["failed"],
        }

    def dispatch_webhook_deliveries(
        self,
        *,
        now: float | None = None,
        limit: int = 50,
        sender: Callable[[str, dict[str, Any], dict[str, str], float], int] | None = None,
    ) -> dict[str, Any]:
        now = _now() if now is None else now
        limit = max(1, min(limit, 200))
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT d.*, w.name AS webhook_name, w.target_url AS target_url,
                           w.secret AS secret, w.timeout_seconds AS timeout_seconds,
                           w.max_attempts AS max_attempts
                    FROM archub_webhook_deliveries d
                    JOIN archub_webhooks w ON w.webhook_id = d.webhook_id
                    WHERE w.active = 1
                      AND d.status IN ('pending', 'retry')
                      AND d.next_attempt_at <= ?
                      AND d.attempts < w.max_attempts
                    ORDER BY d.next_attempt_at, d.delivery_id
                    LIMIT ?
                    """,
                    (now, limit),
                ).fetchall()
                result: dict[str, Any] = {
                    "processed_count": 0,
                    "delivered": [],
                    "retry": [],
                    "failed": [],
                }
                for row in rows:
                    delivery_id = int(row["delivery_id"])
                    event_type = str(row["event_type"])
                    payload = _json_loads_dict(str(row["payload_json"] or "{}"))
                    attempts = int(row["attempts"] or 0) + 1
                    max_attempts = max(1, int(row["max_attempts"] or 5))
                    target_url = str(row["target_url"] or "")
                    timeout = float(row["timeout_seconds"] or 5.0)
                    headers = self._webhook_headers(
                        delivery_id=delivery_id,
                        event_type=event_type,
                        payload=payload,
                        secret=str(row["secret"] or ""),
                    )
                    try:
                        status_code = (
                            sender(target_url, payload, headers, timeout)
                            if sender is not None
                            else self._send_webhook(target_url, payload, headers, timeout)
                        )
                        if 200 <= int(status_code) < 300:
                            conn.execute(
                                """
                                UPDATE archub_webhook_deliveries
                                SET status = 'delivered', attempts = ?,
                                    last_error = '', updated_at = ?, delivered_at = ?
                                WHERE delivery_id = ?
                                """,
                                (attempts, now, now, delivery_id),
                            )
                            result["delivered"].append({"delivery_id": delivery_id, "status_code": int(status_code)})
                            continue
                        raise RuntimeError(f"HTTP {status_code}")
                    except Exception as exc:
                        failed = attempts >= max_attempts
                        status = "failed" if failed else "retry"
                        delay = min(3600.0, 60.0 * (2 ** max(0, attempts - 1)))
                        next_attempt_at = now if failed else now + delay
                        error = str(exc)[:500]
                        conn.execute(
                            """
                            UPDATE archub_webhook_deliveries
                            SET status = ?, attempts = ?, next_attempt_at = ?,
                                last_error = ?, updated_at = ?
                            WHERE delivery_id = ?
                            """,
                            (status, attempts, next_attempt_at, error, now, delivery_id),
                        )
                        result[status].append({"delivery_id": delivery_id, "error": error})
                result["processed_count"] = len(rows)
                conn.commit()
                return result
            finally:
                conn.close()

    def get_workflow(self, node_id: str) -> ContentWorkflow:
        node = self.get_node(node_id)
        if node is None:
            raise ValueError("Content node not found")
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM archub_content_workflows WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
                if row is not None:
                    return _workflow_from_row(row)
            finally:
                conn.close()
        return ContentWorkflow(
            node_id=node_id,
            state=node.status if node.status in _WORKFLOW_STATES else "draft",
            assigned_to="",
            scheduled_publish_at=None,
            scheduled_unpublish_at=None,
            note="",
            updated_at=node.updated_at,
            updated_by=node.updated_by,
        )

    def upsert_workflow(
        self,
        *,
        node_id: str,
        state: str,
        assigned_to: str = "",
        scheduled_publish_at: float | None = None,
        scheduled_unpublish_at: float | None = None,
        note: str = "",
        updated_by: str,
    ) -> ContentWorkflow:
        clean_state = state.strip().lower() or "draft"
        if clean_state not in _WORKFLOW_STATES:
            raise ValueError(f"Unknown workflow state: {state}")
        if (
            scheduled_publish_at is not None
            and scheduled_unpublish_at is not None
            and scheduled_unpublish_at <= scheduled_publish_at
        ):
            raise ValueError("Scheduled unpublish must be later than scheduled publish")
        with self._lock:
            conn = self._connect()
            try:
                self._get_node_row(conn, node_id)
                now = _now()
                conn.execute(
                    """
                    INSERT INTO archub_content_workflows (
                        node_id, state, assigned_to, scheduled_publish_at,
                        scheduled_unpublish_at, note, updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        state = excluded.state,
                        assigned_to = excluded.assigned_to,
                        scheduled_publish_at = excluded.scheduled_publish_at,
                        scheduled_unpublish_at = excluded.scheduled_unpublish_at,
                        note = excluded.note,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (
                        node_id,
                        clean_state,
                        assigned_to.strip(),
                        scheduled_publish_at,
                        scheduled_unpublish_at,
                        note.strip(),
                        now,
                        updated_by,
                    ),
                )
                self._record_activity(
                    conn,
                    node_id=node_id,
                    action="workflow.updated",
                    actor=updated_by,
                    summary=f"Workflow set to {clean_state}",
                    metadata={
                        "state": clean_state,
                        "assigned_to": assigned_to.strip(),
                        "scheduled_publish_at": scheduled_publish_at,
                        "scheduled_unpublish_at": scheduled_unpublish_at,
                        "note": note.strip(),
                    },
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM archub_content_workflows WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
                return _workflow_from_row(row)
            finally:
                conn.close()

    def workflow_report(self, *, now: float | None = None, limit: int = 200) -> dict[str, Any]:
        now = _now() if now is None else now
        limit = max(1, min(limit, 1000))
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT w.*, n.name, n.route_path, n.status AS content_status,
                           n.content_type_alias
                    FROM archub_content_workflows w
                    JOIN archub_content_nodes n ON n.node_id = w.node_id
                    ORDER BY
                        CASE WHEN w.scheduled_publish_at IS NULL THEN 1 ELSE 0 END,
                        w.scheduled_publish_at,
                        w.updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            finally:
                conn.close()
        items: list[dict[str, Any]] = []
        for row in rows:
            workflow = _workflow_from_row(row)
            publish_due = bool(workflow.scheduled_publish_at and workflow.scheduled_publish_at <= now)
            unpublish_due = bool(workflow.scheduled_unpublish_at and workflow.scheduled_unpublish_at <= now)
            items.append(
                {
                    **workflow.__dict__,
                    "name": str(row["name"]),
                    "route_path": str(row["route_path"]),
                    "content_status": str(row["content_status"]),
                    "content_type_alias": str(row["content_type_alias"]),
                    "publish_due": publish_due,
                    "unpublish_due": unpublish_due,
                }
            )
        return {
            "states": {state: sum(1 for item in items if item["state"] == state) for state in sorted(_WORKFLOW_STATES)},
            "items": items,
            "total": len(items),
            "due": sum(1 for item in items if item["publish_due"] or item["unpublish_due"]),
        }

    def apply_due_workflows(self, *, now: float | None = None, updated_by: str = "system") -> dict[str, Any]:
        now = _now() if now is None else now
        report = self.workflow_report(now=now, limit=1000)
        applied: list[dict[str, str]] = []
        errors: list[dict[str, str]] = []
        for item in report["items"]:
            node_id = str(item["node_id"])
            state = str(item["state"])
            assigned_to = str(item["assigned_to"])
            note = str(item["note"])
            scheduled_publish_at = item["scheduled_publish_at"]
            scheduled_unpublish_at = item["scheduled_unpublish_at"]
            try:
                if item["publish_due"]:
                    self.publish_node(node_id, published_by=updated_by)
                    scheduled_publish_at = None
                    state = "published"
                    applied.append({"node_id": node_id, "action": "publish"})
                if item["unpublish_due"]:
                    self.unpublish_node(node_id, updated_by=updated_by)
                    scheduled_unpublish_at = None
                    state = "unpublished"
                    applied.append({"node_id": node_id, "action": "unpublish"})
                if item["publish_due"] or item["unpublish_due"]:
                    self.upsert_workflow(
                        node_id=node_id,
                        state=state,
                        assigned_to=assigned_to,
                        scheduled_publish_at=scheduled_publish_at,
                        scheduled_unpublish_at=scheduled_unpublish_at,
                        note=note,
                        updated_by=updated_by,
                    )
            except Exception as exc:
                logger.warning("ArcHub workflow due action failed: %s", node_id, exc_info=True)
                errors.append({"node_id": node_id, "error": str(exc)})
        return {"applied": applied, "errors": errors, "applied_count": len(applied), "error_count": len(errors)}

    def content_health_report(self) -> dict[str, Any]:
        issues: list[ContentAuditIssue] = []
        nodes = self.list_tree()
        types = {content_type.alias: content_type for content_type in self.list_content_types()}
        published_paths = {node.route_path.rstrip("/") or _PUBLIC_ROOT for node in nodes if node.is_published}
        builder = None

        for node in nodes:
            content_type = types.get(node.content_type_alias)
            payload = node.published if node.is_published else node.draft
            if content_type is None:
                issues.append(self._audit_issue(node, "error", "Content type is missing."))
                continue
            template = self.get_template(content_type.template)
            if template is None:
                issues.append(self._audit_issue(node, "error", f"Template is missing: {content_type.template}"))
            elif (
                template.allowed_content_type_aliases
                and content_type.alias not in template.allowed_content_type_aliases
            ):
                issues.append(
                    self._audit_issue(
                        node,
                        "error",
                        f"Template {template.alias} is not allowed for {content_type.alias}",
                    )
                )
            if not node.is_root and node.status != _STATUS_PUBLISHED:
                issues.append(self._audit_issue(node, "info", "Node is not published."))
            for error in self._validate_payload_for_publish(node.content_type_alias, node.draft):
                issues.append(self._audit_issue(node, "error", error))

            title = str(payload.get("title") or payload.get("hero_title") or node.name).strip()
            if not title:
                issues.append(self._audit_issue(node, "warning", "Content has no title."))
            if content_type.template in {"page", "landing", "article", "expert"} and not node.is_root:
                body = _plain_text(payload.get("body"))
                blocks = payload.get("builder_blocks")
                has_blocks = bool(blocks)
                if len(body) < 40 and not has_blocks:
                    issues.append(self._audit_issue(node, "warning", "Content body is short and has no builder blocks."))
                seo_description = str(payload.get("seo_description") or payload.get("excerpt") or "").strip()
                if node.is_published and content_type.alias == "page" and len(seo_description) < 40:
                    issues.append(self._audit_issue(node, "info", "Published page has a short SEO description."))

            if content_type.field("builder_blocks") is not None:
                if builder is None:
                    from archub_cms.services.content_builder import (
                        get_archub_content_builder_service,
                    )

                    builder = get_archub_content_builder_service()
                blocks = builder.parse_blocks(payload.get("builder_blocks"))
                for issue in builder.audit_blocks(blocks):
                    if blocks or issue.severity == "error":
                        issues.append(
                            self._audit_issue(
                                node,
                                issue.severity,
                                f"Content Builder: {issue.message}",
                            )
                        )

            for link in _internal_cms_links(payload):
                target_path = link.rstrip("/") or _PUBLIC_ROOT
                if target_path not in published_paths and self.resolve_redirect(target_path) is None:
                    issues.append(self._audit_issue(node, "error", f"Broken internal CMS link: {link}"))

        return {
            "ok": not any(issue.severity == "error" for issue in issues),
            "nodes": len(nodes),
            "published": sum(1 for node in nodes if node.is_published),
            "draft": sum(1 for node in nodes if node.status == _STATUS_DRAFT),
            "unpublished": sum(1 for node in nodes if node.status == _STATUS_UNPUBLISHED),
            "issue_count": len(issues),
            "error_count": sum(1 for issue in issues if issue.severity == "error"),
            "warning_count": sum(1 for issue in issues if issue.severity == "warning"),
            "info_count": sum(1 for issue in issues if issue.severity == "info"),
            "issues": issues,
        }

    def delivery_cache_report(self, *, limit: int = 20) -> dict[str, Any]:
        published_nodes = [node for node in self.list_tree() if node.is_published]
        published_nodes.sort(key=lambda node: (node.published_at or 0.0, node.updated_at), reverse=True)
        latest = 0.0
        for node in published_nodes:
            latest = max(latest, node.updated_at, node.published_at or 0.0)
        return {
            "strategy": "published-content conditional delivery",
            "published_nodes": len(published_nodes),
            "latest_published_update": latest or None,
            "latest_published_update_iso": _iso_datetime(latest) if latest else "",
            "surfaces": [
                "/cms/api/content",
                "/cms/api/tree",
                "/cms/api/search",
                "/cms/api/tags",
                "/cms/feed.xml",
                "/sitemap.xml",
                "/cms/{path}",
            ],
            "headers": {
                "etag": True,
                "last_modified": True,
                "cache_control": True,
                "conditional_304": True,
            },
            "items": [
                {
                    "node_id": node.node_id,
                    "route_path": node.route_path,
                    "content_type_alias": node.content_type_alias,
                    "published_at": node.published_at,
                    "updated_at": node.updated_at,
                }
                for node in published_nodes[: max(1, min(limit, 200))]
            ],
        }

    def list_nodes_by_type(
        self,
        content_type_alias: str,
        *,
        include_unpublished: bool = False,
    ) -> list[ContentNode]:
        with self._lock:
            conn = self._connect()
            try:
                if include_unpublished:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_content_nodes
                        WHERE content_type_alias = ? AND status != ?
                        ORDER BY route_path, sort_order, name
                        """,
                        (content_type_alias, _STATUS_TRASHED),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_content_nodes
                        WHERE content_type_alias = ? AND status = ?
                        ORDER BY route_path, sort_order, name
                        """,
                        (content_type_alias, _STATUS_PUBLISHED),
                    ).fetchall()
                return [_node_from_row(row) for row in rows]
            finally:
                conn.close()

    def list_filtered_nodes(
        self,
        *,
        content_type_alias: str = "",
        status: str = "",
        query: str = "",
    ) -> list[ContentNode]:
        content_type_alias = content_type_alias.strip()
        status = status.strip().lower()
        tokens = _search_tokens(query)
        nodes = self.list_tree()
        out: list[ContentNode] = []
        for node in nodes:
            if content_type_alias and node.content_type_alias != content_type_alias:
                continue
            if status and node.status != status:
                continue
            if tokens:
                text = " ".join(
                    (
                        node.name,
                        node.slug,
                        node.route_path,
                        node.content_type_alias,
                        _json_dumps(node.draft),
                        _json_dumps(node.published),
                    )
                ).casefold()
                if not all(_token_in_text(token, text) for token in tokens):
                    continue
            out.append(node)
        return out

    def find_node_by_field(
        self,
        content_type_alias: str,
        field_alias: str,
        value: str,
        *,
        include_unpublished: bool = True,
    ) -> ContentNode | None:
        needle = str(value or "").strip()
        if not needle:
            return None
        for node in self.list_nodes_by_type(content_type_alias, include_unpublished=include_unpublished):
            payloads = [node.draft]
            if not include_unpublished:
                payloads = [node.published]
            elif node.published:
                payloads.append(node.published)
            for payload in payloads:
                if str(payload.get(field_alias) or "").strip() == needle:
                    return node
        return None

    def get_published_bot_resource(self, relative_path: str) -> dict[str, Any] | None:
        target = relative_path.strip().lstrip("/")
        if not target:
            return None
        data_path = f"apps/bot/data/{target}"
        for node in self.list_nodes_by_type("bot_resource"):
            payload = node.published
            if not _truthy(payload.get("active", True)):
                continue
            source_path = str(payload.get("source_path") or "").strip().replace("\\", "/")
            if source_path in {target, data_path} or source_path.endswith("/" + data_path):
                return self._runtime_node_payload(node)
        return None

    def managed_counts(self) -> dict[str, int]:
        return {
            alias: len(self.list_nodes_by_type(alias, include_unpublished=True))
            for alias in _MANAGED_CONTENT_ALIASES
        }

    def runtime_catalog(
        self,
        corpus_specs: Iterable[Any] = (),
        bot_resource_roots: Iterable[Path | str] = (),
    ) -> dict[str, Any]:
        rag_nodes = self.list_nodes_by_type("rag_material", include_unpublished=True)
        resource_nodes = self.list_nodes_by_type("bot_resource", include_unpublished=True)

        rag_by_corpus: dict[str, list[ContentNode]] = {}
        for node in rag_nodes:
            payload = node.published if node.is_published else node.draft
            key = _normalize_corpus_key(payload.get("corpus_key")) or "default"
            rag_by_corpus.setdefault(key, []).append(node)

        corpora: list[dict[str, Any]] = []
        known_keys: set[str] = set()
        for spec in corpus_specs:
            key = _normalize_corpus_key(getattr(spec, "key", "")) or "default"
            known_keys.add(key)
            files = {
                _relative_source_path(path)
                for path in self._iter_corpus_files(getattr(spec, "corpus_dirs", ()))
            }
            nodes = rag_by_corpus.get(key, [])
            sources = {
                str((node.published if node.is_published else node.draft).get("source_path") or "")
                for node in nodes
            }
            corpora.append(
                {
                    "key": key,
                    "title": str(getattr(spec, "title", "") or key),
                    "corpus_dirs": [
                        str(path) for path in getattr(spec, "corpus_dirs", ())
                    ],
                    "index_dir": str(getattr(spec, "default_index_dir", "") or ""),
                    "files_total": len(files),
                    "nodes_total": len(nodes),
                    "published_active": sum(1 for node in nodes if self._node_active(node)),
                    "missing_sources": sorted(files - sources),
                }
            )

        for key, nodes in sorted(rag_by_corpus.items()):
            if key in known_keys:
                continue
            corpora.append(
                {
                    "key": key,
                    "title": key,
                    "corpus_dirs": [],
                    "index_dir": "",
                    "files_total": 0,
                    "nodes_total": len(nodes),
                    "published_active": sum(1 for node in nodes if self._node_active(node)),
                    "missing_sources": [],
                }
            )

        resource_files = {
            _relative_source_path(path)
            for path in self._iter_resource_files(bot_resource_roots)
        }
        resource_sources = {
            str((node.published if node.is_published else node.draft).get("source_path") or "")
            for node in resource_nodes
        }
        groups: dict[str, dict[str, Any]] = {}
        for node in resource_nodes:
            payload = node.published if node.is_published else node.draft
            group = str(payload.get("resource_group") or "bot").strip() or "bot"
            row = groups.setdefault(
                group,
                {
                    "group": group,
                    "nodes_total": 0,
                    "published_active": 0,
                    "files_total": 0,
                    "missing_sources": [],
                },
            )
            row["nodes_total"] += 1
            if self._node_active(node):
                row["published_active"] += 1

        for source in resource_files:
            group = Path(source).parent.name or "bot"
            row = groups.setdefault(
                group,
                {
                    "group": group,
                    "nodes_total": 0,
                    "published_active": 0,
                    "files_total": 0,
                    "missing_sources": [],
                },
            )
            row["files_total"] += 1
            if source not in resource_sources:
                row["missing_sources"].append(source)

        return {
            "corpora": corpora,
            "bot_resource_groups": sorted(groups.values(), key=lambda item: item["group"]),
            "missing_rag_sources_total": sum(len(item["missing_sources"]) for item in corpora),
            "missing_bot_sources_total": len(resource_files - resource_sources),
        }

    def seed_ai_experts(self, experts: Iterable[Any], *, created_by: str = "system") -> int:
        inserted = 0
        for expert in experts:
            expert_id = str(getattr(expert, "expert_id", "") or "").strip()
            if not expert_id or self.find_node_by_field("ai_expert", "expert_id", expert_id):
                continue
            payload = {
                "expert_id": expert_id,
                "avatar": str(getattr(expert, "avatar", "") or "🔮"),
                "school": str(getattr(expert, "school", "") or "western"),
                "title": str(getattr(expert, "title", "") or ""),
                "bio": str(getattr(expert, "bio", "") or ""),
                "tags": _csv(getattr(expert, "tags", "")),
                "price_per_message": str(getattr(expert, "price_per_message", 40) or 40),
                "currency": str(getattr(expert, "currency", "") or "ток."),
                "greeting": str(getattr(expert, "greeting", "") or ""),
                "sample_questions": _lines(getattr(expert, "sample_questions", "")),
                "system_prompt": str(getattr(expert, "system_prompt", "") or ""),
                "rag_school": str(getattr(expert, "rag_school", "") or ""),
                "online": bool(getattr(expert, "online", True)),
                "visible": bool(getattr(expert, "visible", True)),
            }
            try:
                node = self.create_node(
                    parent_id=_ROOT_NODE_ID,
                    content_type_alias="ai_expert",
                    name=str(getattr(expert, "name", "") or expert_id),
                    slug=str(getattr(expert, "slug", "") or expert_id),
                    payload=payload,
                    created_by=created_by,
                )
                self.publish_node(node.node_id, published_by=created_by)
            except ValueError:
                logger.warning("Cannot import AI expert into ArcHub: %s", expert_id, exc_info=True)
                continue
            inserted += 1
        return inserted

    def seed_rag_corpus(self, corpus_specs: Iterable[Any], *, created_by: str = "system") -> int:
        inserted = 0
        for spec in corpus_specs:
            corpus_key = str(getattr(spec, "key", "") or "").strip()
            if not corpus_key:
                continue
            for file_path in self._iter_corpus_files(getattr(spec, "corpus_dirs", ())):
                source_path = _relative_source_path(file_path)
                if self.find_node_by_field("rag_material", "source_path", source_path):
                    continue
                try:
                    body = file_path.read_text(encoding="utf-8")
                except OSError:
                    logger.warning("Cannot import RAG material into ArcHub: %s", file_path, exc_info=True)
                    continue
                title = _markdown_title(body, file_path.stem.replace("_", " ").replace("-", " ").title())
                try:
                    node = self.create_node(
                        parent_id=_ROOT_NODE_ID,
                        content_type_alias="rag_material",
                        name=title,
                        slug=f"rag-{corpus_key}-{file_path.stem}",
                        payload={
                            "title": title,
                            "corpus_key": corpus_key,
                            "source_path": source_path,
                            "body": body,
                            "tags": corpus_key,
                            "active": True,
                        },
                        created_by=created_by,
                    )
                    self.publish_node(node.node_id, published_by=created_by)
                except ValueError:
                    logger.warning("Cannot import RAG material into ArcHub: %s", file_path, exc_info=True)
                    continue
                inserted += 1
        return inserted

    def seed_bot_resources(self, roots: Iterable[Path | str], *, created_by: str = "system") -> int:
        inserted = 0
        for file_path in self._iter_resource_files(roots):
            source_path = _relative_source_path(file_path)
            if self.find_node_by_field("bot_resource", "source_path", source_path):
                continue
            try:
                body = file_path.read_text(encoding="utf-8")
            except OSError:
                logger.warning("Cannot import bot resource into ArcHub: %s", file_path, exc_info=True)
                continue
            title = _markdown_title(body, file_path.stem.replace("_", " ").replace("-", " ").title())
            group = file_path.parent.name if file_path.parent.name else "bot"
            try:
                node = self.create_node(
                    parent_id=_ROOT_NODE_ID,
                    content_type_alias="bot_resource",
                    name=title,
                    slug=f"bot-{group}-{file_path.stem}",
                    payload={
                        "title": title,
                        "resource_key": file_path.stem,
                        "resource_group": group,
                        "source_path": source_path,
                        "format": file_path.suffix.lstrip(".") or "text",
                        "body": body,
                        "locale": "ru",
                        "active": True,
                    },
                    created_by=created_by,
                )
                self.publish_node(node.node_id, published_by=created_by)
            except ValueError:
                logger.warning("Cannot import bot resource into ArcHub: %s", file_path, exc_info=True)
                continue
            inserted += 1
        return inserted

    def bootstrap_runtime_content(
        self,
        *,
        experts: Iterable[Any] = (),
        rag_specs: Iterable[Any] = (),
        bot_resource_roots: Iterable[Path | str] = (),
        created_by: str = "system",
    ) -> dict[str, int]:
        return {
            "ai_experts": self.seed_ai_experts(experts, created_by=created_by),
            "rag_materials": self.seed_rag_corpus(rag_specs, created_by=created_by),
            "bot_resources": self.seed_bot_resources(bot_resource_roots, created_by=created_by),
        }

    def runtime_export_status(self, export_dir: Path | str | None = None) -> dict[str, Any]:
        base = _runtime_export_dir(export_dir)
        manifest_path = base / "manifest.json"
        manifest = _json_loads_dict(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        generated_at = float(manifest.get("generated_at") or 0.0)
        latest_runtime_update = self._latest_runtime_update_at()
        return {
            "export_dir": str(base),
            "manifest_path": str(manifest_path),
            "exists": manifest_path.exists(),
            "generated_at": generated_at or None,
            "counts": manifest.get("counts") or {},
            "latest_runtime_update": latest_runtime_update or None,
            "needs_export": bool(latest_runtime_update and latest_runtime_update > generated_at),
        }

    def runtime_audit_report(self) -> dict[str, Any]:
        issues: list[ContentAuditIssue] = []
        runtime_nodes: list[ContentNode] = []
        for alias in _MANAGED_CONTENT_ALIASES:
            runtime_nodes.extend(self.list_nodes_by_type(alias, include_unpublished=True))

        seen_experts: dict[str, ContentNode] = {}
        for node in runtime_nodes:
            if node.status != _STATUS_PUBLISHED:
                issues.append(
                    self._audit_issue(
                        node,
                        "warning",
                        "Runtime-managed node is not published and will not be used.",
                    )
                )
            errors = self._validate_payload_for_publish(node.content_type_alias, node.draft)
            for error in errors:
                issues.append(self._audit_issue(node, "error", error))
            if node.content_type_alias == "ai_expert":
                expert_id = str(node.draft.get("expert_id") or "").strip()
                if expert_id and expert_id in seen_experts:
                    issues.append(self._audit_issue(node, "error", f"Duplicate expert_id: {expert_id}"))
                    issues.append(self._audit_issue(seen_experts[expert_id], "error", f"Duplicate expert_id: {expert_id}"))
                elif expert_id:
                    seen_experts[expert_id] = node

        export_status = self.runtime_export_status()
        if export_status["needs_export"]:
            issues.append(
                ContentAuditIssue(
                    node_id="runtime",
                    route_path=str(export_status["manifest_path"]),
                    content_type_alias="runtime_export",
                    severity="warning",
                    message="Runtime snapshot is older than published CMS content.",
                )
            )
        return {
            "ok": not any(issue.severity == "error" for issue in issues),
            "issues": issues,
            "issue_count": len(issues),
            "error_count": sum(1 for issue in issues if issue.severity == "error"),
            "warning_count": sum(1 for issue in issues if issue.severity == "warning"),
        }

    def runtime_snapshot(self) -> dict[str, Any]:
        ai_experts = [
            self._runtime_node_payload(node)
            for node in self.list_nodes_by_type("ai_expert")
        ]
        rag_materials = [
            self._runtime_node_payload(node)
            for node in self.list_nodes_by_type("rag_material")
            if _truthy(node.published.get("active", True))
        ]
        bot_resources = [
            self._runtime_node_payload(node)
            for node in self.list_nodes_by_type("bot_resource")
            if _truthy(node.published.get("active", True))
        ]
        counts = {
            "ai_experts": len(ai_experts),
            "rag_materials": len(rag_materials),
            "bot_resources": len(bot_resources),
        }
        return {
            "generated_at": _now(),
            "counts": counts,
            "ai_experts": ai_experts,
            "rag_materials": rag_materials,
            "bot_resources": bot_resources,
        }

    def export_runtime_content(
        self,
        export_dir: Path | str | None = None,
        *,
        exported_by: str = "system",
    ) -> dict[str, Any]:
        base = _runtime_export_dir(export_dir)
        snapshot = self.runtime_snapshot()
        base.mkdir(parents=True, exist_ok=True)

        _json_file(base / "experts.json", snapshot["ai_experts"])
        _json_file(base / "bot_resources.json", snapshot["bot_resources"])
        _json_file(base / "rag_materials.json", snapshot["rag_materials"])

        rag_root = base / "rag_corpus"
        if rag_root.exists():
            for old_file in rag_root.rglob("*.md"):
                old_file.unlink()
        exported_by_corpus: dict[str, list[dict[str, str]]] = {}
        for material in snapshot["rag_materials"]:
            corpus_key = _normalize_corpus_key(material.get("corpus_key")) or "default"
            title = str(material.get("title") or material.get("name") or material["node_id"])
            slug = _slugify(str(material.get("slug") or title), fallback=str(material["node_id"]))
            path = rag_root / corpus_key / f"{slug}.md"
            _markdown_file(
                path,
                title=title,
                body=str(material.get("body") or ""),
                metadata={
                    "node_id": material["node_id"],
                    "corpus_key": corpus_key,
                    "source_path": material.get("source_path", ""),
                    "route_path": material["route_path"],
                    "tags": material.get("tags", ""),
                },
            )
            exported_by_corpus.setdefault(corpus_key, []).append(
                {"title": title, "path": str(path), "node_id": str(material["node_id"])}
            )

        manifest = {
            "generated_at": snapshot["generated_at"],
            "export_dir": str(base),
            "counts": snapshot["counts"],
            "rag_corpora": exported_by_corpus,
            "files": {
                "experts": str(base / "experts.json"),
                "bot_resources": str(base / "bot_resources.json"),
                "rag_materials": str(base / "rag_materials.json"),
                "rag_corpus_root": str(rag_root),
            },
        }
        _json_file(base / "manifest.json", manifest)
        with self._lock:
            conn = self._connect()
            try:
                self._record_activity(
                    conn,
                    action="runtime.exported",
                    actor=exported_by,
                    summary=f"Exported runtime snapshot to {base}",
                    metadata={
                        "export_dir": str(base),
                        "counts": snapshot["counts"],
                    },
                )
                conn.commit()
            finally:
                conn.close()
        logger.info("ArcHub runtime content exported to %s", base)
        return manifest

    def rebuild_exported_rag_indexes(
        self,
        *,
        corpus_key: str | None = None,
        model: str | None = None,
        export_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        manifest = self.export_runtime_content(export_dir)
        export_base = Path(str(manifest["export_dir"]))
        rag_root = export_base / "rag_corpus"
        model_name = model or os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        from archub_cms.integrations.rag import (
            get_rag_corpus_spec,
            iter_rag_corpus_specs,
            rebuild_corpus_index,
        )

        specs = [get_rag_corpus_spec(corpus_key)] if corpus_key else list(iter_rag_corpus_specs())
        results: dict[str, str] = {}
        for spec in specs:
            if spec is None:
                continue
            cms_dir = rag_root / spec.key
            if not cms_dir.exists() or not any(cms_dir.rglob("*.md")):
                results[spec.key] = "skipped:no-cms-materials"
                continue
            results[spec.key] = rebuild_corpus_index(
                corpus_dirs=(*spec.corpus_dirs, cms_dir),
                index_dir=spec.default_index_dir,
                model=model_name,
            )
        return {"export": manifest, "model": model_name, "indexes": results}

    def search_published_rag_materials(
        self,
        corpus_key: str | None,
        query: str = "",
        *,
        limit: int = 6,
    ) -> list[ContentNode]:
        target_key = _normalize_corpus_key(corpus_key)
        tokens = _search_tokens(query)
        scored: list[tuple[int, str, ContentNode]] = []
        for node in self.list_nodes_by_type("rag_material"):
            payload = node.published
            if not _truthy(payload.get("active", True)):
                continue
            node_key = _normalize_corpus_key(payload.get("corpus_key"))
            if target_key and node_key != target_key:
                continue
            title = str(payload.get("title") or node.name)
            tags = str(payload.get("tags") or "")
            source = str(payload.get("source_path") or "")
            body = str(payload.get("body") or "")
            if not tokens:
                score = 1
            else:
                title_text = title.casefold()
                tag_text = tags.casefold()
                source_text = source.casefold()
                body_text = body.casefold()
                score = sum(
                    (4 if _token_in_text(token, title_text) else 0)
                    + (3 if _token_in_text(token, tag_text) else 0)
                    + (2 if _token_in_text(token, source_text) else 0)
                    + (1 if _token_in_text(token, body_text) else 0)
                    for token in tokens
                )
            if score > 0:
                scored.append((score, node.route_path, node))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [node for _score, _path, node in scored[: max(1, limit)]]

    def _content_package_nodes(
        self,
        *,
        node_ids: Iterable[str],
        include_descendants: bool,
    ) -> list[ContentNode]:
        nodes = self.list_tree()
        requested = {str(item).strip() for item in node_ids if str(item).strip()}
        if not requested:
            return nodes
        by_id = {node.node_id: node for node in nodes}
        selected: dict[str, ContentNode] = {}
        for node_id in requested:
            node = by_id.get(node_id)
            if node is not None:
                selected[node.node_id] = node
                if include_descendants:
                    route = node.route_path.rstrip("/")
                    for candidate in nodes:
                        if candidate.route_path.startswith(f"{route}/"):
                            selected[candidate.node_id] = candidate
        return [node for node in nodes if node.node_id in selected]

    def _node_package_payload(self, node: ContentNode) -> dict[str, Any]:
        return {
            "node_id": node.node_id,
            "parent_id": node.parent_id,
            "content_type_alias": node.content_type_alias,
            "name": node.name,
            "slug": node.slug,
            "route_path": node.route_path,
            "level": node.level,
            "status": node.status,
            "draft": node.draft,
            "published": node.published,
            "sort_order": node.sort_order,
            "created_at": node.created_at,
            "updated_at": node.updated_at,
            "published_at": node.published_at,
            "created_by": node.created_by,
            "updated_by": node.updated_by,
            "variants": [item.__dict__ for item in self.list_content_variants(node.node_id)],
            "segments": [item.__dict__ for item in self.list_content_segments(node.node_id)],
        }

    def _workflow_package_items(self, *, limit: int) -> list[dict[str, Any]]:
        report = self.workflow_report(limit=limit)
        return [
            {
                "node_id": str(item.get("node_id") or ""),
                "state": str(item.get("state") or "draft"),
                "assigned_to": str(item.get("assigned_to") or ""),
                "scheduled_publish_at": item.get("scheduled_publish_at"),
                "scheduled_unpublish_at": item.get("scheduled_unpublish_at"),
                "note": str(item.get("note") or ""),
            }
            for item in report.get("items", [])
            if isinstance(item, dict)
        ]

    @staticmethod
    def _package_items(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            value = value.get("items", [])
        if not isinstance(value, list):
            return []
        return [dict(item) for item in value if isinstance(item, dict)]

    def _plan_package_node_import(
        self,
        conn: sqlite3.Connection,
        item: dict[str, Any],
        *,
        overwrite: bool,
    ) -> dict[str, Any]:
        node_id = str(item.get("node_id") or "").strip()
        route_path = self._normalize_public_path(str(item.get("route_path") or ""))
        by_id = (
            conn.execute(
                """
                SELECT node_id, route_path, name, content_type_alias, status
                FROM archub_content_nodes
                WHERE node_id = ?
                """,
                (node_id,),
            ).fetchone()
            if node_id
            else None
        )
        by_route = conn.execute(
            """
            SELECT node_id, route_path, name, content_type_alias, status
            FROM archub_content_nodes
            WHERE route_path = ?
            """,
            (route_path,),
        ).fetchone()
        action = "create"
        reason = "missing"
        existing = by_id or by_route
        if by_id is not None and by_route is not None and str(by_id["node_id"]) != str(by_route["node_id"]):
            action = "conflict"
            reason = "node_id_and_route_match_different_existing_nodes"
            existing = by_route
        elif by_id is not None:
            action = "update" if overwrite else "skip"
            reason = "node_id_exists"
            existing = by_id
        elif by_route is not None and overwrite:
            action = "update"
            reason = "route_exists"
            existing = by_route
        elif by_route is not None:
            action = "conflict"
            reason = "route_exists"
            existing = by_route
        return {
            "action": action,
            "reason": reason,
            "node_id": node_id,
            "target_node_id": str(existing["node_id"]) if existing is not None else node_id,
            "route_path": route_path,
            "name": str(item.get("name") or ""),
            "content_type_alias": str(item.get("content_type_alias") or ""),
            "existing_route_path": str(existing["route_path"]) if existing is not None else "",
            "existing_name": str(existing["name"]) if existing is not None else "",
            "existing_status": str(existing["status"]) if existing is not None else "",
        }

    def _import_package_content_model(self, package: dict[str, Any], *, imported_by: str) -> None:
        model = package.get("content_model") if isinstance(package.get("content_model"), dict) else {}
        for item in self._package_items(model.get("data_types") if isinstance(model, dict) else []):
            self.upsert_data_type(
                alias=str(item.get("alias") or ""),
                name=str(item.get("name") or ""),
                editor=str(item.get("editor") or "text"),
                description=str(item.get("description") or ""),
                config=_json_dict_from_value(item.get("config")),
                validation=_json_dict_from_value(item.get("validation")),
                updated_by=imported_by,
            )
        templates = self._package_items(model.get("templates") if isinstance(model, dict) else [])
        for item in templates:
            self.upsert_template(
                alias=str(item.get("alias") or ""),
                name=str(item.get("name") or ""),
                view=str(item.get("view") or "archub_public.html"),
                description=str(item.get("description") or ""),
                allowed_content_type_aliases=(),
                config=_json_dict_from_value(item.get("config")),
                updated_by=imported_by,
            )
        for item in self._package_items(model.get("compositions") if isinstance(model, dict) else []):
            self.upsert_content_composition(
                alias=str(item.get("alias") or ""),
                name=str(item.get("name") or ""),
                description=str(item.get("description") or ""),
                fields=self._package_items(item.get("fields")),
                updated_by=imported_by,
            )
        for item in self._package_items(model.get("content_types") if isinstance(model, dict) else []):
            self.upsert_content_type(
                alias=str(item.get("alias") or ""),
                name=str(item.get("name") or ""),
                icon=str(item.get("icon") or "□"),
                description=str(item.get("description") or ""),
                fields=self._package_items(item.get("fields")),
                allowed_child_aliases=item.get("allowed_child_aliases") or (),
                composition_aliases=item.get("composition_aliases") or (),
                allow_at_root=bool(item.get("allow_at_root")),
                is_element=bool(item.get("is_element")),
                template=str(item.get("template") or "page"),
                updated_by=imported_by,
            )
        for item in templates:
            self.upsert_template(
                alias=str(item.get("alias") or ""),
                name=str(item.get("name") or ""),
                view=str(item.get("view") or "archub_public.html"),
                description=str(item.get("description") or ""),
                allowed_content_type_aliases=item.get("allowed_content_type_aliases") or (),
                config=_json_dict_from_value(item.get("config")),
                updated_by=imported_by,
            )
        for item in self._package_items(model.get("blueprints") if isinstance(model, dict) else []):
            self.upsert_content_blueprint(
                blueprint_id=str(item.get("blueprint_id") or ""),
                content_type_alias=str(item.get("content_type_alias") or ""),
                name=str(item.get("name") or ""),
                description=str(item.get("description") or ""),
                payload=_json_dict_from_value(item.get("payload")),
                updated_by=imported_by,
            )

    def _import_package_nodes(
        self,
        nodes: list[dict[str, Any]],
        *,
        imported_by: str,
        overwrite: bool,
    ) -> dict[str, Any]:
        id_map: dict[str, str] = {}
        imported = {"nodes": 0, "variants": 0, "segments": 0}
        skipped = {"nodes": 0}
        with self._lock:
            conn = self._connect()
            try:
                for item in sorted(nodes, key=lambda row: (_safe_int(row.get("level")), str(row.get("route_path") or ""))):
                    original_id = str(item.get("node_id") or "").strip() or secrets.token_urlsafe(10)
                    parent_id = str(item.get("parent_id") or "").strip() or None
                    if parent_id:
                        parent_id = id_map.get(parent_id, parent_id)
                    existing = conn.execute(
                        "SELECT * FROM archub_content_nodes WHERE node_id = ?",
                        (original_id,),
                    ).fetchone()
                    if existing is None:
                        existing = conn.execute(
                            "SELECT * FROM archub_content_nodes WHERE route_path = ?",
                            (str(item.get("route_path") or ""),),
                        ).fetchone()
                    final_id = str(existing["node_id"]) if existing is not None else original_id
                    id_map[original_id] = final_id
                    if existing is not None and not overwrite:
                        skipped["nodes"] += 1
                        continue
                    imported["nodes"] += 1
                    package_node_counts = self._upsert_packaged_node(
                        conn,
                        item,
                        node_id=final_id,
                        parent_id=parent_id,
                        imported_by=imported_by,
                        existing=existing is not None,
                    )
                    imported["variants"] += package_node_counts["variants"]
                    imported["segments"] += package_node_counts["segments"]
                conn.commit()
            finally:
                conn.close()
        return {"imported": imported, "skipped": skipped, "id_map": id_map}

    def _upsert_packaged_node(
        self,
        conn: sqlite3.Connection,
        item: dict[str, Any],
        *,
        node_id: str,
        parent_id: str | None,
        imported_by: str,
        existing: bool,
    ) -> dict[str, int]:
        content_type = self._hydrate_content_type(
            conn,
            self._get_content_type_row(conn, str(item.get("content_type_alias") or "")),
        )
        if parent_id:
            self._get_node_row(conn, parent_id)
        draft = self._clean_payload(content_type, _json_dict_from_value(item.get("draft")))
        published = self._clean_payload(content_type, _json_dict_from_value(item.get("published")))
        route_path = self._normalize_public_path(str(item.get("route_path") or ""))
        status = str(item.get("status") or _STATUS_DRAFT)
        if status not in {_STATUS_DRAFT, _STATUS_PUBLISHED, _STATUS_UNPUBLISHED}:
            status = _STATUS_DRAFT
        published_json = _json_dumps(published) if published else None
        published_at = _safe_float(item.get("published_at")) or None
        now = _now()
        values = (
            parent_id,
            content_type.alias,
            str(item.get("name") or route_path.rsplit("/", 1)[-1] or "Imported content"),
            str(item.get("slug") or route_path.rsplit("/", 1)[-1] or ""),
            route_path,
            _safe_int(item.get("level"), 1),
            status,
            _json_dumps(draft),
            published_json,
            _safe_int(item.get("sort_order")),
            _safe_float(item.get("created_at"), now),
            _safe_float(item.get("updated_at"), now),
            published_at,
            str(item.get("created_by") or imported_by),
            imported_by,
            node_id,
        )
        if existing:
            conn.execute(
                """
                UPDATE archub_content_nodes
                SET parent_id = ?, content_type_alias = ?, name = ?, slug = ?,
                    route_path = ?, level = ?, status = ?, draft_json = ?,
                    published_json = ?, sort_order = ?, created_at = ?,
                    updated_at = ?, published_at = ?, created_by = ?, updated_by = ?
                WHERE node_id = ?
                """,
                values,
            )
        else:
            conn.execute(
                """
                INSERT INTO archub_content_nodes (
                    parent_id, content_type_alias, name, slug, route_path,
                    level, status, draft_json, published_json, sort_order,
                    created_at, updated_at, published_at, created_by, updated_by,
                    node_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        self._add_version(
            conn,
            node_id=node_id,
            status=status,
            payload=published if status == _STATUS_PUBLISHED and published else draft,
            created_by=imported_by,
            note="Imported from ArcHub package",
        )
        variant_count = 0
        conn.execute("DELETE FROM archub_content_variants WHERE node_id = ?", (node_id,))
        for variant in self._package_items(item.get("variants")):
            culture = _normalize_culture(str(variant.get("culture") or ""))
            if not culture:
                continue
            variant_draft = self._clean_payload(content_type, _json_dict_from_value(variant.get("draft")))
            variant_published = self._clean_payload(content_type, _json_dict_from_value(variant.get("published")))
            conn.execute(
                """
                INSERT INTO archub_content_variants (
                    node_id, culture, status, draft_json, published_json,
                    created_at, updated_at, published_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    culture,
                    str(variant.get("status") or _STATUS_DRAFT),
                    _json_dumps(variant_draft),
                    _json_dumps(variant_published) if variant_published else None,
                    _safe_float(variant.get("created_at"), now),
                    _safe_float(variant.get("updated_at"), now),
                    _safe_float(variant.get("published_at")) or None,
                    imported_by,
                ),
            )
            variant_count += 1
        conn.execute("DELETE FROM archub_content_segments WHERE node_id = ?", (node_id,))
        segment_count = 0
        for segment in self._package_items(item.get("segments")):
            segment_alias = _normalize_segment(str(segment.get("segment") or ""))
            segment_draft = self._clean_segment_payload(content_type, _json_dict_from_value(segment.get("draft")))
            segment_published = self._clean_segment_payload(content_type, _json_dict_from_value(segment.get("published")))
            conn.execute(
                """
                INSERT INTO archub_content_segments (
                    node_id, segment, status, draft_json, published_json,
                    created_at, updated_at, published_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    segment_alias,
                    str(segment.get("status") or _STATUS_DRAFT),
                    _json_dumps(segment_draft),
                    _json_dumps(segment_published) if segment_published else None,
                    _safe_float(segment.get("created_at"), now),
                    _safe_float(segment.get("updated_at"), now),
                    _safe_float(segment.get("published_at")) or None,
                    imported_by,
                ),
            )
            segment_count += 1
        self._record_activity(
            conn,
            node_id=node_id,
            action="package.node_imported",
            actor=imported_by,
            summary=f"Imported package node: {values[2]}",
            metadata={"route_path": route_path, "status": status},
        )
        return {"variants": variant_count, "segments": segment_count}

    def _import_package_domains(
        self,
        package: dict[str, Any],
        *,
        id_map: dict[str, str],
        imported_by: str,
    ) -> int:
        count = 0
        for item in self._package_items(package.get("domains")):
            root_node_id = str(item.get("root_node_id") or _ROOT_NODE_ID)
            self.upsert_content_domain(
                domain_id=str(item.get("domain_id") or ""),
                hostname=str(item.get("hostname") or ""),
                root_node_id=id_map.get(root_node_id, root_node_id),
                culture=str(item.get("culture") or ""),
                is_default=bool(item.get("is_default")),
                secure=bool(item.get("secure")),
                sort_order=_safe_int(item.get("sort_order")),
                updated_by=imported_by,
            )
            count += 1
        return count

    def _import_package_dictionary(self, package: dict[str, Any], *, imported_by: str) -> int:
        count = 0
        for item in self._package_items(package.get("dictionary_items")):
            self.upsert_dictionary_item(
                item_key=str(item.get("item_key") or ""),
                group_name=str(item.get("group_name") or ""),
                values={
                    str(key): str(value)
                    for key, value in _json_dict_from_value(item.get("values")).items()
                },
                updated_by=imported_by,
            )
            count += 1
        return count

    def _import_package_media(self, package: dict[str, Any], *, imported_by: str) -> int:
        count = 0
        for item in self._package_items(package.get("media_assets")):
            self.register_media_reference(
                filename=str(item.get("filename") or item.get("original_name") or "asset"),
                original_name=str(item.get("original_name") or item.get("filename") or "asset"),
                content_type=str(item.get("content_type") or "application/octet-stream"),
                url=str(item.get("url") or ""),
                folder=str(item.get("folder") or ""),
                alt_text=str(item.get("alt_text") or ""),
                tags=[str(tag) for tag in item.get("tags", [])] if isinstance(item.get("tags"), list) else [],
                metadata=_json_dict_from_value(item.get("metadata")),
                created_by=imported_by,
            )
            count += 1
        return count

    def _import_package_redirects(self, package: dict[str, Any], *, imported_by: str) -> int:
        count = 0
        for item in self._package_items(package.get("redirects")):
            self.upsert_redirect(
                source_path=str(item.get("source_path") or ""),
                target_path=str(item.get("target_path") or ""),
                status_code=_safe_int(item.get("status_code"), 301),
                active=bool(item.get("active", True)),
                note=str(item.get("note") or ""),
                updated_by=imported_by,
            )
            count += 1
        return count

    def _import_package_access(
        self,
        package: dict[str, Any],
        *,
        id_map: dict[str, str],
        imported_by: str,
    ) -> int:
        count = 0
        for item in self._package_items(package.get("public_access")):
            node_id = str(item.get("node_id") or "")
            self.set_public_access_rule(
                id_map.get(node_id, node_id),
                policy=str(item.get("policy") or "public"),
                member_groups=item.get("member_groups") or (),
                include_descendants=bool(item.get("include_descendants", True)),
                login_path=str(item.get("login_path") or "/login"),
                denied_path=str(item.get("denied_path") or ""),
                note=str(item.get("note") or ""),
                updated_by=imported_by,
            )
            count += 1
        return count

    def _import_package_workflows(
        self,
        package: dict[str, Any],
        *,
        id_map: dict[str, str],
        imported_by: str,
    ) -> int:
        count = 0
        for item in self._package_items(package.get("workflows")):
            node_id = str(item.get("node_id") or "")
            self.upsert_workflow(
                node_id=id_map.get(node_id, node_id),
                state=str(item.get("state") or "draft"),
                assigned_to=str(item.get("assigned_to") or ""),
                scheduled_publish_at=_safe_float(item.get("scheduled_publish_at")) or None,
                scheduled_unpublish_at=_safe_float(item.get("scheduled_unpublish_at")) or None,
                note=str(item.get("note") or ""),
                updated_by=imported_by,
            )
            count += 1
        return count

    @staticmethod
    def _runtime_node_payload(node: ContentNode) -> dict[str, Any]:
        payload = dict(node.published)
        payload.update(
            {
                "node_id": node.node_id,
                "content_type_alias": node.content_type_alias,
                "name": node.name,
                "slug": node.slug,
                "route_path": node.route_path,
                "published_at": node.published_at,
                "updated_at": node.updated_at,
            }
        )
        return payload

    @staticmethod
    def _preview_token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _preview_token_payload(token: ContentPreviewToken) -> dict[str, Any]:
        return {
            "token_hash": token.token_hash,
            "node_id": token.node_id,
            "node_name": token.node_name,
            "route_path": token.route_path,
            "content_type_alias": token.content_type_alias,
            "created_by": token.created_by,
            "created_at": token.created_at,
            "created_at_iso": _iso_datetime(token.created_at),
            "expires_at": token.expires_at,
            "expires_at_iso": _iso_datetime(token.expires_at),
            "revoked_at": token.revoked_at,
            "revoked_at_iso": _iso_datetime(token.revoked_at),
            "revoked_by": token.revoked_by,
            "note": token.note,
            "active": token.is_active,
        }

    @staticmethod
    def _draft_node_payload(
        conn: sqlite3.Connection,
        node: ContentNode,
        *,
        include_children: bool = False,
        max_depth: int = 4,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "node_id": node.node_id,
            "content_type_alias": node.content_type_alias,
            "name": node.name,
            "slug": node.slug,
            "route_path": node.route_path,
            "level": node.level,
            "status": node.status,
            "draft_updated_at": node.updated_at,
            "draft_updated_at_iso": _iso_datetime(node.updated_at),
            "published_at": node.published_at,
            "published_at_iso": _iso_datetime(node.published_at),
            "has_published_payload": bool(node.published),
            "payload": dict(node.draft),
        }
        if include_children:
            children: list[dict[str, Any]] = []
            if max_depth > 0:
                rows = conn.execute(
                    """
                    SELECT * FROM archub_content_nodes
                    WHERE parent_id = ? AND status != ?
                    ORDER BY sort_order, name
                    """,
                    (node.node_id, _STATUS_TRASHED),
                ).fetchall()
                children = [
                    ArcHubCMSService._draft_node_payload(
                        conn,
                        _node_from_row(row),
                        include_children=True,
                        max_depth=max_depth - 1,
                    )
                    for row in rows
                ]
            payload["children"] = children
        return payload

    def _public_node_payload(
        self,
        node: ContentNode,
        *,
        include_children: bool = False,
        max_depth: int = 4,
        culture: str = "",
        segment: str = "",
    ) -> dict[str, Any]:
        localized, resolved_culture, culture_fallback, resolved_segment, segment_fallback = (
            self._delivery_payload(node, culture=culture, segment=segment)
        )
        payload = {
            "node_id": node.node_id,
            "content_type_alias": node.content_type_alias,
            "name": node.name,
            "slug": node.slug,
            "route_path": node.route_path,
            "level": node.level,
            "culture": resolved_culture,
            "culture_fallback": culture_fallback,
            "available_cultures": self._published_variant_cultures(node.node_id),
            "segment": resolved_segment,
            "segment_fallback": segment_fallback,
            "available_segments": self._published_segment_aliases(node.node_id),
            "published_at": node.published_at,
            "published_at_iso": _iso_datetime(node.published_at),
            "updated_at": node.updated_at,
            "updated_at_iso": _iso_datetime(node.updated_at),
            "payload": localized,
        }
        if include_children:
            children = []
            if max_depth > 0:
                children = [
                    self._public_node_payload(
                        child,
                        include_children=True,
                        max_depth=max_depth - 1,
                        culture=culture,
                        segment=segment,
                    )
                    for child in self.published_children(node.node_id)
                ]
            payload["children"] = children
        return payload

    def _public_search_payload(
        self,
        node: ContentNode,
        *,
        score: int,
        culture: str = "",
        segment: str = "",
    ) -> dict[str, Any]:
        payload, resolved_culture, culture_fallback, resolved_segment, segment_fallback = (
            self._delivery_payload(node, culture=culture, segment=segment)
        )
        return {
            "node_id": node.node_id,
            "score": score,
            "content_type_alias": node.content_type_alias,
            "name": node.name,
            "culture": resolved_culture,
            "culture_fallback": culture_fallback,
            "segment": resolved_segment,
            "segment_fallback": segment_fallback,
            "title": _content_title(node, payload),
            "summary": _content_summary(payload),
            "route_path": node.route_path,
            "published_at": node.published_at,
            "published_at_iso": _iso_datetime(node.published_at),
            "updated_at": node.updated_at,
            "updated_at_iso": _iso_datetime(node.updated_at),
            "tags": list(_content_tags(payload)),
        }

    def _localized_payload(self, node: ContentNode, culture: str = "") -> tuple[dict[str, Any], str, bool]:
        clean_culture = _normalize_culture(culture)
        if not clean_culture:
            return dict(node.published), "", False
        variant = self._published_variant(node.node_id, clean_culture)
        if variant is None:
            return dict(node.published), clean_culture, True
        payload = dict(node.published)
        payload.update(variant.published)
        return payload, clean_culture, False

    def _delivery_payload(
        self,
        node: ContentNode,
        *,
        culture: str = "",
        segment: str = "",
    ) -> tuple[dict[str, Any], str, bool, str, bool]:
        payload, resolved_culture, culture_fallback = self._localized_payload(node, culture)
        clean_segment = _normalize_segment(segment) if str(segment or "").strip() else ""
        if not clean_segment:
            return payload, resolved_culture, culture_fallback, "", False
        segment_variant = self._published_segment(node.node_id, clean_segment)
        if segment_variant is None:
            return payload, resolved_culture, culture_fallback, clean_segment, True
        payload.update(segment_variant.published)
        return payload, resolved_culture, culture_fallback, clean_segment, False

    def _published_variant(self, node_id: str, culture: str) -> ContentVariant | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT * FROM archub_content_variants
                    WHERE node_id = ? AND culture = ? AND status = ?
                    """,
                    (node_id, culture, _STATUS_PUBLISHED),
                ).fetchone()
                return _variant_from_row(row) if row is not None else None
            finally:
                conn.close()

    def _published_variant_cultures(self, node_id: str) -> list[str]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT culture FROM archub_content_variants
                    WHERE node_id = ? AND status = ?
                    ORDER BY culture
                    """,
                    (node_id, _STATUS_PUBLISHED),
                ).fetchall()
                return [str(row["culture"]) for row in rows]
            finally:
                conn.close()

    def _published_segment(self, node_id: str, segment: str) -> ContentSegment | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT * FROM archub_content_segments
                    WHERE node_id = ? AND segment = ? AND status = ?
                    """,
                    (node_id, segment, _STATUS_PUBLISHED),
                ).fetchone()
                return _segment_from_row(row) if row is not None else None
            finally:
                conn.close()

    def _published_segment_aliases(self, node_id: str) -> list[str]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT segment FROM archub_content_segments
                    WHERE node_id = ? AND status = ?
                    ORDER BY segment
                    """,
                    (node_id, _STATUS_PUBLISHED),
                ).fetchall()
                return [str(row["segment"]) for row in rows]
            finally:
                conn.close()

    @staticmethod
    def _node_active(node: ContentNode) -> bool:
        if not node.is_published:
            return False
        return _truthy(node.published.get("active", True))

    @staticmethod
    def _audit_issue(node: ContentNode, severity: str, message: str) -> ContentAuditIssue:
        return ContentAuditIssue(
            node_id=node.node_id,
            route_path=node.route_path,
            content_type_alias=node.content_type_alias,
            severity=severity,
            message=message,
        )

    def register_media_reference(
        self,
        *,
        filename: str,
        original_name: str,
        content_type: str,
        url: str,
        folder: str,
        alt_text: str,
        tags: list[str],
        metadata: dict[str, Any],
        created_by: str,
    ) -> MediaAsset:
        now = _now()
        asset_id = secrets.token_urlsafe(10)
        clean_tags = [tag.strip() for tag in tags if tag.strip()]
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO archub_media_assets (
                        asset_id, filename, original_name, content_type, url,
                        folder, alt_text, tags_json, metadata_json, created_at,
                        created_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        asset_id,
                        filename,
                        original_name,
                        content_type,
                        url,
                        folder,
                        alt_text,
                        _json_dumps(clean_tags),
                        _json_dumps(metadata),
                        now,
                        created_by,
                    ),
                )
                self._record_activity(
                    conn,
                    action="media.registered",
                    actor=created_by,
                    summary=f"Registered media: {original_name}",
                    metadata={
                        "asset_id": asset_id,
                        "filename": filename,
                        "original_name": original_name,
                        "content_type": content_type,
                        "url": url,
                        "folder": folder,
                        "tags": clean_tags,
                    },
                )
                conn.commit()
                return MediaAsset(
                    asset_id=asset_id,
                    filename=filename,
                    original_name=original_name,
                    content_type=content_type,
                    url=url,
                    folder=folder,
                    alt_text=alt_text,
                    tags=tuple(clean_tags),
                    metadata=metadata,
                    created_at=now,
                    created_by=created_by,
                )
            finally:
                conn.close()

    def list_media_assets(self, *, folder: str = "", limit: int = 100) -> list[MediaAsset]:
        limit = max(1, min(limit, 500))
        with self._lock:
            conn = self._connect()
            try:
                if folder.strip():
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_media_assets
                        WHERE folder = ?
                        ORDER BY created_at DESC, original_name
                        LIMIT ?
                        """,
                        (folder.strip(), limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_media_assets
                        ORDER BY created_at DESC, original_name
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                return [
                    MediaAsset(
                        asset_id=str(row["asset_id"]),
                        filename=str(row["filename"]),
                        original_name=str(row["original_name"]),
                        content_type=str(row["content_type"]),
                        url=str(row["url"]),
                        folder=str(row["folder"] or ""),
                        alt_text=str(row["alt_text"] or ""),
                        tags=tuple(str(item) for item in _json_loads_list(str(row["tags_json"] or "[]"))),
                        metadata=_json_loads_dict(str(row["metadata_json"] or "{}")),
                        created_at=float(row["created_at"] or 0.0),
                        created_by=str(row["created_by"] or ""),
                    )
                    for row in rows
                ]
            finally:
                conn.close()

    def upsert_dictionary_item(
        self,
        *,
        item_key: str,
        group_name: str,
        values: dict[str, str],
        updated_by: str,
    ) -> dict[str, Any]:
        key = item_key.strip()
        if not key:
            raise ValueError("Dictionary item key is required")
        clean_values = {
            str(locale).strip(): str(value)
            for locale, value in values.items()
            if str(locale).strip()
        }
        now = _now()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO archub_dictionary_items (
                        item_key, group_name, values_json, updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(item_key) DO UPDATE SET
                        group_name = excluded.group_name,
                        values_json = excluded.values_json,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (key, group_name.strip(), _json_dumps(clean_values), now, updated_by),
                )
                self._record_activity(
                    conn,
                    action="dictionary.upserted",
                    actor=updated_by,
                    summary=f"Dictionary item saved: {key}",
                    metadata={
                        "item_key": key,
                        "group_name": group_name.strip(),
                        "locales": sorted(clean_values),
                    },
                )
                conn.commit()
                return {
                    "item_key": key,
                    "group_name": group_name.strip(),
                    "values": clean_values,
                    "updated_at": now,
                    "updated_by": updated_by,
                }
            finally:
                conn.close()

    def list_dictionary_items(self, *, group_name: str = "", limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self._lock:
            conn = self._connect()
            try:
                if group_name.strip():
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_dictionary_items
                        WHERE group_name = ?
                        ORDER BY item_key
                        LIMIT ?
                        """,
                        (group_name.strip(), limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM archub_dictionary_items
                        ORDER BY group_name, item_key
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                return [
                    {
                        "item_key": str(row["item_key"]),
                        "group_name": str(row["group_name"] or ""),
                        "values": _json_loads_dict(str(row["values_json"] or "{}")),
                        "updated_at": float(row["updated_at"] or 0.0),
                        "updated_by": str(row["updated_by"] or ""),
                    }
                    for row in rows
                ]
            finally:
                conn.close()

    @staticmethod
    def _iter_corpus_files(roots: Iterable[Path | str]) -> list[Path]:
        files: list[Path] = []
        for root in roots:
            path = Path(root)
            if path.is_file() and path.suffix.lower() == ".md":
                files.append(path)
            elif path.is_dir():
                files.extend(item for item in path.rglob("*.md") if item.is_file())
        return sorted(files, key=_relative_source_path)

    @staticmethod
    def _iter_resource_files(roots: Iterable[Path | str]) -> list[Path]:
        files: list[Path] = []
        for root in roots:
            path = Path(root)
            if path.is_file() and path.suffix.lower() in _RESOURCE_SUFFIXES:
                files.append(path)
            elif path.is_dir():
                files.extend(
                    item
                    for item in path.rglob("*")
                    if item.is_file() and item.suffix.lower() in _RESOURCE_SUFFIXES
                )
        return sorted(files, key=_relative_source_path)

    def _latest_runtime_update_at(self) -> float:
        latest = 0.0
        for alias in _MANAGED_CONTENT_ALIASES:
            for node in self.list_nodes_by_type(alias):
                latest = max(latest, node.updated_at, node.published_at or 0.0)
        return latest

    def _validate_payload_for_publish(
        self,
        content_type_alias: str,
        payload: dict[str, Any],
    ) -> list[str]:
        errors: list[str] = []
        if content_type_alias == "ai_expert":
            expert_id = str(payload.get("expert_id") or "").strip()
            school = str(payload.get("school") or "").strip()
            rag_school = str(payload.get("rag_school") or school).strip()
            if not re.fullmatch(r"exp_[A-Za-z0-9_-]{3,64}", expert_id):
                errors.append("AI expert must have stable expert_id like exp_indubala")
            if school not in _VALID_SCHOOLS:
                errors.append(f"Unknown expert school: {school or '<empty>'}")
            if _safe_int(payload.get("price_per_message"), -1) < 0:
                errors.append("Token price must be a non-negative integer")
            if len(str(payload.get("system_prompt") or "").strip()) < 40:
                errors.append("System prompt is too short for runtime expert persona")
            if rag_school and not self._known_rag_corpus(rag_school):
                errors.append(f"Unknown RAG corpus: {rag_school}")
        elif content_type_alias == "rag_material":
            corpus_key = str(payload.get("corpus_key") or "").strip()
            body = str(payload.get("body") or "").strip()
            if not corpus_key:
                errors.append("RAG material must have corpus_key")
            elif not self._known_rag_corpus(corpus_key):
                errors.append(f"Unknown RAG corpus: {corpus_key}")
            if _truthy(payload.get("active", True)) and len(body) < 40:
                errors.append("Active RAG material body is too short")
        elif content_type_alias == "bot_resource":
            resource_key = str(payload.get("resource_key") or "").strip()
            body = str(payload.get("body") or "").strip()
            fmt = str(payload.get("format") or "").strip().lower()
            if not resource_key:
                errors.append("Bot resource must have resource_key")
            if _truthy(payload.get("active", True)) and not body:
                errors.append("Active bot resource body is empty")
            if body and fmt in {"yaml", "yml"}:
                try:
                    import yaml

                    yaml.safe_load(body)
                except Exception:
                    errors.append("Bot resource YAML body is invalid")
            elif body and fmt == "json":
                try:
                    json.loads(body)
                except json.JSONDecodeError:
                    errors.append("Bot resource JSON body is invalid")
        return errors

    @staticmethod
    def _known_rag_corpus(corpus_key: str) -> bool:
        try:
            from archub_cms.integrations.rag import get_rag_corpus_spec

            return get_rag_corpus_spec(corpus_key) is not None
        except Exception:
            logger.debug("RAG corpus validation failed", exc_info=True)
            return False

    def _get_node_row(self, conn: sqlite3.Connection, node_id: str | None) -> sqlite3.Row:
        if not node_id:
            raise ValueError("Node is required")
        row = conn.execute(
            "SELECT * FROM archub_content_nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Content node not found")
        return row

    @staticmethod
    def _preview_token_row(
        conn: sqlite3.Connection,
        token_hash: str,
        *,
        required: bool = True,
    ) -> sqlite3.Row | None:
        row = conn.execute(
            """
            SELECT t.*, n.name AS node_name, n.route_path, n.content_type_alias
            FROM archub_preview_tokens t
            LEFT JOIN archub_content_nodes n ON n.node_id = t.node_id
            WHERE t.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if row is None and required:
            raise ValueError("Preview token not found")
        return row

    @staticmethod
    def _domain_row(
        conn: sqlite3.Connection,
        value: str,
        *,
        by: str,
        required: bool = True,
    ) -> sqlite3.Row | None:
        if by not in {"domain_id", "hostname"}:
            raise ValueError("Invalid domain lookup")
        row = conn.execute(
            f"""
            SELECT d.*, n.name AS root_name, n.route_path AS root_route_path
            FROM archub_content_domains d
            LEFT JOIN archub_content_nodes n ON n.node_id = d.root_node_id
            WHERE d.{by} = ?
            """,
            (value,),
        ).fetchone()
        if row is None and required:
            raise ValueError("Content domain not found")
        return row

    def _get_content_type_row(self, conn: sqlite3.Connection, alias: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM archub_content_types WHERE alias = ?",
            (alias,),
        ).fetchone()
        if row is None:
            raise ValueError("Content type not found")
        return row

    @staticmethod
    def _active_lock_row(
        conn: sqlite3.Connection,
        *,
        node_id: str,
        now: float,
    ) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT l.*, n.name AS node_name, n.route_path, n.content_type_alias
            FROM archub_content_locks l
            LEFT JOIN archub_content_nodes n ON n.node_id = l.node_id
            WHERE l.node_id = ? AND l.expires_at > ?
            """,
            (node_id, now),
        ).fetchone()

    @staticmethod
    def _assert_content_lock(
        conn: sqlite3.Connection,
        *,
        node_id: str,
        actor: str,
    ) -> None:
        clean_actor = actor.strip()
        if not clean_actor:
            return
        lock = ArcHubCMSService._active_lock_row(conn, node_id=node_id, now=_now())
        if lock is None or str(lock["owner"]) == clean_actor:
            return
        expires_at = _iso_datetime(float(lock["expires_at"] or 0.0))
        raise ValueError(f"Content is locked by {lock['owner']} until {expires_at}")

    @staticmethod
    def _normalize_permission_action(action: str) -> str:
        clean_action = action.strip().lower().replace("-", "_")
        if clean_action not in _CONTENT_PERMISSION_ACTIONS:
            raise ValueError(f"Unknown ArcHub permission action: {action}")
        return clean_action

    @classmethod
    def _normalize_permission_actions(cls, actions: Iterable[str]) -> tuple[str, ...]:
        requested = {cls._normalize_permission_action(str(action)) for action in actions if str(action).strip()}
        return tuple(action for action in _CONTENT_PERMISSION_ACTIONS if action in requested)

    @staticmethod
    def _normalize_permission_subject(subject: str) -> str:
        clean_subject = subject.strip().lower()
        if not clean_subject:
            raise ValueError("Permission subject is required")
        if clean_subject == "*":
            return clean_subject
        if clean_subject.startswith(("user:", "role:")):
            prefix, value = clean_subject.split(":", 1)
            value = value.strip()
            if not value:
                raise ValueError("Permission subject is required")
            return f"{prefix}:{value}"
        return f"user:{clean_subject}"

    @classmethod
    def _permission_subject_candidates(cls, username: str) -> tuple[str, ...]:
        clean_username = username.strip().lower()
        if not clean_username:
            return ()
        return ("*", f"user:{clean_username}")

    @staticmethod
    def _normalize_hostname(hostname: str) -> str:
        clean = str(hostname or "").strip().lower()
        clean = re.sub(r"^https?://", "", clean).split("/", 1)[0].strip().rstrip(".")
        if clean.startswith("["):
            raise ValueError("IPv6 hostnames are not supported for ArcHub domains yet")
        if ":" in clean:
            clean = clean.split(":", 1)[0]
        if not clean or not _HOSTNAME_RE.fullmatch(clean):
            raise ValueError("Domain hostname is invalid")
        return clean

    @classmethod
    def _domain_hostname_candidates(cls, hostname: str) -> tuple[str, ...]:
        try:
            clean = cls._normalize_hostname(hostname)
        except ValueError:
            clean = ""
        candidates: list[str] = []
        if clean:
            candidates.append(clean)
            parts = clean.split(".")
            if len(parts) > 2:
                candidates.append("*." + ".".join(parts[1:]))
        candidates.append("*")
        seen: set[str] = set()
        return tuple(item for item in candidates if not (item in seen or seen.add(item)))

    @staticmethod
    def _permission_rule_row(
        conn: sqlite3.Connection,
        rule_id: str,
        *,
        required: bool = True,
    ) -> sqlite3.Row | None:
        row = conn.execute(
            """
            SELECT p.*, n.name AS node_name,
                   n.route_path AS route_path,
                   n.content_type_alias AS content_type_alias
            FROM archub_content_permissions p
            LEFT JOIN archub_content_nodes n ON n.node_id = p.scope_node_id
            WHERE p.rule_id = ?
            """,
            (rule_id,),
        ).fetchone()
        if row is None and required:
            raise ValueError("Permission rule not found")
        return row

    @staticmethod
    def _permission_scope_matches(
        conn: sqlite3.Connection,
        rule: sqlite3.Row,
        node_id: str,
    ) -> bool:
        scope_node_id = str(rule["scope_node_id"] or "").strip()
        if not scope_node_id:
            return True
        if scope_node_id == node_id:
            return True
        if not bool(rule["include_descendants"]):
            return False
        target = conn.execute(
            "SELECT route_path FROM archub_content_nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        scope = conn.execute(
            "SELECT route_path FROM archub_content_nodes WHERE node_id = ?",
            (scope_node_id,),
        ).fetchone()
        if target is None or scope is None:
            return False
        scope_route = str(scope["route_path"] or "").rstrip("/")
        target_route = str(target["route_path"] or "")
        return bool(scope_route) and target_route.startswith(f"{scope_route}/")

    @staticmethod
    def _access_rule_row_for_node(
        conn: sqlite3.Connection,
        node_id: str,
        *,
        required: bool = True,
    ) -> sqlite3.Row | None:
        row = conn.execute(
            """
            SELECT a.*, n.name AS node_name,
                   n.route_path AS route_path,
                   n.content_type_alias AS content_type_alias
            FROM archub_content_access a
            LEFT JOIN archub_content_nodes n ON n.node_id = a.node_id
            WHERE a.node_id = ?
            """,
            (node_id,),
        ).fetchone()
        if row is None and required:
            raise ValueError("Public access rule not found")
        return row

    @staticmethod
    def _effective_access_rule_row(
        conn: sqlite3.Connection,
        node_id: str,
    ) -> sqlite3.Row | None:
        target = conn.execute(
            "SELECT route_path FROM archub_content_nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if target is None:
            raise ValueError("Content node not found")
        target_route = str(target["route_path"] or "")
        rows = conn.execute(
            """
            SELECT a.*, n.name AS node_name,
                   n.route_path AS route_path,
                   n.content_type_alias AS content_type_alias,
                   n.level AS node_level
            FROM archub_content_access a
            JOIN archub_content_nodes n ON n.node_id = a.node_id
            ORDER BY n.level DESC, a.updated_at DESC
            """
        ).fetchall()
        for row in rows:
            scope_node_id = str(row["node_id"] or "")
            scope_route = str(row["route_path"] or "").rstrip("/")
            if scope_node_id == node_id:
                return row
            if bool(row["include_descendants"]) and scope_route and target_route.startswith(f"{scope_route}/"):
                return row
        return None

    def _hydrate_content_type(self, conn: sqlite3.Connection, row: sqlite3.Row) -> ContentType:
        content_type = _type_from_row(row)
        if not content_type.composition_aliases:
            return ContentType(
                alias=content_type.alias,
                name=content_type.name,
                icon=content_type.icon,
                description=content_type.description,
                fields=self._resolve_content_field_data_types(conn, content_type.fields),
                allowed_child_aliases=content_type.allowed_child_aliases,
                composition_aliases=content_type.composition_aliases,
                allow_at_root=content_type.allow_at_root,
                is_element=content_type.is_element,
                template=content_type.template,
                created_at=content_type.created_at,
                updated_at=content_type.updated_at,
            )
        composition_fields: list[ContentField] = []
        for alias in content_type.composition_aliases:
            composition = conn.execute(
                "SELECT * FROM archub_content_compositions WHERE alias = ?",
                (alias,),
            ).fetchone()
            if composition is not None:
                composition_fields.extend(_composition_from_row(composition).fields)
        return ContentType(
            alias=content_type.alias,
            name=content_type.name,
            icon=content_type.icon,
            description=content_type.description,
            fields=self._resolve_content_field_data_types(
                conn,
                self._merge_fields((*composition_fields, *content_type.fields)),
            ),
            allowed_child_aliases=content_type.allowed_child_aliases,
            composition_aliases=content_type.composition_aliases,
            allow_at_root=content_type.allow_at_root,
            is_element=content_type.is_element,
            template=content_type.template,
            created_at=content_type.created_at,
            updated_at=content_type.updated_at,
        )

    @staticmethod
    def _merge_fields(fields: Iterable[ContentField]) -> tuple[ContentField, ...]:
        by_alias: dict[str, ContentField] = {}
        order: list[str] = []
        for field in fields:
            if field.alias not in by_alias:
                order.append(field.alias)
            by_alias[field.alias] = field
        return tuple(by_alias[alias] for alias in order)

    @staticmethod
    def _validate_schema_alias(value: str, *, label: str) -> str:
        alias = str(value or "").strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", alias):
            raise ValueError(f"{label} must match [a-z][a-z0-9_]{{1,63}}")
        return alias

    @staticmethod
    def _normalize_content_fields(fields: Iterable[dict[str, Any] | ContentField]) -> tuple[ContentField, ...]:
        normalized: list[ContentField] = []
        for item in fields:
            field = item if isinstance(item, ContentField) else _field_from_dict(item)
            alias = ArcHubCMSService._validate_schema_alias(field.alias, label="Field alias")
            name = field.name.strip()
            if not name:
                raise ValueError(f"Field name is required for {alias}")
            normalized.append(
                ContentField(
                    alias=alias,
                    name=name,
                    editor=field.editor.strip(),
                    required=field.required,
                    help_text=field.help_text.strip(),
                    default=field.default,
                    data_type_alias=field.data_type_alias.strip(),
                    config=dict(field.config),
                    validation=dict(field.validation),
                )
            )
        aliases = [field.alias for field in normalized]
        if len(set(aliases)) != len(aliases):
            raise ValueError("Field aliases must be unique")
        return tuple(normalized)

    def _resolve_content_field_data_types(
        self,
        conn: sqlite3.Connection,
        fields: Iterable[ContentField],
    ) -> tuple[ContentField, ...]:
        resolved: list[ContentField] = []
        for field in fields:
            data_type_alias = field.data_type_alias.strip()
            if not data_type_alias:
                resolved.append(
                    ContentField(
                        alias=field.alias,
                        name=field.name,
                        editor=field.editor.strip() or "text",
                        required=field.required,
                        help_text=field.help_text,
                        default=field.default,
                        config=dict(field.config),
                        validation=dict(field.validation),
                    )
                )
                continue
            data_type = conn.execute(
                "SELECT * FROM archub_data_types WHERE alias = ?",
                (data_type_alias,),
            ).fetchone()
            if data_type is None:
                raise ValueError(f"Unknown data type: {data_type_alias}")
            typed = _data_type_from_row(data_type)
            config = dict(typed.config)
            config.update(field.config)
            validation = dict(typed.validation)
            validation.update(field.validation)
            resolved.append(
                ContentField(
                    alias=field.alias,
                    name=field.name,
                    editor=field.editor.strip() or typed.editor,
                    required=field.required,
                    help_text=field.help_text.strip() or typed.description,
                    default=field.default,
                    data_type_alias=typed.alias,
                    config=config,
                    validation=validation,
                )
            )
        return tuple(resolved)

    @staticmethod
    def _field_payload(field: ContentField) -> dict[str, Any]:
        return {
            "alias": field.alias,
            "name": field.name,
            "editor": field.editor,
            "required": field.required,
            "help_text": field.help_text,
            "default": field.default,
            "data_type_alias": field.data_type_alias,
            "config": field.config,
            "validation": field.validation,
        }

    @staticmethod
    def _data_type_payload(data_type: ContentDataType) -> dict[str, Any]:
        return {
            "alias": data_type.alias,
            "name": data_type.name,
            "editor": data_type.editor,
            "description": data_type.description,
            "config": data_type.config,
            "validation": data_type.validation,
            "created_at": data_type.created_at,
            "updated_at": data_type.updated_at,
            "updated_by": data_type.updated_by,
        }

    @staticmethod
    def _domain_payload(domain: ContentDomain) -> dict[str, Any]:
        return {
            "domain_id": domain.domain_id,
            "hostname": domain.hostname,
            "root_node_id": domain.root_node_id,
            "root_name": domain.root_name,
            "root_route_path": domain.root_route_path,
            "culture": domain.culture,
            "is_default": domain.is_default,
            "secure": domain.secure,
            "sort_order": domain.sort_order,
            "created_at": domain.created_at,
            "created_at_iso": _iso_datetime(domain.created_at),
            "updated_at": domain.updated_at,
            "updated_at_iso": _iso_datetime(domain.updated_at),
            "updated_by": domain.updated_by,
        }

    @staticmethod
    def _media_payload(asset: MediaAsset) -> dict[str, Any]:
        return {
            "asset_id": asset.asset_id,
            "filename": asset.filename,
            "original_name": asset.original_name,
            "content_type": asset.content_type,
            "url": asset.url,
            "folder": asset.folder,
            "alt_text": asset.alt_text,
            "tags": list(asset.tags),
            "metadata": asset.metadata,
            "created_at": asset.created_at,
            "created_at_iso": _iso_datetime(asset.created_at),
            "created_by": asset.created_by,
        }

    @staticmethod
    def _template_payload(template: ContentTemplate) -> dict[str, Any]:
        return {
            "alias": template.alias,
            "name": template.name,
            "view": template.view,
            "description": template.description,
            "allowed_content_type_aliases": list(template.allowed_content_type_aliases),
            "config": template.config,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
            "updated_by": template.updated_by,
        }

    @classmethod
    def _composition_payload(cls, composition: ContentComposition) -> dict[str, Any]:
        return {
            "alias": composition.alias,
            "name": composition.name,
            "description": composition.description,
            "fields": [cls._field_payload(field) for field in composition.fields],
            "created_at": composition.created_at,
            "updated_at": composition.updated_at,
            "updated_by": composition.updated_by,
        }

    @staticmethod
    def _blueprint_payload(blueprint: ContentBlueprint) -> dict[str, Any]:
        return {
            "blueprint_id": blueprint.blueprint_id,
            "content_type_alias": blueprint.content_type_alias,
            "name": blueprint.name,
            "description": blueprint.description,
            "payload": blueprint.payload,
            "created_at": blueprint.created_at,
            "updated_at": blueprint.updated_at,
            "updated_by": blueprint.updated_by,
        }

    @classmethod
    def _content_type_payload(cls, content_type: ContentType) -> dict[str, Any]:
        return {
            "alias": content_type.alias,
            "name": content_type.name,
            "icon": content_type.icon,
            "description": content_type.description,
            "fields": [cls._field_payload(field) for field in content_type.fields],
            "allowed_child_aliases": list(content_type.allowed_child_aliases),
            "composition_aliases": list(content_type.composition_aliases),
            "allow_at_root": content_type.allow_at_root,
            "is_element": content_type.is_element,
            "template": content_type.template,
            "created_at": content_type.created_at,
            "updated_at": content_type.updated_at,
        }

    @staticmethod
    def _trash_payload(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "node_id": str(row["node_id"]),
            "name": str(row["name"]),
            "content_type_alias": str(row["content_type_alias"]),
            "route_path": str(row["trashed_original_route_path"] or row["route_path"]),
            "trash_route_path": str(row["route_path"]),
            "slug": str(row["trashed_original_slug"] or row["slug"] or ""),
            "original_parent_id": (
                str(row["trashed_original_parent_id"]) if row["trashed_original_parent_id"] else None
            ),
            "original_status": str(row["trashed_original_status"] or ""),
            "trashed_at": float(row["trashed_at"] or 0.0),
            "trashed_by": str(row["trashed_by"] or ""),
            "updated_at": float(row["updated_at"] or 0.0),
        }

    def _clean_payload(self, content_type: ContentType, payload: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        missing: list[str] = []
        validation_errors: list[str] = []
        for field in content_type.fields:
            value = payload.get(field.alias, field.default)
            if field.editor == "checkbox":
                clean[field.alias] = _truthy(value)
                continue
            if field.editor == "builder":
                from archub_cms.services.content_builder import (
                    get_archub_content_builder_service,
                )

                builder = get_archub_content_builder_service()
                blocks = builder.parse_blocks(value, strict=True)
                if field.required and not blocks:
                    missing.append(field.name)
                clean[field.alias] = builder.serialize_blocks(blocks)
                continue
            text = str(value or "").strip()
            if field.required and not text:
                missing.append(field.name)
            if text:
                validation_errors.extend(self._field_validation_errors(field, text))
            clean[field.alias] = text
        errors: list[str] = []
        if missing:
            errors.append("Required fields: " + ", ".join(missing))
        errors.extend(validation_errors)
        if errors:
            raise ValueError("; ".join(errors))
        return clean

    def _clean_segment_payload(self, content_type: ContentType, payload: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        validation_errors: list[str] = []
        fields = {field.alias: field for field in content_type.fields}
        for alias, value in payload.items():
            field = fields.get(str(alias))
            if field is None:
                continue
            if field.editor == "checkbox":
                clean[field.alias] = _truthy(value)
                continue
            if field.editor == "builder":
                from archub_cms.services.content_builder import (
                    get_archub_content_builder_service,
                )

                builder = get_archub_content_builder_service()
                clean[field.alias] = builder.serialize_blocks(builder.parse_blocks(value, strict=True))
                continue
            text = str(value or "").strip()
            if text:
                validation_errors.extend(self._field_validation_errors(field, text))
            clean[field.alias] = text
        if validation_errors:
            raise ValueError("; ".join(validation_errors))
        return clean

    @staticmethod
    def _field_validation_errors(field: ContentField, text: str) -> list[str]:
        validation = field.validation
        errors: list[str] = []
        min_length = _safe_int(validation.get("min_length"), 0)
        max_length = _safe_int(validation.get("max_length"), 0)
        pattern = str(validation.get("pattern") or "").strip()
        if min_length and len(text) < min_length:
            errors.append(f"{field.name} must be at least {min_length} characters")
        if max_length and len(text) > max_length:
            errors.append(f"{field.name} must be at most {max_length} characters")
        if pattern:
            try:
                matched = re.fullmatch(pattern, text) is not None
            except re.error as exc:
                raise ValueError(f"Invalid validation pattern for {field.name}: {exc}") from exc
            if not matched:
                errors.append(f"{field.name} must match {pattern}")
        return errors

    def _clean_blueprint_payload(self, content_type: ContentType, payload: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        for field in content_type.fields:
            value = payload.get(field.alias, field.default)
            if field.editor == "checkbox":
                clean[field.alias] = _truthy(value)
                continue
            if field.editor == "builder":
                from archub_cms.services.content_builder import (
                    get_archub_content_builder_service,
                )

                builder = get_archub_content_builder_service()
                clean[field.alias] = builder.serialize_blocks(builder.parse_blocks(value, strict=True))
                continue
            clean[field.alias] = str(value or "").strip()
        return clean

    def _next_sort_order(self, conn: sqlite3.Connection, parent_id: str | None) -> int:
        if parent_id is None:
            row = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_sort FROM archub_content_nodes WHERE parent_id IS NULL"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_sort FROM archub_content_nodes WHERE parent_id = ?",
                (parent_id,),
            ).fetchone()
        return int(row["next_sort"] if row is not None else 0)

    def _unique_slug(
        self,
        conn: sqlite3.Connection,
        parent_id: str | None,
        desired: str,
        *,
        exclude_id: str | None = None,
    ) -> str:
        base = _slugify(desired)
        slug = base
        suffix = 2
        while self._slug_exists(conn, parent_id, slug, exclude_id=exclude_id):
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    def _slug_exists(
        self,
        conn: sqlite3.Connection,
        parent_id: str | None,
        slug: str,
        *,
        exclude_id: str | None = None,
    ) -> bool:
        if parent_id is None:
            row = conn.execute(
                """
                SELECT node_id FROM archub_content_nodes
                WHERE parent_id IS NULL AND slug = ? AND (? IS NULL OR node_id != ?)
                LIMIT 1
                """,
                (slug, exclude_id, exclude_id),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT node_id FROM archub_content_nodes
                WHERE parent_id = ? AND slug = ? AND (? IS NULL OR node_id != ?)
                LIMIT 1
                """,
                (parent_id, slug, exclude_id, exclude_id),
            ).fetchone()
        return row is not None

    def _add_version(
        self,
        conn: sqlite3.Connection,
        *,
        node_id: str,
        status: str,
        payload: dict[str, Any],
        created_by: str,
        note: str,
    ) -> None:
        row = conn.execute(
            "SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version FROM archub_content_versions WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        next_version = int(row["next_version"] if row is not None else 1)
        conn.execute(
            """
            INSERT INTO archub_content_versions (
                node_id, version_no, status, payload_json, created_at,
                created_by, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (node_id, next_version, status, _json_dumps(payload), _now(), created_by, note),
        )

    @staticmethod
    def _normalize_webhook_events(events: Iterable[str]) -> tuple[str, ...]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in events:
            for raw in re.split(r"[,;\n]+", str(item or "")):
                event = raw.strip().lower()
                if not event:
                    continue
                if event == "*":
                    return ("*",)
                if not re.fullmatch(r"[a-z0-9_.-]+\*?", event):
                    raise ValueError(f"Invalid webhook event: {raw}")
                if event not in seen:
                    seen.add(event)
                    cleaned.append(event)
        return tuple(cleaned or ("*",))

    @staticmethod
    def _webhook_event_matches(subscription: str, event_type: str) -> bool:
        if subscription == "*":
            return True
        if subscription.endswith("*"):
            return event_type.startswith(subscription[:-1])
        return subscription == event_type

    @staticmethod
    def _webhook_headers(
        *,
        delivery_id: int,
        event_type: str,
        payload: dict[str, Any],
        secret: str,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ArcHub-CMS-Webhook/1.0",
            "X-ArcHub-Delivery": str(delivery_id),
            "X-ArcHub-Event": event_type,
        }
        if secret:
            body = _json_dumps(payload).encode("utf-8")
            signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            headers["X-ArcHub-Signature"] = f"sha256={signature}"
        return headers

    @staticmethod
    def _send_webhook(
        target_url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> int:
        import requests

        response = requests.post(target_url, json=payload, headers=headers, timeout=timeout)
        return int(response.status_code)

    @staticmethod
    def _enqueue_webhook_deliveries(
        conn: sqlite3.Connection,
        *,
        event_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
    ) -> None:
        now = _now()
        rows = conn.execute(
            """
            SELECT webhook_id, events_json
            FROM archub_webhooks
            WHERE active = 1
            """
        ).fetchall()
        for row in rows:
            events = tuple(str(item) for item in _json_loads_list(str(row["events_json"] or "[]")))
            if not any(ArcHubCMSService._webhook_event_matches(item, event_type) for item in events):
                continue
            conn.execute(
                """
                INSERT INTO archub_webhook_deliveries (
                    webhook_id, event_type, aggregate_id, payload_json, status,
                    attempts, next_attempt_at, last_error, created_at, updated_at,
                    delivered_at
                )
                VALUES (?, ?, ?, ?, 'pending', 0, ?, '', ?, ?, NULL)
                """,
                (
                    str(row["webhook_id"]),
                    event_type,
                    aggregate_id,
                    _json_dumps(payload),
                    now,
                    now,
                    now,
                ),
            )

    @staticmethod
    def _record_activity(
        conn: sqlite3.Connection,
        *,
        node_id: str = "",
        action: str,
        actor: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        created_at = _now()
        clean_metadata = metadata or {}
        cursor = conn.execute(
            """
            INSERT INTO archub_content_activity (
                node_id, action, actor, summary, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                action,
                actor,
                summary,
                _json_dumps(clean_metadata),
                created_at,
            ),
        )
        payload = {
            "activity_id": int(cursor.lastrowid or 0),
            "event_type": action,
            "aggregate_id": node_id,
            "actor": actor,
            "summary": summary,
            "metadata": clean_metadata,
            "occurred_at": created_at,
        }
        ArcHubCMSService._enqueue_webhook_deliveries(
            conn,
            event_type=action,
            aggregate_id=node_id,
            payload=payload,
        )

    def _refresh_descendant_routes(self, conn: sqlite3.Connection, node_id: str) -> None:
        parent = self._get_node_row(conn, node_id)
        rows = conn.execute(
            "SELECT node_id, slug FROM archub_content_nodes WHERE parent_id = ? ORDER BY sort_order, name",
            (node_id,),
        ).fetchall()
        for row in rows:
            child_id = str(row["node_id"])
            route_path = _route_for(str(parent["route_path"]), str(row["slug"]))
            conn.execute(
                "UPDATE archub_content_nodes SET route_path = ? WHERE node_id = ?",
                (route_path, child_id),
            )
            self._refresh_descendant_routes(conn, child_id)

    def _normalize_public_path(self, route_path: str) -> str:
        route_path = "/" + route_path.strip("/")
        if route_path == "/":
            return _PUBLIC_ROOT
        if route_path == _PUBLIC_ROOT or route_path.startswith(_PUBLIC_ROOT + "/"):
            return route_path
        return _PUBLIC_ROOT + route_path


@cache
def get_archub_cms_service() -> ArcHubCMSService:
    db_path = os.getenv("ARCHUB_CMS_DB", "data/archub_cms.db")
    return ArcHubCMSService(db_path)
