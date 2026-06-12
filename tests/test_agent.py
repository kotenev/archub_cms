"""Tests for agentic tool-augmented answering (Phase 19)."""

from __future__ import annotations

import pytest

from archub_cms.application.agent_service import get_archub_agent_service
from archub_cms.application.knowledge import get_archub_knowledge_base_service
from archub_cms.demo import seed_demo_content
from archub_cms.extensibility.host import PluginHost
from archub_cms.services.cms import get_archub_cms_service


@pytest.fixture
def agent(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "archub.db"))
    get_archub_cms_service.cache_clear()
    cms = get_archub_cms_service()
    seed_demo_content(cms)
    host = PluginHost().load()
    knowledge = get_archub_knowledge_base_service(cms, plugin_host=host)
    return get_archub_agent_service(knowledge=knowledge, plugin_host=host)


def test_available_tools_includes_summarize(agent):
    assert "summarize" in agent.available_tools()


def test_tool_selection_modes(agent):
    # explicit (filtered to known)
    assert agent.select_tools("q", requested=("summarize", "nope")) == ["summarize"]
    # auto: name appears in question
    assert agent.select_tools("please summarize this", auto=True) == ["summarize"]
    assert agent.select_tools("unrelated question", auto=True) == []
    # neither → no tools
    assert agent.select_tools("summarize", requested=(), auto=False) == []


def test_answer_runs_requested_tool_and_augments(agent):
    result = agent.answer("What is ArcHub?", tools=("summarize",))
    assert result["provider"] == "offline-extractive"
    assert result["sources"]
    used = {t["name"] for t in result["tools_used"]}
    assert "summarize" in used
    assert "augmented_answer" in result
    assert "summarize" in result["augmented_answer"]


def test_answer_without_tools_has_no_augmentation(agent):
    result = agent.answer("What is ArcHub?")
    assert result["tools_used"] == []
    assert "augmented_answer" not in result


def test_auto_selects_tool_by_keyword(agent):
    result = agent.answer("Can you summarize the docs?", auto=True)
    assert [t["name"] for t in result["tools_used"]] == ["summarize"]


def test_unknown_tool_is_ignored(agent):
    result = agent.answer("x", tools=("does-not-exist",))
    assert result["tools_used"] == []


# --- endpoints ------------------------------------------------------------


def test_agent_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from archub_cms.app import create_archub_app
    from archub_cms.extensibility.host import get_plugin_host

    monkeypatch.setenv("ARCHUB_CMS_DB", str(tmp_path / "web.db"))
    get_archub_cms_service.cache_clear()
    get_plugin_host(reload=True)

    with TestClient(create_archub_app()) as client:
        tools = client.get("/api/platform/knowledge/tools").json()
        assert "summarize" in tools["tools"]

        answered = client.post(
            "/api/platform/knowledge/agent-answer",
            json={"question": "What is ArcHub?", "tools": ["summarize"]},
        )
        assert answered.status_code == 200
        body = answered.json()
        assert body["sources"]
        assert any(t["name"] == "summarize" for t in body["tools_used"])
