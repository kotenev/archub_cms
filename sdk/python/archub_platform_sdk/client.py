"""HTTP client for ArcHub platform APIs."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from archub_platform_sdk.models import ArcHubResponse, RequestSpec

Transport = Callable[[RequestSpec, str, dict[str, str], bytes | None, float], ArcHubResponse]


class ArcHubClientError(RuntimeError):
    """Raised when ArcHub returns a non-2xx response or invalid JSON."""


class ArcHubClient:
    def __init__(
        self,
        base_url: str,
        *,
        token: str = "",
        timeout: float = 15.0,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._transport = transport

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        spec = RequestSpec(method=method.upper(), path=path, query=query, json_body=json_body)
        url = self._url(path, query)
        headers = {"Accept": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        body: bytes | None = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        response = (
            self._transport(spec, url, headers, body, self.timeout)
            if self._transport is not None
            else self._urllib(spec, url, headers, body, self.timeout)
        )
        if response.status < 200 or response.status >= 300:
            raise ArcHubClientError(f"{method} {path} failed with HTTP {response.status}")
        return response.data

    def capabilities(self) -> dict[str, Any]:
        return self.request("GET", "/api/platform/capabilities")

    def platform_index(self) -> dict[str, Any]:
        return self.request("GET", "/api/platform/index")

    def core_plugins(self) -> dict[str, Any]:
        return self.request("GET", "/api/platform/core-plugins")

    def rust_workspace(self) -> dict[str, Any]:
        return self.request("GET", "/api/platform/core-plugins/rust-workspace")

    def plugin_catalog(self) -> dict[str, Any]:
        return self.request("GET", "/api/platform/plugins/manage")

    def enable_plugin(self, plugin_id: str, *, actor: str = "") -> dict[str, Any]:
        return self.request(
            "POST",
            f"/api/platform/plugins/{urllib.parse.quote(plugin_id)}/enable",
            json_body={"actor": actor},
        )

    def disable_plugin(self, plugin_id: str, *, actor: str = "") -> dict[str, Any]:
        return self.request(
            "POST",
            f"/api/platform/plugins/{urllib.parse.quote(plugin_id)}/disable",
            json_body={"actor": actor},
        )

    def marketplace(self, repository: str) -> dict[str, Any]:
        return self.request(
            "GET",
            "/api/platform/modules/marketplace",
            query={"repository": repository},
        )

    def install_from_marketplace(
        self,
        repository: str,
        module_id: str,
        *,
        version: str = "",
        actor: str = "",
        enable: bool | None = None,
        replace: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "repository": repository,
            "module_id": module_id,
            "version": version,
            "actor": actor,
            "replace": replace,
        }
        if enable is not None:
            body["enable"] = enable
        return self.request("POST", "/api/platform/modules/marketplace/install", json_body=body)

    def delivery_tree(self, *, start_item: str = "") -> dict[str, Any]:
        headers = {"Start-Item": start_item} if start_item else None
        return self.request("GET", "/cms/api/tree", extra_headers=headers)

    def delivery_content(self, path: str = "", *, fields: str = "", expand: str = "") -> dict[str, Any]:
        endpoint = "/cms/api/content" if not path else f"/cms/api/content/{path.strip('/')}"
        return self.request("GET", endpoint, query={"fields": fields, "expand": expand})

    def delivery_search(self, query: str, *, limit: int = 20) -> dict[str, Any]:
        return self.request("GET", "/cms/api/search", query={"q": query, "limit": limit})

    def knowledge_search(self, query: str, *, space_key: str = "", limit: int = 10) -> dict[str, Any]:
        return self.request(
            "GET",
            "/api/platform/knowledge/search",
            query={"q": query, "space_key": space_key, "limit": limit},
        )

    def knowledge_answer(
        self,
        question: str,
        *,
        space_key: str = "",
        corpus_key: str = "",
        limit: int = 5,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "/api/platform/knowledge/answer",
            json_body={
                "question": question,
                "space_key": space_key,
                "corpus_key": corpus_key,
                "limit": limit,
            },
        )

    def runtime_status(self) -> dict[str, Any]:
        return self.request("GET", "/api/platform/runtime/status")

    def runtime_export(self, *, actor: str = "") -> dict[str, Any]:
        return self.request("POST", "/api/platform/runtime/export", json_body={"actor": actor})

    def _url(self, path: str, query: dict[str, Any] | None = None) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        encoded_query = ""
        if query:
            clean_query = {key: value for key, value in query.items() if value not in {"", None}}
            encoded_query = urllib.parse.urlencode(clean_query)
        suffix = f"?{encoded_query}" if encoded_query else ""
        return f"{self.base_url}{clean_path}{suffix}"

    @staticmethod
    def _urllib(
        spec: RequestSpec,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> ArcHubResponse:
        request = urllib.request.Request(url, data=body, headers=headers, method=spec.method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
                return ArcHubResponse(
                    status=response.status,
                    headers={key.lower(): value for key, value in response.headers.items()},
                    data=data,
                )
        except urllib.error.HTTPError as exc:
            raise ArcHubClientError(f"{spec.method} {spec.path} failed: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ArcHubClientError(f"{spec.method} {spec.path} failed: {exc}") from exc
