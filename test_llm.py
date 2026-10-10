"""
Quick LLM probe — tests model availability, logs status/fallback, never logs keys.
Run: python test_llm.py
"""
from dotenv import load_dotenv
load_dotenv()

import os, json, sys
import requests

model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
api_key = os.environ.get("OPENROUTER_API_KEY", "")

print(f"Provider : openrouter")
print(f"Base URL : {base_url}")
print(f"Model    : {model}")
print(f"API key  : {'set' if api_key else 'NOT SET'}")
print()

if not api_key:
    print("FAIL: OPENROUTER_API_KEY not set — cannot test LLM.")
    sys.exit(1)

# Minimal chat completions request (no structured output, just check reachability)
payload = {
    "model": model,
    "messages": [
        {"role": "user", "content": "Reply with the single word: pong"}
    ],
    "max_tokens": 10,
    "temperature": 0.0,
}
headers = {
    "Authorization": f"Bearer {api_key}",  # key never printed
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/geolens-ai",
    "X-Title": "GeoLens AI",
}

print(f"POST {base_url}/chat/completions  model={model}")
try:
    resp = requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers=headers,
        timeout=30,
    )
    print(f"HTTP status : {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        actual_model = data.get("model", "unknown")
        print(f"Model used  : {actual_model}")
        print(f"Response    : {content!r}")
        print()
        print("PASS: LLM reachable, no fallback needed.")
    elif resp.status_code == 404:
        print(f"FAIL: HTTP 404 — model '{model}' not found on OpenRouter.")
        print(f"Response body: {resp.text[:300]}")
        print()
        print("ACTION: Change OPENROUTER_MODEL to a valid model slug.")
        print("        Free models: https://openrouter.ai/models?order=newest&max_price=0")
    elif resp.status_code == 401:
        print(f"FAIL: HTTP 401 — API key rejected.")
        print(f"Response body: {resp.text[:300]}")
    else:
        print(f"FAIL: HTTP {resp.status_code}")
        print(f"Response body: {resp.text[:300]}")

except requests.RequestException as exc:
    print(f"FAIL: Network error — {exc}")
