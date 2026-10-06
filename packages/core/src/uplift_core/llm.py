"""Amazon Bedrock: Converse (plain text, schema-constrained JSON via forced tool use) and image models."""

import base64
import json
import os
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

# One model for text and image inputs, one region. Auth: the Bedrock API key in AWS_BEARER_TOKEN_BEDROCK.
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.xai.grok-4.7")
REGION = os.environ.get("AWS_REGION", "us-east-1")


@lru_cache
def _client():
    return boto3.client(
        "bedrock-runtime",
        region_name=REGION,
        config=Config(retries={"max_attempts": 5, "mode": "adaptive"}, read_timeout=300),
    )


def _content(prompt: str, images: list[bytes] | None, documents: list[tuple[str, bytes]] | None) -> list:
    blocks: list[dict[str, Any]] = [{"text": prompt}]
    for raw in images or []:
        fmt = "png" if raw[:4] == b"\x89PNG" else "jpeg" if raw[:2] == b"\xff\xd8" else "webp"
        blocks.append({"image": {"format": fmt, "source": {"bytes": raw}}})
    for i, (fmt, raw) in enumerate(documents or []):
        blocks.append({"document": {"format": fmt, "name": f"doc{i}", "source": {"bytes": raw}}})
    return blocks


def text(prompt: str, system: str = "", max_tokens: int = 4000, images: list[bytes] | None = None) -> str:
    resp = _client().converse(
        modelId=MODEL_ID,
        system=[{"text": system}] if system else [],
        messages=[{"role": "user", "content": _content(prompt, images, None)}],
        inferenceConfig={"maxTokens": max_tokens},
    )
    return "".join(b.get("text", "") for b in resp["output"]["message"]["content"])


def structured(
    prompt: str,
    schema: dict[str, Any],
    system: str = "",
    max_tokens: int = 4000,
    images: list[bytes] | None = None,
    documents: list[tuple[str, bytes]] | None = None,
) -> dict[str, Any]:
    """Return JSON matching `schema` by forcing the model to call a single `respond` tool."""
    resp = _client().converse(
        modelId=MODEL_ID,
        system=[{"text": system}] if system else [],
        messages=[{"role": "user", "content": _content(prompt, images, documents)}],
        inferenceConfig={"maxTokens": max_tokens},
        toolConfig={
            "tools": [{"toolSpec": {"name": "respond", "description": "Return the answer.",
                                    "inputSchema": {"json": schema}}}],
            "toolChoice": {"tool": {"name": "respond"}},
        },
    )
    for block in resp["output"]["message"]["content"]:
        if "toolUse" in block:
            return block["toolUse"]["input"]
    raise RuntimeError("model returned no structured output")


def image(model: str, body: dict[str, Any]) -> bytes:
    """Stability AI Image Services on Bedrock (InvokeModel). Returns the first image's bytes."""
    out = json.loads(_client().invoke_model(modelId=model, body=json.dumps(body))["body"].read())
    reason = (out.get("finish_reasons") or [None])[0]
    if reason:
        raise RuntimeError(f"{model}: {reason}")
    return base64.b64decode(out["images"][0])
