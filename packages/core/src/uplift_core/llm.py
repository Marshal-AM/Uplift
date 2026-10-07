"""Amazon Bedrock over HTTPS with a Bedrock API key: Grok 4.7 for every text and image-input call, through the
bedrock-runtime OpenAI-compatible Chat Completions API (plain text, and schema-constrained JSON via a forced
function call). Fixed model, one region."""

import base64
import json
import os
import re
import time
from typing import Any

import httpx

from . import trace

REGION = "us-east-1"
LLM_MODEL = "us.xai.grok-4.7"
LLM_KEY_ENV = "BEDROCK_LLM_API_KEY"
URL = f"https://bedrock-runtime.{REGION}.amazonaws.com/openai/v1/chat/completions"
REASONING = "low"  # Grok's hidden reasoning counts against max_tokens; low keeps answers inside the budget
RETRYABLE = {429, 500, 502, 503, 504}


def purpose(prompt: str) -> str:
    """The prompt's first sentence: what this call is for, as the live trace shows it."""
    first = re.split(r"(?<=[.?!:])\s|\n", prompt.strip(), maxsplit=1)[0]
    return first if len(first) <= 140 else first[:139] + "…"


def _complete(body: dict[str, Any], prompt: str = "") -> dict[str, Any]:
    """POST a chat completion; retries throttling and transient errors with exponential backoff."""
    headers = {"Authorization": f"Bearer {os.environ[LLM_KEY_ENV]}"}
    images = sum(1 for m in body["messages"] for c in (m["content"] if isinstance(m["content"], list) else [])
                 if c.get("type") == "image_url")
    meta = {"model": LLM_MODEL, "reasoning": REASONING, "max_tokens": body.get("max_tokens"),
            "output": "structured (JSON schema)" if "tools" in body else "text", "prompt": prompt[:1200]}
    if images:
        meta["images"] = images
    with trace.span("Amazon Bedrock · Grok 4.7", purpose(prompt) or "Model call", "thinking…", kind="llm",
                    meta=meta) as s:
        retries = 0
        for attempt in range(5):
            try:
                resp = httpx.post(URL, json={"model": LLM_MODEL, "reasoning_effort": REASONING, **body},
                                  headers=headers, timeout=httpx.Timeout(300, connect=10))
            except httpx.TransportError:
                if attempt == 4:
                    raise
            else:
                if resp.status_code not in RETRYABLE or attempt == 4:
                    break
            retries += 1
            time.sleep(min(30, 2 ** attempt))
        if resp.status_code >= 400:
            raise RuntimeError(f"Bedrock chat completion → {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        usage = data.get("usage") or {}
        s.detail = (f"{usage.get('prompt_tokens', 0):,} tokens in → {usage.get('completion_tokens', 0):,} out"
                    + (f" · {images} image{'s' * (images > 1)}" if images else "")
                    + (f" · {retries} retr{'ies' if retries > 1 else 'y'} after throttling" if retries else ""))
        s.meta |= {"tokens_in": usage.get("prompt_tokens"), "tokens_out": usage.get("completion_tokens"),
                   "finish_reason": data["choices"][0].get("finish_reason")}
        return data["choices"][0]


def _messages(prompt: str, system: str, images: list[bytes] | None) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for raw in images or []:
        mime = "image/png" if raw[:4] == b"\x89PNG" else "image/jpeg" if raw[:2] == b"\xff\xd8" else "image/webp"
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{base64.b64encode(raw).decode()}"}})
    return ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]


def text(prompt: str, system: str = "", max_tokens: int = 4000, images: list[bytes] | None = None) -> str:
    choice = _complete({"messages": _messages(prompt, system, images), "max_tokens": max_tokens}, prompt)
    return choice["message"].get("content") or ""


def structured(
    prompt: str,
    schema: dict[str, Any],
    system: str = "",
    max_tokens: int = 4000,
    images: list[bytes] | None = None,
) -> dict[str, Any]:
    """Return JSON matching `schema` by forcing the model to call a single `respond` function. The model can omit a
    required field now and then; such an answer is requested again (up to 3 attempts in all)."""
    body = {
        "messages": _messages(prompt, system, images),
        "max_tokens": max_tokens,
        "tools": [{"type": "function", "function": {"name": "respond", "description": "Return the answer.",
                                                    "parameters": schema}}],
        "tool_choice": {"type": "function", "function": {"name": "respond"}},
    }
    for _ in range(3):
        choice = _complete(body, prompt)
        calls = choice["message"].get("tool_calls") or []
        if not calls:
            raise RuntimeError(f"model returned no structured output (finish_reason={choice.get('finish_reason')})")
        out = json.loads(calls[0]["function"]["arguments"])
        missing = [k for k in schema.get("required", []) if k not in out]
        if not missing:
            return out
    raise RuntimeError(f"model left out required fields {missing} three times")
