"""
Find a working free model for this OpenRouter key by trying candidates in order.
Never logs the API key.
"""
from dotenv import load_dotenv
load_dotenv()

import os, requests

api_key  = os.environ.get("OPENROUTER_API_KEY", "")
base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/geolens-ai",
    "X-Title": "GeoLens AI",
}

# Well-known free / low-cost models on OpenRouter (as of 2025/2026)
CANDIDATES = [
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-flash-1.5",
    "google/gemini-flash-1.5:free",
    "google/gemini-pro",
    "meta-llama/llama-3.1-8b-instruct:free",
    "meta-llama/llama-3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "mistralai/mistral-7b-instruct-v0.2",
    "openai/gpt-4o-mini",
    "anthropic/claude-3-haiku",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "deepseek/deepseek-chat:free",
]

print(f"Testing {len(CANDIDATES)} model candidates against {base_url} ...\n")

working = []
for model in CANDIDATES:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "pong"}],
        "max_tokens": 5,
        "temperature": 0.0,
    }
    try:
        r = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=20)
        status = r.status_code
        if status == 200:
            actual = r.json().get("model", model)
            print(f"  OK  {model} (served as {actual})")
            working.append(model)
        elif status == 404:
            print(f"  404 {model}")
        elif status == 401:
            print(f"  401 {model}  — bad key, stopping")
            break
        elif status == 429:
            print(f"  429 {model}  — rate limited, skipping")
        else:
            body = r.text[:120]
            print(f"  {status} {model}  — {body}")
    except Exception as exc:
        print(f"  ERR {model}  — {exc}")

print()
if working:
    print(f"Recommended OPENROUTER_MODEL={working[0]}")
else:
    print("No working model found — check key permissions or account credits.")
