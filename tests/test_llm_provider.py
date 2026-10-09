"""
tests/test_llm_provider.py — OpenRouter provider adapter unit tests.

All provider calls are mocked — no real network calls are made here.
A separate live integration test is in tests/test_llm_provider_live.py
(opt-in, requires OPENROUTER_API_KEY and OPENROUTER_RUN_LIVE_TESTS=true).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Ensure no real API key leaks into tests
os.environ.pop("OPENROUTER_API_KEY", None)

from llm_provider import (
    OPENROUTER_DEFAULT_MODEL,
    LLMPlannerProvider,
    OpenRouterPlannerProvider,
    ProviderError,
    get_provider,
    get_provider_info,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_PLAN_JSON = json.dumps({
    "target": {"concept": "swimming_pool", "kind": "instance", "filters": {"min_area_m2": None}},
    "relations": [{"type": "dwithin", "reference_concept": "road", "distance_m": 100.0, "negate": False}],
    "limit": None,
    "session_id": None,
})

INVALID_PLAN_JSON = json.dumps({
    "target": {"concept": "pool", "kind": "magic"},  # invalid kind
    "relations": [],
})

MALFORMED_JSON = "This is not JSON at all."

MARKDOWN_WRAPPED_JSON = f"```json\n{VALID_PLAN_JSON}\n```"


def _mock_response(content: str, status_code: int = 200) -> MagicMock:
    """Build a mock requests.Response with the given content and status."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    mock.text = content
    return mock


def _make_provider(**kwargs) -> OpenRouterPlannerProvider:
    return OpenRouterPlannerProvider(api_key="test-key-never-logged", **kwargs)


# ---------------------------------------------------------------------------
# Interface conformance
# ---------------------------------------------------------------------------

class TestProviderInterface:

    def test_openrouter_implements_interface(self):
        provider = _make_provider()
        assert isinstance(provider, LLMPlannerProvider)

    def test_provider_name(self):
        provider = _make_provider()
        assert provider.provider_name == "openrouter"

    def test_default_model(self):
        provider = _make_provider()
        assert provider.model == OPENROUTER_DEFAULT_MODEL

    def test_custom_model_from_arg(self):
        provider = _make_provider(model="openai/gpt-4o-mini")
        assert provider.model == "openai/gpt-4o-mini"

    def test_custom_model_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        # Reload to pick up env var
        provider = OpenRouterPlannerProvider(api_key="k")
        assert provider.model == "openai/gpt-4o-mini"

    def test_no_api_key_raises(self):
        with pytest.raises(ProviderError, match="OPENROUTER_API_KEY"):
            OpenRouterPlannerProvider(api_key="")


# ---------------------------------------------------------------------------
# Successful responses
# ---------------------------------------------------------------------------

class TestSuccessfulResponses:

    @patch("llm_provider.requests.post")
    def test_valid_json_response(self, mock_post):
        mock_post.return_value = _mock_response(VALID_PLAN_JSON)
        provider = _make_provider()
        result = provider.generate_plan([{"role": "user", "content": "pools near roads"}])
        assert "swimming_pool" in result

    @patch("llm_provider.requests.post")
    def test_markdown_wrapped_json_returned_as_is(self, mock_post):
        """Provider returns raw content; extraction is caller's responsibility."""
        mock_post.return_value = _mock_response(MARKDOWN_WRAPPED_JSON)
        provider = _make_provider()
        result = provider.generate_plan([{"role": "user", "content": "test"}])
        assert VALID_PLAN_JSON in result or "swimming_pool" in result

    @patch("llm_provider.requests.post")
    def test_structured_output_payload_includes_response_format(self, mock_post):
        mock_post.return_value = _mock_response(VALID_PLAN_JSON)
        provider = _make_provider()
        schema = {"type": "object", "properties": {}}
        provider.generate_plan([{"role": "user", "content": "test"}], response_schema=schema)
        call_args = mock_post.call_args
        payload = call_args.kwargs.get("json") or call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["json"]
        assert payload.get("response_format", {}).get("type") == "json_schema"

    @patch("llm_provider.requests.post")
    def test_structured_output_payload_includes_require_parameters(self, mock_post):
        mock_post.return_value = _mock_response(VALID_PLAN_JSON)
        provider = _make_provider()
        schema = {"type": "object"}
        provider.generate_plan([{"role": "user", "content": "test"}], response_schema=schema)
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1]
        assert payload.get("provider", {}).get("require_parameters") is True

    @patch("llm_provider.requests.post")
    def test_no_schema_omits_response_format(self, mock_post):
        mock_post.return_value = _mock_response(VALID_PLAN_JSON)
        provider = _make_provider()
        provider.generate_plan([{"role": "user", "content": "test"}], response_schema=None)
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1]
        assert "response_format" not in payload

    @patch("llm_provider.requests.post")
    def test_temperature_zero(self, mock_post):
        mock_post.return_value = _mock_response(VALID_PLAN_JSON)
        provider = _make_provider()
        provider.generate_plan([{"role": "user", "content": "test"}])
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1]
        assert payload["temperature"] == 0.0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:

    @patch("llm_provider.requests.post")
    def test_401_raises_non_retryable(self, mock_post):
        mock_post.return_value = _mock_response("Unauthorized", status_code=401)
        provider = _make_provider()
        with pytest.raises(ProviderError) as exc_info:
            provider.generate_plan([{"role": "user", "content": "test"}])
        assert not exc_info.value.retryable
        assert exc_info.value.status_code == 401

    @patch("llm_provider.requests.post")
    def test_403_raises_non_retryable(self, mock_post):
        mock_post.return_value = _mock_response("Forbidden", status_code=403)
        provider = _make_provider()
        with pytest.raises(ProviderError) as exc_info:
            provider.generate_plan([{"role": "user", "content": "test"}])
        assert not exc_info.value.retryable

    @patch("llm_provider.requests.post")
    def test_429_retries_then_raises(self, mock_post):
        mock_post.return_value = _mock_response("Rate limited", status_code=429)
        provider = _make_provider(max_retries=1)
        with pytest.raises(ProviderError):
            provider.generate_plan([{"role": "user", "content": "test"}])
        # Should have been called 2 times (1 initial + 1 retry)
        assert mock_post.call_count == 2

    @patch("llm_provider.requests.post")
    def test_500_retries_then_raises(self, mock_post):
        mock_post.return_value = _mock_response("Server error", status_code=500)
        provider = _make_provider(max_retries=2)
        with pytest.raises(ProviderError):
            provider.generate_plan([{"role": "user", "content": "test"}])
        assert mock_post.call_count == 3  # 1 + 2 retries

    @patch("llm_provider.requests.post")
    def test_timeout_retries(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.Timeout()
        provider = _make_provider(max_retries=1)
        with pytest.raises(ProviderError, match="timed out"):
            provider.generate_plan([{"role": "user", "content": "test"}])
        assert mock_post.call_count == 2

    @patch("llm_provider.requests.post")
    def test_null_content_raises(self, mock_post):
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {"choices": [{"message": {"content": None}}]}
        mock_post.return_value = mock
        provider = _make_provider()
        with pytest.raises(ProviderError, match="null content"):
            provider.generate_plan([{"role": "user", "content": "test"}])

    @patch("llm_provider.requests.post")
    def test_malformed_response_raises(self, mock_post):
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {"unexpected": "shape"}
        mock.text = "{}"
        mock_post.return_value = mock
        provider = _make_provider()
        with pytest.raises(ProviderError, match="parse error"):
            provider.generate_plan([{"role": "user", "content": "test"}])


# ---------------------------------------------------------------------------
# API key security
# ---------------------------------------------------------------------------

class TestAPIKeySecurity:

    @patch("llm_provider.requests.post")
    def test_api_key_in_header_not_body(self, mock_post):
        """API key must only appear in Authorization header, never in the request body."""
        mock_post.return_value = _mock_response(VALID_PLAN_JSON)
        provider = _make_provider()
        provider.generate_plan([{"role": "user", "content": "test"}])

        call_kwargs = mock_post.call_args.kwargs
        headers = call_kwargs.get("headers", {})
        body = json.dumps(call_kwargs.get("json", {}))

        assert "test-key-never-logged" in headers.get("Authorization", "")
        assert "test-key-never-logged" not in body

    def test_get_provider_info_does_not_expose_key(self):
        """get_provider_info() must never return the raw API key."""
        info = get_provider_info()
        for v in info.values():
            if isinstance(v, str):
                # Should only ever be True/False/model-name/url — never a secret
                assert "Bearer" not in v
                assert "sk-" not in v


# ---------------------------------------------------------------------------
# get_provider() factory
# ---------------------------------------------------------------------------

class TestGetProvider:

    def test_no_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        assert get_provider() is None

    def test_key_set_returns_provider(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        provider = get_provider()
        assert provider is not None
        assert isinstance(provider, OpenRouterPlannerProvider)

    def test_get_provider_info_no_key(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        info = get_provider_info()
        assert info["provider"] == "fallback"
        assert info["api_key_configured"] is False
        assert info["model"] is None

    def test_get_provider_info_with_key(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        info = get_provider_info()
        assert info["provider"] == "openrouter"
        assert info["api_key_configured"] is True
        assert info["model"] == OPENROUTER_DEFAULT_MODEL


# ---------------------------------------------------------------------------
# planner_agent integration (mocked provider)
# ---------------------------------------------------------------------------

class TestPlannerAgentWithProvider:

    @patch("llm_provider.requests.post")
    def test_valid_provider_response_used(self, mock_post, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        mock_post.return_value = _mock_response(VALID_PLAN_JSON)

        import planner_agent
        p, sid = planner_agent.plan("swimming pools within 100 m of a road")
        assert p.target.concept == "swimming_pool"
        assert p.relations[0].distance_m == 100.0

    @patch("llm_provider.requests.post")
    def test_invalid_schema_response_falls_back(self, mock_post, monkeypatch):
        """When provider returns a plan that fails validate_plan, fallback planner is used."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        mock_post.return_value = _mock_response(INVALID_PLAN_JSON)

        import planner_agent
        # Should not raise — fallback produces a valid plan
        p, _ = planner_agent.plan("swimming pools within 100 m of a road")
        from validate_plan import is_valid_plan
        assert is_valid_plan(p.to_dict())

    @patch("llm_provider.requests.post")
    def test_provider_failure_falls_back_to_rule_based(self, mock_post, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        mock_post.return_value = _mock_response("Auth failed", status_code=401)

        import planner_agent
        p, _ = planner_agent.plan("show me all roads")
        assert p.target.concept == "road"

    def test_no_key_uses_fallback_directly(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        import planner_agent
        p, _ = planner_agent.plan("buildings within 200 m of a park")
        assert p.target.concept == "building"

    @patch("llm_provider.requests.post")
    def test_follow_up_query_via_provider(self, mock_post, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        # First call: valid plan
        amended_plan = json.dumps({
            "target": {"concept": "swimming_pool", "kind": "instance", "filters": {"min_area_m2": None}},
            "relations": [{"type": "dwithin", "reference_concept": "road", "distance_m": 50.0, "negate": False}],
            "limit": None,
            "session_id": None,
        })
        mock_post.side_effect = [
            _mock_response(VALID_PLAN_JSON),  # first query
            _mock_response(amended_plan),      # follow-up
        ]

        import planner_agent
        _, sid = planner_agent.plan("swimming pools within 100 m of a road")
        p2, _ = planner_agent.plan("now within 50 m", session_id=sid)
        assert p2.relations[0].distance_m == 50.0

    @patch("llm_provider.requests.post")
    def test_unsupported_concept_still_valid_plan(self, mock_post, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        solar_plan = json.dumps({
            "target": {"concept": "solar_panel", "kind": "instance", "filters": {}},
            "relations": [],
            "limit": None,
            "session_id": None,
        })
        mock_post.return_value = _mock_response(solar_plan)

        import planner_agent
        p, _ = planner_agent.plan("solar panels on rooftops")
        from validate_plan import is_valid_plan
        assert is_valid_plan(p.to_dict())

    @patch("llm_provider.requests.post")
    def test_plan_source_not_leaked_to_client(self, mock_post, monkeypatch):
        """The OPENROUTER_API_KEY must never appear in the plan or session history."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-key-xyz")
        mock_post.return_value = _mock_response(VALID_PLAN_JSON)

        import planner_agent, json as _json
        p, sid = planner_agent.plan("pools near roads")
        plan_str = _json.dumps(p.to_dict())
        history_str = _json.dumps(planner_agent.get_session_history(sid))

        assert "super-secret-key-xyz" not in plan_str
        assert "super-secret-key-xyz" not in history_str
