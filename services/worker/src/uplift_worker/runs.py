"""Building blocks shared by standalone specialist runs and Nora's orchestration."""

import html
import json
import re
import secrets
import time
from typing import Any

import boto3
import httpx
import jwt
from uplift_core.hashing import canonical, change_hash

from .clients import Sokosumi, gateway
from .config import settings

APPROVE = re.compile(r"^\s*(approve|approved|yes|go|ship it|lgtm)\b", re.IGNORECASE)


def owner(task: dict) -> tuple[str, str]:
    return task["ownerId"], task.get("organizationId") or ""


def read_token(task: dict) -> str:
    user_id, org_id = owner(task)
    return jwt.encode({"user_id": user_id, "org_id": org_id, "exp": int(time.time()) + 6 * 3600},
                      settings().read_capability_secret, algorithm="HS256")


def store_connected(task: dict) -> bool:
    user_id, org_id = owner(task)
    try:
        return gateway("/v1/read/status", {"user_id": user_id, "org_id": org_id})["connected"]
    except Exception:
        return False


def request_connection(client: Sokosumi, task: dict, reason: str) -> None:
    user_id, org_id = owner(task)
    state = jwt.encode({"task_id": task["id"], "user_id": user_id, "org_id": org_id, "coworker": client.role,
                        "nonce": secrets.token_hex(16), "exp": int(time.time()) + 24 * 3600},
                       settings().connect_state_secret, algorithm="HS256")
    client.event(task["id"], status="AUTHENTICATION_REQUIRED",
                 authenticationUrl=f"{settings().gateway_url}/connect/shopify/start?state={state}",
                 comment=f"{reason} Click **Authenticate** to connect your store — I'll continue automatically.")


def snapshot(task: dict, product_id: str) -> dict:
    user_id, org_id = owner(task)
    return gateway("/v1/read/snapshot", {"user_id": user_id, "org_id": org_id, "product_id": product_id})


def find_products(task: dict, query: str = "") -> list[dict]:
    user_id, org_id = owner(task)
    q = "query($q: String) { products(first: 10, query: $q) { nodes { id title handle onlineStoreUrl } } }"
    return gateway("/v1/read/graphql", {"user_id": user_id, "org_id": org_id, "query": q,
                                        "variables": {"q": query or None}})["products"]["nodes"]


def user_replies(client: Sokosumi, task_id: str, after_event_id: str | None) -> list[dict]:
    """User-authored events after `after_event_id` (status moves and comments), oldest first."""
    events = client.task_events(task_id)
    if after_event_id:
        ids = [e["id"] for e in events]
        events = events[ids.index(after_event_id) + 1:] if after_event_id in ids else events
    return [e for e in events if (e.get("actor") or {}).get("type") == "user"]


def approval_event(replies: list[dict]) -> dict | None | bool:
    """The approving event (Ready/Running or 'approve'), False on another comment first, None while waiting."""
    for e in replies:
        if e.get("status") in ("READY", "RUNNING") or APPROVE.match(e.get("comment") or ""):
            return e
        if e.get("comment"):
            return False
    return None


def latest_comment(replies: list[dict]) -> str:
    return next((e["comment"] for e in reversed(replies) if e.get("comment")), "")


def _s3():
    return boto3.client("s3", region_name=settings().aws_region)


def manifest_from_store(result_hash: str) -> dict:
    body = _s3().get_object(Bucket=settings().artifact_bucket, Key=f"artifacts/{result_hash}/manifest.json")["Body"]
    return json.loads(body.read())


def manifest_ref(result_hash: str) -> dict:
    """What CRE needs to fetch a deliverable itself: its hash and a short-lived URL (the hash makes it trustless)."""
    url = _s3().generate_presigned_url("get_object", ExpiresIn=3600, Params={
        "Bucket": settings().artifact_bucket, "Key": f"artifacts/{result_hash}/manifest.json"})
    return {"hash": result_hash, "url": url}


def changeset_url(changeset: list[dict]) -> str:
    """Store the exact canonical change set the merchant approved, addressed by its change hash."""
    key = f"artifacts/{change_hash(changeset)}/changeset.json"
    _s3().put_object(Bucket=settings().artifact_bucket, Key=key, Body=canonical(changeset).encode(),
                     ContentType="application/json")
    return _s3().generate_presigned_url("get_object", ExpiresIn=3600,
                                        Params={"Bucket": settings().artifact_bucket, "Key": key})


def deliver_files(client: Sokosumi, task_id: str, manifest: dict, prefix: str = "") -> None:
    for art in manifest["artifacts"]:
        data = httpx.get(art["url"], timeout=120).content
        client.upload(task_id, f"{prefix}{art['name'].replace('/', '-')}", data, art["mime"])


def describe_changes(changeset: list[dict], snapshot_product: dict | None) -> str:
    """Plain-language list of changes for the approval comment."""
    lines = []
    for op in changeset:
        name = op["op"]
        if name == "product.update":
            for field, after in op["fields"].items():
                before = (snapshot_product or {}).get(field)
                if isinstance(after, dict):
                    after = " · ".join(f"{k}: {v}" for k, v in after.items())
                    before = " · ".join(f"{k}: {v}" for k, v in (before or {}).items()) if isinstance(before, dict) else before
                lines.append(f"- **{field}**: {_short(before)} → {_short(after)}")
        elif name in ("product.tags_add", "product.taxonomy_tags_add"):
            lines.append(f"- **tags**: add {', '.join(op['tags'])}")
        elif name == "metafields.set":
            lines.append(f"- **{', '.join(m['key'] for m in op['metafields'])}**: set")
        elif name == "collection.add_products":
            lines.append(f"- **collections**: add to {op['collection_id'].split('/')[-1]}")
        elif name == "collection.create":
            lines.append(f"- **new collection**: {op['input']['title']}")
        elif name == "media.add":
            lines.append(f"- **images**: add {len(op['media'])}")
        elif name == "media.update_alt":
            lines.append(f"- **alt text**: update {len(op['files'])} images")
        elif name == "media.reorder":
            lines.append("- **images**: reorder")
        elif name == "translations.register":
            lines.append(f"- **translation {op['translations'][0]['locale'] if op['translations'] else ''}**: "
                         f"{len(op['translations'])} fields")
        elif name == "discount.create":
            lines.append(f"- **discount code** {op['input']['code']}: "
                         f"{op['input']['customerGets']['value'].get('percentage', 0) * 100:.0f}% "
                         f"({op['input']['startsAt'][:10]} → {op['input'].get('endsAt', '')[:10]})")
        elif name == "article.create":
            lines.append(f"- **blog article** (unpublished): {op['input']['title']}")
    return "\n".join(lines)


def changes_html(changeset: list[dict]) -> bytes:
    rows = "".join(f"<h3>{html.escape(op['op'])}</h3><pre>{html.escape(json.dumps(op, indent=2, ensure_ascii=False))}</pre>"
                   for op in changeset)
    return f"<!doctype html><meta charset=utf-8><title>Uplift changes</title><body>{rows}</body>".encode()


def _short(value: Any, n: int = 90) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or "—"))
    text = re.sub(r"\s+", " ", text).strip()
    return f"“{text[:n]}{'…' if len(text) > n else ''}”"
