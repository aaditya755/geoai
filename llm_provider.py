"""
llm_provider.py — LLM provider interface and OpenRouter adapter for GeoLens AI.

Architecture:
  LLMPlannerProvider (abstract interface)
      └── OpenRouterPlannerProvider   — production, uses OpenRouter chat completions API
      └── (future providers implement the same interface)

The planner_agent.py calls provider.generate_plan(...) and never depends on
OpenRouter-specific details. Adding a new provider requires only implementing
LLMPlannerProvider and wiring it in planner_agent.py's _get_provider().

GIS execution, geometry, and spatial rules are NOT the LLM's concern.
The provider's sole job: convert a text prompt into a schema-valid JSON plan string.

Configuration (all from environment — never hardcoded or exposed to the client):
  OPENROUTER_API_KEY       — required for live inference
  OPENROUTER_MODEL         — model ID (default: google/gemini-2.0-flash-001)
  OPENROUTER_BASE_URL      — override API base (default: https://openrouter.ai/api/v1)
  OPENROUTER_TIMEOUT_S     — request timeout in seconds (default: 30)
  OPENROUTER_MAX_RETRIES   — max retries for transient errors (default: 2)

Selected model rationale:
  google/gemini-2.0-flash-001
    - Confirmed structured output (json_schema) support via OpenRouter/Google provider
    - Strong JSON adherence on schema-constrained tasks
    - Good spatial/relational reasoning
    - Low cost ($0.10/$0.40 per 1M tokens input/output as of model release)
    - Stable versioned endpoint (not :free which varies)
  Free alternative:
    google/gemini-2.0-flash-exp:free
    - Zero cost but rate-limited and may vary between requests
    - Structured output confirmed on Google provider endpoint
    - Suitable for development and testing, not production evaluation
  Fallback if structured output fails:
    Any model: the provider falls back to prompt-based JSON extraction + local schema
    validation. The response is never accepted without passing validate_plan().
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import requests

# ---------------------------------------------------------------------------
# Configuration — read from environment, never from code
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
).rstrip("/")

# Default model: stable paid Gemini 2.0 Flash.
# Override via OPENROUTER_MODEL env var.
OPENROUTER_DEFAULT_MODEL = "google/gemini-2.0-flash-001"

OPENROUTER_TIMEOUT_S = int(os.environ.get("OPENROUTER_TIMEOUT_S", "30"))
OPENROUTER_MAX_RETRIES = int(os.environ.get("OPENROUTER_MAX_RETRIES", "2"))

# Non-retryable HTTP status codes (auth, schema errors, bad requests)
_NO_RETRY_STATUSES = {400, 401, 403, 422}


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

class LLMPlannerProvider(ABC):
    """
    Abstract interface for LLM-based plan generation.

    Implementors must provide generate_plan(). The caller (planner_agent.py)
    never sees provider-specific details.
    """

    @abstractmethod
    def generate_plan(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Send messages to the LLM and return the raw response string.

        Parameters
        ----------
        messages        : OpenAI-style message list [{"role": ..., "content": ...}]
        response_schema : JSON Schema dict to pass as response_format.json_schema.schema.
                          When provided, provider attempts structured output.
                          When None, provider requests plain JSON in the prompt.

        Returns
        -------
        Raw string content of the model's response.
        Raises ProviderError on all non-retried failures.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name for diagnostics (e.g. 'openrouter')."""


class ProviderError(Exception):
    """Raised when the provider cannot return a usable response."""

    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


# ---------------------------------------------------------------------------
# OpenRouter implementation
# ---------------------------------------------------------------------------

class OpenRouterPlannerProvider(LLMPlannerProvider):
    """
    LLM provider backed by OpenRouter's OpenAI-compatible chat completions API.

    Endpoint: POST https://openrouter.ai/api/v1/chat/completions
    Docs:     https://openrouter.ai/docs
              https://openrouter.ai/docs/guides/features/structured-outputs

    Structured output:
      Uses response_format = {"type": "json_schema", "json_schema": {...}, "strict": true}
      when response_schema is provided. Falls back to prompt-only JSON extraction if the
      provider endpoint returns a 4xx indicating the parameter is unsupported.
      Local schema validation (validate_plan) runs regardless.

    Provider routing:
      Sets require_parameters: true so the request is only routed to endpoints that
      actually support the requested parameters (structured output, temperature=0).
      This prevents silent routing to endpoints that ignore response_format.
    """

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_s: int = OPENROUTER_TIMEOUT_S,
        max_retries: int = OPENROUTER_MAX_RETRIES,
    ):
        if not api_key:
            raise ProviderError("OPENROUTER_API_KEY is not set.", retryable=False)
        self._api_key = api_key  # never logged, never exposed
        self._model = model or os.environ.get("OPENROUTER_MODEL", OPENROUTER_DEFAULT_MODEL)
        self._base_url = (base_url or OPENROUTER_BASE_URL).rstrip("/")
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._endpoint = f"{self._base_url}/chat/completions"

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def model(self) -> str:
        return self._model

    def generate_plan(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Call OpenRouter. Returns the raw response content string.
        Retries up to max_retries on transient (5xx / 429) errors only.
        Raises ProviderError on non-retryable failures.
        """
        payload = self._build_payload(messages, response_schema)
        headers = self._build_headers()

        last_exc: Optional[ProviderError] = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = requests.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout_s,
                )
            except requests.Timeout:
                last_exc = ProviderError(
                    f"OpenRouter request timed out after {self._timeout_s}s "
                    f"(attempt {attempt + 1}/{self._max_retries + 1}).",
                    retryable=True,
                )
                if attempt < self._max_retries:
                    time.sleep(1.5 ** attempt)
                continue
            except requests.ConnectionError as e:
                last_exc = ProviderError(
                    f"OpenRouter connection error: {e} "
                    f"(attempt {attempt + 1}/{self._max_retries + 1}).",
                    retryable=True,
                )
                if attempt < self._max_retries:
                    time.sleep(1.5 ** attempt)
                continue

            if resp.status_code == 200:
                return self._extract_content(resp)

            # Non-retryable errors
            if resp.status_code in _NO_RETRY_STATUSES:
                raise ProviderError(
                    f"OpenRouter returned HTTP {resp.status_code} "
                    f"(model={self._model}). "
                    f"Check OPENROUTER_API_KEY and model availability. "
                    f"Response: {resp.text[:200]}",
                    status_code=resp.status_code,
                    retryable=False,
                )

            # Retryable (429 rate limit, 5xx server errors)
            last_exc = ProviderError(
                f"OpenRouter returned HTTP {resp.status_code} "
                f"(attempt {attempt + 1}/{self._max_retries + 1}): {resp.text[:200]}",
                status_code=resp.status_code,
                retryable=True,
            )
            if attempt < self._max_retries:
                time.sleep(1.5 ** attempt)

        raise last_exc or ProviderError("OpenRouter: unknown failure after retries.")

    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.0,
        }

        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "geolens_plan",
                    "strict": True,
                    "schema": response_schema,
                },
            }
            # Route only to endpoints that actually support these parameters.
            # Prevents silent fallback to endpoints that ignore response_format.
            payload["provider"] = {
                "require_parameters": True,
            }

        return payload

    def _build_headers(self) -> Dict[str, str]:
        # API key is only ever placed in the Authorization header.
        # It is never logged, never returned to the client, never included
        # in error messages surfaced to the frontend.
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/geolens-ai",  # OpenRouter optional attribution
            "X-Title": "GeoLens AI",
        }

    @staticmethod
    def _extract_content(resp: requests.Response) -> str:
        """Extract the message content string from a successful OpenRouter response."""
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if content is None:
                raise ProviderError(
                    "OpenRouter returned null content. "
                    "The model may have refused the request or the endpoint "
                    "does not support the requested response_format.",
                    retryable=False,
                )
            return content
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ProviderError(
                f"OpenRouter response parse error: {e}. "
                f"Raw response (truncated): {resp.text[:300]}",
                retryable=False,
            ) from e


# ---------------------------------------------------------------------------
# Provider factory — single point where provider is constructed from env
# ---------------------------------------------------------------------------

def get_provider() -> Optional[LLMPlannerProvider]:
    """
    Return the configured provider, or None if no API key is available.

    The caller (planner_agent.py) treats None as "use fallback planner".
    API key is read from environment; never passed as an argument here.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    return OpenRouterPlannerProvider(api_key=api_key)


def get_provider_info() -> Dict[str, Any]:
    """
    Return diagnostic info about the current provider configuration.
    Safe to include in health-check responses — contains no secrets.
    """
    api_key_set = bool(os.environ.get("OPENROUTER_API_KEY"))
    model = os.environ.get("OPENROUTER_MODEL", OPENROUTER_DEFAULT_MODEL)
    return {
        "provider": "openrouter" if api_key_set else "fallback",
        "api_key_configured": api_key_set,
        "model": model if api_key_set else None,
        "base_url": OPENROUTER_BASE_URL,
        "structured_output": "json_schema",
    }
