"""
translate.py — language translation adapter for GeoLens AI.

The planner always works in English. This adapter translates user input
to English before planning, and shows the English interpretation as plan chips.

Implementation: Sarvam AI translation endpoint.
  Key: SARVAM_API_KEY environment variable.

TODO [UNVERIFIED]: The Sarvam AI translate endpoint URL and request schema
could not be verified at design time. The passthrough fallback is always
used until this is confirmed. Replace the stub body of _call_sarvam() once
the endpoint is confirmed.

See design.md §7 (Adapters) for the full contract.
"""

from __future__ import annotations

import os
import warnings
from typing import Optional

SARVAM_API_KEY: Optional[str] = os.environ.get("SARVAM_API_KEY")

# TODO: verify Sarvam AI endpoint URL and request/response schema
# The URL below is a placeholder and must be confirmed against official Sarvam AI docs
# before this code is activated in production.
_SARVAM_ENDPOINT = "https://api.sarvam.ai/translate"  # TODO: UNVERIFIED


def _call_sarvam(text: str, source_language_code: str, target_language_code: str) -> str:
    """
    Call the Sarvam AI translate API.

    TODO [UNVERIFIED]: This function body is a stub.
    The endpoint URL, request body schema, and response format below are
    placeholders based on common translate API patterns. They must be confirmed
    against the official Sarvam AI documentation before this is used in production.

    Until confirmed, this function always raises NotImplementedError and the
    caller falls back to passthrough.
    """
    # TODO: Replace this entire body once the Sarvam AI endpoint is confirmed.
    raise NotImplementedError(
        "Sarvam AI translate endpoint not yet verified. "
        "See translate.py TODO. Using passthrough fallback."
    )

    # --- Placeholder implementation (do not activate until endpoint is confirmed) ---
    # import requests
    # headers = {
    #     "Authorization": f"Bearer {SARVAM_API_KEY}",
    #     "Content-Type": "application/json",
    # }
    # payload = {
    #     "input": text,
    #     "source_language_code": source_language_code,
    #     "target_language_code": target_language_code,
    # }
    # response = requests.post(_SARVAM_ENDPOINT, json=payload, headers=headers, timeout=10)
    # response.raise_for_status()
    # return response.json()["output"]


def translate(text: str, from_lang: str, to_lang: str) -> str:
    """
    Translate text from from_lang to to_lang.

    Language codes follow BCP-47 (e.g. "en-IN", "hi-IN", "pt-BR").
    If from_lang == to_lang, returns text unchanged.

    Falls back to passthrough (returns text as-is) when:
    - SARVAM_API_KEY is not set
    - The Sarvam AI endpoint is not yet verified (current state)
    - Any API error occurs

    Planner always receives and returns English.
    Frontend shows the English interpretation as plan chips regardless of input language.

    Parameters
    ----------
    text      : input text
    from_lang : source language code (e.g. "hi-IN" for Hindi)
    to_lang   : target language code (e.g. "en-IN" for English)

    Returns
    -------
    Translated string, or original text if translation unavailable.
    """
    if from_lang == to_lang:
        return text

    if not SARVAM_API_KEY:
        warnings.warn(
            "SARVAM_API_KEY not set — using passthrough (no translation). "
            "Set SARVAM_API_KEY to enable Sarvam AI translation.",
            UserWarning,
            stacklevel=2,
        )
        return text

    try:
        return _call_sarvam(text, from_lang, to_lang)
    except NotImplementedError as e:
        warnings.warn(str(e), UserWarning, stacklevel=2)
        return text
    except Exception as e:
        warnings.warn(
            f"Sarvam AI translation failed ({e}); using passthrough.",
            UserWarning,
            stacklevel=2,
        )
        return text


def detect_language(text: str) -> str:
    """
    Detect the language of the input text.

    Currently returns "en-IN" (English) always — a passthrough.
    TODO: Implement real language detection if Sarvam AI offers it,
    or use langdetect as a lightweight local option.

    Returns BCP-47 language code.
    """
    # TODO: implement real language detection
    return "en-IN"
