"""Amazon Bedrock over HTTPS with a Bedrock API key: Grok 4.7 for every text and image-input call, through the
bedrock-runtime OpenAI-compatible Chat Completions API (plain text, and schema-constrained JSON via a forced
function call). Fixed model, one region."""

import base64
import json
import os
import re
from typing import Any

from . import resilience, trace

REGION = "us-east-1"
LLM_MODEL = "us.xai.grok-4.7"
LLM_KEY_ENV = "BEDROCK_LLM_API_KEY"
URL = f"https://bedrock-runtime.{REGION}.amazonaws.com/openai/v1/chat/completions"
REASONING = "low"  # Grok's hidden reasoning counts against max_tokens; low keeps answers inside the budget
POLICY = resilience.Policy("Amazon Bedrock · Grok 4.7", attempt_timeout=300, attempts=3)


def purpose(prompt: str) -> str:
    """The prompt's first sentence: what this call is for, as the live trace shows it."""
    first = re.split(r"(?<=[.?!:])\s|\n", prompt.strip(), maxsplit=1)[0]
    return first if len(first) <= 140 else first[:139] + "…"


def deadline(max_tokens: int, images: int = 0) -> float:
    """Seconds one attempt may take: room for the whole output at a slow 25 tokens/s (Grok on Bedrock answered at
    63–73 tokens/s in our runs) plus 30 s for the request and hidden reasoning, 15 s per image; 45–300 s."""
    return max(45.0, min(300.0, 30 + max_tokens / 25 + 15 * images))


def _complete(body: dict[str, Any], prompt: str = "", label: str | None = None) -> dict[str, Any]:
    """POST a chat completion under a deadline sized to the call, with bounded retries (see resilience.py): a hung
    or throttled request is retried, and the whole call gives up within its budget instead of hanging."""
    headers = {"Authorization": f"Bearer {os.environ[LLM_KEY_ENV]}"}
    images = sum(1 for m in body["messages"] for c in (m["content"] if isinstance(m["content"], list) else [])
                 if c.get("type") == "image_url")
    attempt_s = deadline(body.get("max_tokens") or 4000, images)
    policy = POLICY.with_timeout(attempt_s, budget=2.2 * attempt_s + 40)  # two full attempts and a short third
    meta = {"model": LLM_MODEL, "reasoning": REASONING, "max_tokens": body.get("max_tokens"),
            "output": "structured (JSON schema)" if "tools" in body else "text",
            "attempt limit": f"{attempt_s:.0f} s", "prompt": prompt[:1200]}
    if images:
        meta["images"] = images
    with trace.span("Amazon Bedrock · Grok 4.7", label or purpose(prompt) or "Model call", "thinking…", kind="llm",
                    meta=meta) as s:
        resp = resilience.request("POST", URL, policy, headers=headers,
                                  json={"model": LLM_MODEL, "reasoning_effort": REASONING, **body})
        if resp.status_code >= 400:
            raise RuntimeError(f"Bedrock chat completion → {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        usage = data.get("usage") or {}
        s.detail = (f"{usage.get('prompt_tokens', 0):,} tokens in → {usage.get('completion_tokens', 0):,} out"
                    + (f" · {images} image{'s' * (images > 1)}" if images else ""))
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


def text(prompt: str, system: str = "", max_tokens: int = 4000, images: list[bytes] | None = None,
         purpose: str | None = None) -> str:
    """`purpose`: how the live trace names this call (default: the prompt's first sentence)."""
    choice = _complete({"messages": _messages(prompt, system, images), "max_tokens": max_tokens}, prompt, purpose)
    return choice["message"].get("content") or ""


def structured(
    prompt: str,
    schema: dict[str, Any],
    system: str = "",
    max_tokens: int = 4000,
    images: list[bytes] | None = None,
    purpose: str | None = None,
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
        choice = _complete(body, prompt, purpose)
        calls = choice["message"].get("tool_calls") or []
        if not calls:
            raise RuntimeError(f"model returned no structured output (finish_reason={choice.get('finish_reason')})")
        out = json.loads(calls[0]["function"]["arguments"])
        missing = [k for k in schema.get("required", []) if k not in out]
        if not missing:
            return out
    raise RuntimeError(f"model left out required fields {missing} three times")
