"""DDD application service for ArcHub corporate knowledge-base use cases."""

from __future__ import annotations

__all__ = [
    "ArcHubKnowledgeBaseService",
    "ExtractiveLLMProvider",
    "OpenAICompatibleLLMProvider",
    "get_archub_knowledge_base_service",
]

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from typing import Any

from archub_cms.application.embeddings import get_embedder_from_settings
from archub_cms.application.plugins import ArcHubPluginRegistry, get_archub_plugin_registry
from archub_cms.domain.knowledge import (
    KnowledgeAnswer,
    KnowledgeDocument,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeSource,
    KnowledgeSpace,
    extract_knowledge_links,
    slug_to_space_key,
)
from archub_cms.infrastructure.db.database import Database
from archub_cms.infrastructure.sqlite.embedding_repository import SqliteEmbeddingRepository
from archub_cms.ports import EmbeddingPort, LLMProviderPort, LLMRequest, LLMResponse, SearchPort
from archub_cms.services.cms import ArcHubCMSService, ContentNode, get_archub_cms_service
from archub_cms.settings import ArcHubSettings

_KNOWLEDGE_TYPES = (
    "page",
    "knowledge_article",
    "rag_material",
    "bot_landing",
    "expert_page",
    "ai_expert",
    "bot_resource",
)
_TAG_SPLIT_RE = re.compile(r"[,#\s]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
# How strongly semantic similarity (0..1) re-ranks vs. lexical token scores.
_SEMANTIC_WEIGHT = 6.0


@dataclass(frozen=True)
class KnowledgeQuery:
    q: str = ""
    space_key: str = ""
    tags: tuple[str, ...] = ()
    limit: int = 25


class ExtractiveLLMProvider:
    """Offline fallback that answers only from retrieved source excerpts."""

    provider_name = "offline-extractive"
    mode = "offline"

    def complete(self, request: LLMRequest) -> LLMResponse:
        contexts = list(request.context)
        if not contexts:
            return LLMResponse(
                text="No published knowledge sources matched the question.",
                provider=self.provider_name,
                mode=self.mode,
                model="extractive",
                metadata={"grounded": True, "source_count": 0},
            )
        lines = []
        for index, item in enumerate(contexts[:5], start=1):
            title = str(item.get("title") or f"Source {index}")
            excerpt = _squash(str(item.get("excerpt") or ""))[:420]
            lines.append(f"{index}. {title}: {excerpt}")
        return LLMResponse(
            text=(
                "Grounded draft answer from published ArcHub knowledge sources:\n"
                + "\n".join(lines)
            ),
            provider=self.provider_name,
            mode=self.mode,
            model="extractive",
            metadata={"grounded": True, "source_count": len(contexts)},
        )


class OpenAICompatibleLLMProvider:
    """Minimal stdlib client for cloud or local OpenAI-compatible chat APIs."""

    provider_name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        model: str = "",
        timeout_seconds: float = 15.0,
        mode: str = "online",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model or "gpt-4.1-mini"
        self._timeout_seconds = timeout_seconds
        self.mode = mode

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self._base_url:
            raise ValueError("ARCHUB_LLM_BASE_URL is required for openai-compatible provider")
        context_text = "\n\n".join(
            f"Source: {item.get('title')}\nURL: {item.get('route_path')}\n{item.get('excerpt')}"
            for item in request.context
        )
        payload = {
            "model": request.model or self._model,
            "temperature": request.temperature,
            "messages": [
                {
                    "role": "system",
                    "content": request.system_prompt
                    or "Answer only from the provided ArcHub knowledge context.",
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context_text}\n\nQuestion:\n{request.prompt}",
                },
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        http_request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"LLM provider request failed: {exc}") from exc
        text = (
            str(data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
            if isinstance(data.get("choices"), list)
            else ""
        )
        return LLMResponse(
            text=text or "The configured LLM provider returned an empty answer.",
            provider=self.provider_name,
            model=str(data.get("model") or request.model or self._model),
            mode=self.mode,
            metadata={"usage": data.get("usage", {}) if isinstance(data, dict) else {}},
        )


class ArcHubKnowledgeBaseService:
    """Application boundary for enterprise knowledge-base use cases."""

    def __init__(
        self,
        cms: ArcHubCMSService | None = None,
        *,
        settings: ArcHubSettings | None = None,
        llm_provider: LLMProviderPort | None = None,
        plugin_registry: ArcHubPluginRegistry | None = None,
        embedder: EmbeddingPort | None = None,
        search_index: SearchPort | None = None,
        plugin_host: Any | None = None,
    ) -> None:
        self._cms = cms or get_archub_cms_service()
        self._settings = settings or ArcHubSettings.from_env()
        self._llm_provider = llm_provider or _llm_provider_from_settings(self._settings)
        self._plugin_registry = plugin_registry or get_archub_plugin_registry(self._settings)
        # Semantic search is on by default via the offline hashing embedder.
        self._embedder = embedder or get_embedder_from_settings(self._settings)
        self._search_index = search_index or SqliteEmbeddingRepository(
            Database(self._cms.db_path), self._embedder
        )
        # Plugin host is optional; injected lazily to avoid import cycles at boot.
        self._plugin_host = plugin_host
        self._indexed = False

    def platform_report(self) -> dict[str, Any]:
        documents = self._documents()
        graph = self.graph()
        plugins = self._plugin_registry.catalog()
        return {
            "bounded_context": "knowledge-base",
            "ddd": {
                "aggregate": "KnowledgeSpace",
                "entities": ["KnowledgeDocument", "KnowledgeEdge"],
                "value_objects": ["space_key", "route_path", "tag", "plugin_id"],
                "ports": ["LLMProviderPort", "plugin manifest registry"],
            },
            "spaces": [item.as_dict() for item in self.spaces()],
            "document_total": len(documents),
            "graph": {
                "edge_count": graph.as_dict()["edge_count"],
                "orphaned_count": graph.as_dict()["orphaned_count"],
                "unresolved_count": graph.as_dict()["unresolved_count"],
            },
            "plugins": {
                "total": plugins["total"],
                "capability_counts": plugins["capability_counts"],
            },
            "llm": {
                "provider": self._llm_provider.provider_name,
                "mode": self._llm_provider.mode,
                "configured_model": self._settings.llm_model,
            },
        }

    def spaces(self) -> tuple[KnowledgeSpace, ...]:
        documents = self._documents()
        top_level = {
            node.route_path: node
            for node in self._cms.list_tree()
            if node.is_published and node.route_path.count("/") <= 2
        }
        grouped: dict[str, list[KnowledgeDocument]] = {}
        for document in documents:
            grouped.setdefault(document.space_key, []).append(document)
        spaces: list[KnowledgeSpace] = []
        for space_key, items in sorted(grouped.items()):
            root_path = f"/cms/{space_key}" if space_key != "root" else "/cms"
            root = top_level.get(root_path)
            first = items[0]
            spaces.append(
                KnowledgeSpace(
                    key=space_key,
                    name=root.name if root is not None else first.title,
                    root_node_id=root.node_id if root is not None else first.node_id,
                    route_path=root.route_path if root is not None else first.route_path,
                    document_count=len(items),
                    updated_at=max(item.updated_at for item in items),
                    tags=tuple(sorted({tag for item in items for tag in item.tags})),
                )
            )
        return tuple(spaces)

    def documents(self, query: KnowledgeQuery | None = None) -> dict[str, Any]:
        source = query or KnowledgeQuery()
        items = self._filter_documents(source)
        return {
            "items": [item.as_dict() for item in items],
            "total": len(items),
            "query": {
                "q": source.q,
                "space_key": source.space_key,
                "tags": list(source.tags),
                "limit": source.limit,
            },
        }

    def graph(self, *, space_key: str = "", limit: int = 200) -> KnowledgeGraph:
        documents = self._filter_documents(KnowledgeQuery(space_key=space_key, limit=limit))
        by_route = {item.route_path.rstrip("/"): item for item in documents}
        edges: list[KnowledgeEdge] = []
        for document in documents:
            text = "\n".join((document.summary, document.body))
            for target in extract_knowledge_links(text):
                clean_target = target.rstrip("/") or "/cms"
                target_document = by_route.get(clean_target)
                edges.append(
                    KnowledgeEdge(
                        source=document.route_path,
                        target=target_document.route_path if target_document else clean_target,
                        unresolved=target_document is None,
                    )
                )
        outgoing = {edge.source for edge in edges}
        incoming = {edge.target for edge in edges if not edge.unresolved}
        orphaned = tuple(
            item
            for item in documents
            if item.route_path not in outgoing and item.route_path not in incoming
        )
        unresolved = tuple(edge for edge in edges if edge.unresolved)
        return KnowledgeGraph(
            documents=tuple(documents),
            edges=tuple(edges),
            orphaned_documents=orphaned,
            unresolved_links=unresolved,
        )

    def answer(
        self,
        question: str,
        *,
        space_key: str = "",
        corpus_key: str = "",
        limit: int = 5,
    ) -> KnowledgeAnswer:
        sources = self._answer_sources(
            question, space_key=space_key, corpus_key=corpus_key, limit=limit
        )
        response = self._llm_provider.complete(
            LLMRequest(
                prompt=question,
                context=tuple(item.as_dict() for item in sources),
                model=self._settings.llm_model,
                metadata={"space_key": space_key, "corpus_key": corpus_key},
            )
        )
        return KnowledgeAnswer(
            question=question,
            answer=response.text,
            provider=response.provider,
            mode=response.mode,
            sources=tuple(sources),
            metadata={"model": response.model, **dict(response.metadata)},
        )

    def vault_export(self, *, space_key: str = "", limit: int = 500) -> dict[str, Any]:
        documents = self._filter_documents(KnowledgeQuery(space_key=space_key, limit=limit))
        files = []
        for document in documents:
            front_matter = {
                "title": document.title,
                "space": document.space_key,
                "route_path": document.route_path,
                "content_type": document.content_type_alias,
                "tags": list(document.tags),
            }
            body = document.body or document.summary
            files.append(
                {
                    "path": document.markdown_path,
                    "front_matter": front_matter,
                    "content": _markdown_document(front_matter, body),
                }
            )
        return {
            "format": "obsidian-compatible-markdown-vault",
            "space_key": space_key,
            "files": files,
            "total": len(files),
        }

    def plugin_catalog(self) -> dict[str, Any]:
        return self._plugin_registry.catalog()

    def hybrid_search(
        self, query: str, *, space_key: str = "", limit: int = 10
    ) -> list[KnowledgeSource]:
        """Blend lexical, semantic (vector) and plugin-contributed results."""
        candidates: dict[str, KnowledgeSource] = {}
        for source in self._search_sources(query, space_key=space_key, limit=limit * 2):
            candidates[source.route_path] = source

        by_route = {doc.route_path: doc for doc in self._documents()}
        for route, similarity in self._semantic_scores(query, space_key=space_key, limit=limit * 2):
            document = by_route.get(route)
            if document is None or similarity <= 0:
                continue
            boost = _SEMANTIC_WEIGHT * similarity
            existing = candidates.get(route)
            if existing is not None:
                candidates[route] = replace(existing, score=existing.score + boost)
            else:
                candidates[route] = KnowledgeSource(
                    title=document.title,
                    route_path=route,
                    excerpt=_excerpt(document.body or document.summary, query),
                    score=boost,
                )

        for hit in self._plugin_hits(query, limit=limit):
            existing = candidates.get(hit.route_path)
            base = existing.score if existing is not None else 0.0
            candidates[hit.route_path] = KnowledgeSource(
                title=(existing.title if existing else hit.title) or hit.route_path,
                route_path=hit.route_path,
                excerpt=(existing.excerpt if existing else hit.excerpt),
                score=base + hit.score,
            )

        return sorted(candidates.values(), key=lambda item: (-item.score, item.route_path))[:limit]

    def _answer_sources(
        self,
        question: str,
        *,
        space_key: str,
        corpus_key: str,
        limit: int,
    ) -> list[KnowledgeSource]:
        candidates: dict[str, KnowledgeSource] = {
            source.route_path: source
            for source in self.hybrid_search(question, space_key=space_key, limit=limit)
        }
        for node in self._cms.search_published_rag_materials(
            corpus_key or None, question, limit=limit
        ):
            payload = node.published
            excerpt = _excerpt(str(payload.get("body") or ""), question)
            candidates[node.route_path] = KnowledgeSource(
                title=str(payload.get("title") or node.name),
                route_path=node.route_path,
                excerpt=excerpt,
                score=max(candidates.get(node.route_path, KnowledgeSource("", "", "")).score, 8.0),
            )
        return sorted(candidates.values(), key=lambda item: (-item.score, item.route_path))[:limit]

    def _ensure_index(self) -> None:
        if self._indexed:
            return
        for document in self._documents():
            text = " ".join(
                (document.title, document.summary, " ".join(document.tags), document.body)
            )
            try:
                self._search_index.index(document.route_path, text)
            except Exception:  # indexing must never break answering
                continue
        self._indexed = True

    def _semantic_scores(
        self, query: str, *, space_key: str, limit: int
    ) -> list[tuple[str, float]]:
        try:
            self._ensure_index()
            return self._search_index.query(query, limit=limit)
        except Exception:  # fall back to lexical-only on any failure
            return []

    def _plugin_hits(self, query: str, *, limit: int) -> list[Any]:
        host = self._plugin_host
        if host is None:
            return []
        try:
            return list(host.search(query, limit=limit))
        except Exception:  # a plugin must not break the answer path
            return []

    def _search_sources(
        self, q: str, *, space_key: str = "", limit: int = 10
    ) -> list[KnowledgeSource]:
        tokens = _tokens(q)
        scored: list[KnowledgeSource] = []
        for document in self._filter_documents(KnowledgeQuery(space_key=space_key, limit=500)):
            haystacks = {
                "title": document.title.casefold(),
                "summary": document.summary.casefold(),
                "tags": " ".join(document.tags).casefold(),
                "body": document.body.casefold(),
            }
            score = (
                1
                if not tokens
                else sum(
                    (5 if token in haystacks["title"] else 0)
                    + (4 if token in haystacks["tags"] else 0)
                    + (3 if token in haystacks["summary"] else 0)
                    + (1 if token in haystacks["body"] else 0)
                    for token in tokens
                )
            )
            if score:
                scored.append(
                    KnowledgeSource(
                        title=document.title,
                        route_path=document.route_path,
                        excerpt=_excerpt(document.body or document.summary, q),
                        score=score,
                    )
                )
        return sorted(scored, key=lambda item: (-item.score, item.route_path))[: max(1, limit)]

    def _filter_documents(self, query: KnowledgeQuery) -> list[KnowledgeDocument]:
        tokens = _tokens(query.q)
        tag_filter = {tag.casefold() for tag in query.tags if tag}
        items: list[KnowledgeDocument] = []
        for document in self._documents():
            if query.space_key and document.space_key != query.space_key:
                continue
            if tag_filter and not tag_filter.issubset({tag.casefold() for tag in document.tags}):
                continue
            if tokens:
                text = " ".join(
                    (document.title, document.summary, " ".join(document.tags), document.body)
                ).casefold()
                if not all(token in text for token in tokens):
                    continue
            items.append(document)
        return items[: max(1, min(query.limit, 500))]

    def _documents(self) -> tuple[KnowledgeDocument, ...]:
        documents: list[KnowledgeDocument] = []
        for node in self._cms.list_tree():
            if not node.is_published or node.content_type_alias not in _KNOWLEDGE_TYPES:
                continue
            documents.append(_document_from_node(node))
        documents.sort(key=lambda item: (item.space_key, item.route_path))
        return tuple(documents)


def get_archub_knowledge_base_service(
    cms: ArcHubCMSService | None = None,
    *,
    settings: ArcHubSettings | None = None,
    llm_provider: LLMProviderPort | None = None,
    plugin_registry: ArcHubPluginRegistry | None = None,
    embedder: EmbeddingPort | None = None,
    search_index: SearchPort | None = None,
    plugin_host: Any | None = None,
) -> ArcHubKnowledgeBaseService:
    return ArcHubKnowledgeBaseService(
        cms,
        settings=settings,
        llm_provider=llm_provider,
        plugin_registry=plugin_registry,
        embedder=embedder,
        search_index=search_index,
        plugin_host=plugin_host,
    )


def _llm_provider_from_settings(settings: ArcHubSettings) -> LLMProviderPort:
    provider = settings.llm_provider.strip().casefold()
    if provider in {"openai-compatible", "online", "ollama", "local-openai"}:
        mode = (
            "offline"
            if "localhost" in settings.llm_base_url or "127.0.0.1" in settings.llm_base_url
            else "online"
        )
        return OpenAICompatibleLLMProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            mode=mode,
        )
    return ExtractiveLLMProvider()


def _document_from_node(node: ContentNode) -> KnowledgeDocument:
    payload = node.published
    title = str(payload.get("title") or payload.get("hero_title") or node.name)
    body = _plain_text(
        "\n".join(
            str(payload.get(key) or "")
            for key in ("body", "excerpt", "summary", "hero_text", "system_prompt")
        )
    )
    tags = _tags(str(payload.get("tags") or payload.get("category") or ""))
    return KnowledgeDocument(
        node_id=node.node_id,
        space_key=slug_to_space_key(node.route_path),
        title=title,
        route_path=node.route_path,
        content_type_alias=node.content_type_alias,
        summary=_squash(str(payload.get("excerpt") or payload.get("summary") or ""))[:300],
        body=body,
        tags=tags,
        source_path=str(payload.get("source_path") or ""),
        updated_at=node.updated_at,
    )


def _tags(raw: str) -> tuple[str, ...]:
    return tuple(
        sorted({item.strip().casefold() for item in _TAG_SPLIT_RE.split(raw) if item.strip()})
    )


def _tokens(raw: str) -> tuple[str, ...]:
    return tuple(item for item in re.split(r"[^a-zA-Z0-9_-]+", raw.casefold()) if len(item) >= 2)


def _plain_text(raw: str) -> str:
    return _squash(_HTML_TAG_RE.sub(" ", raw))


def _squash(raw: str) -> str:
    return re.sub(r"\s+", " ", raw or "").strip()


def _excerpt(text: str, query: str, *, max_length: int = 520) -> str:
    clean = _squash(text)
    if len(clean) <= max_length:
        return clean
    tokens = _tokens(query)
    lowered = clean.casefold()
    positions = [lowered.find(token) for token in tokens if lowered.find(token) >= 0]
    start = max(0, min(positions) - 120) if positions else 0
    return clean[start : start + max_length].strip()


def _markdown_document(front_matter: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, value in front_matter.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(str(item) for item in value)}]")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {front_matter['title']}")
    lines.append("")
    lines.append(body.strip())
    return "\n".join(lines).strip() + "\n"
