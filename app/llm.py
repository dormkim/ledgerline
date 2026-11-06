"""OpenAI-compatible chat client. Default endpoint is Vultr Serverless Inference.

Returns (data, meta). On any failure data is None and meta['error'] says why — callers fall back to
code-written text and show that they did. The API key is never logged, returned or stored.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "https://api.vultrinference.com/v1"


def config() -> dict:
    key = os.environ.get("LLM_API_KEY") or os.environ.get("VULTR_INFERENCE_API_KEY") or ""
    base = (os.environ.get("LLM_BASE_URL") or DEFAULT_BASE).rstrip("/")
    model = os.environ.get("LLM_MODEL", "")
    off = os.environ.get("LLM_DISABLED", "").lower() in {"1", "true", "yes"}
    return {"key": key, "base": base, "model": model, "off": off}


def public_status() -> dict:
    c = config()
    host = re.sub(r"^https?://", "", c["base"]).split("/")[0]
    if c["off"]:
        state = "disabled"
    elif not c["key"] or not c["model"]:
        state = "not configured"
    else:
        state = "configured"
    return {"state": state, "endpoint_host": host, "model": c["model"] or None,
            "vultr_inference": host.endswith("vultrinference.com")}


def chat_json(system: str, user: str, max_tokens: int = 1500, timeout: float = 45.0) -> tuple[dict | None, dict]:
    c = config()
    meta = {"model": c["model"], "ms": 0, "error": None}
    if c["off"] or not c["key"] or not c["model"]:
        meta["error"] = "LLM " + ("disabled" if c["off"] else "not configured")
        return None, meta
    body = {"model": c["model"], "max_tokens": max_tokens, "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(c["base"] + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {c['key']}", "Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode())
        text = payload["choices"][0]["message"]["content"] or ""
    except urllib.error.HTTPError as e:
        meta["error"] = f"HTTP {e.code} from LLM endpoint"
        return None, _done(meta, t0)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        meta["error"] = f"LLM endpoint unreachable ({type(e).__name__})"
        return None, _done(meta, t0)
    except (KeyError, IndexError, json.JSONDecodeError):
        meta["error"] = "LLM reply had no message content"
        return None, _done(meta, t0)
    data = parse_json(text)
    if data is None:
        meta["error"] = "LLM reply was not valid JSON"
    return data, _done(meta, t0)


def _done(meta: dict, t0: float) -> dict:
    meta["ms"] = round((time.perf_counter() - t0) * 1000)
    return meta


def parse_json(text: str) -> dict | None:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()  # reasoning models
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
