"""Building blocks shared by standalone specialist runs and Nora's orchestration."""

import io
import json
import re
import secrets
import time
import zipfile
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
    """Products matching what the merchant wrote: an exact handle first (e.g. `bamboo-insulated-bottle` inside a
    sentence), then Shopify's text search; no query lists the first products."""
    user_id, org_id = owner(task)
    q = "query($q: String) { products(first: 10, query: $q) { nodes { id title handle onlineStoreUrl } } }"
    searches = [f"handle:{h}" for h in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)+", query.lower())] + [query]
    for search in searches if query else [None]:
        nodes = gateway("/v1/read/graphql", {"user_id": user_id, "org_id": org_id, "query": q,
                                             "variables": {"q": search}})["products"]["nodes"]
        if nodes:
            return nodes
    return []


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


ACCEPTED = ("text/markdown", "text/csv", "text/plain", "application/json", "application/zip", "application/pdf",
            "image/")  # what Sokosumi Task files accept (checked by type and by file extension)


def deliver_files(client: Sokosumi, task_id: str, manifest: dict, sent: list[str], save) -> None:
    """Upload each artifact once: `sent` is journaled (via `save`) so a retry does not upload duplicates."""
    for art in manifest["artifacts"]:
        if art["name"] in sent:
            continue
        data = httpx.get(art["url"], timeout=120).content
        name, mime = art["name"].replace("/", "-"), art["mime"]
        if not mime.startswith(ACCEPTED):  # e.g. .html emails, .ics calendars: delivered intact inside a zip
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr(name, data)
            data, name, mime = buf.getvalue(), f"{name}.zip", "application/zip"
        client.upload(task_id, name, data, mime)
        sent.append(art["name"])
        save()


def category_names(task: dict, changeset: list[dict]) -> dict[str, str]:
    """Readable names for the taxonomy categories and collections in a change set (approvals show names, not gids)."""
    ids = [op["fields"]["category"] for op in changeset if op["op"] == "product.update" and op["fields"].get("category")]
    ids += [op["collection_id"] for op in changeset if op["op"] == "collection.add_products"]
    if not ids:
        return {}
    user_id, org_id = owner(task)
    q = "query($ids: [ID!]!) { nodes(ids: $ids) { ... on TaxonomyCategory { id fullName } ... on Collection { id title } } }"
    nodes = gateway("/v1/read/graphql", {"user_id": user_id, "org_id": org_id, "query": q,
                                         "variables": {"ids": ids}})["nodes"]
    return {n["id"]: n.get("fullName") or n.get("title") for n in nodes if n}


def describe_changes(changeset: list[dict], snapshot_product: dict | None, names: dict[str, str] | None = None) -> str:
    """Plain-language list of changes for the approval comment."""
    lines = []
    for op in changeset:
        name = op["op"]
        if name == "product.update":
            for field, after in op["fields"].items():
                before = (snapshot_product or {}).get(field)
                if field == "category":
                    before = (before or {}).get("fullName") if isinstance(before, dict) else before
                    after = (names or {}).get(after, after)
                elif isinstance(after, dict):
                    after = " · ".join(f"{k}: {v}" for k, v in after.items())
                    before = " · ".join(f"{k}: {v}" for k, v in (before or {}).items()) if isinstance(before, dict) else before
                lines.append(f"- **{field}**: {_short(before)} → {_short(after)}")
        elif name in ("product.tags_add", "product.taxonomy_tags_add"):
            lines.append(f"- **tags**: add {', '.join(op['tags'])}")
        elif name == "metafields.set":
            lines.append(f"- **{', '.join(m['key'] for m in op['metafields'])}**: set")
        elif name == "collection.add_products":
            lines.append(f"- **collections**: add to “{(names or {}).get(op['collection_id'], op['collection_id'].split('/')[-1])}”")
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
            scope = "this product only" if op["input"]["customerGets"]["items"].get("products") else "store-wide"
            lines.append(f"- **discount code** {op['input']['code']}: "
                         f"{op['input']['customerGets']['value'].get('percentage', 0) * 100:.0f}% {scope} "
                         f"({op['input']['startsAt'][:10]} → {op['input'].get('endsAt', '')[:10]})")
        elif name == "article.create":
            lines.append(f"- **blog article** (unpublished): {op['input']['title']}")
    return "\n".join(lines)


def changes_md(changeset: list[dict]) -> bytes:
    """The exact change set, one section per operation (attached to the approval request)."""
    rows = "".join(f"## {i}. {op['op']}\n\n```json\n{json.dumps(op, indent=2, ensure_ascii=False)}\n```\n\n"
                   for i, op in enumerate(changeset, 1))
    return f"# Uplift changes\n\n{rows}".encode()


def _short(value: Any, n: int = 90) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or "—"))
    text = re.sub(r"\s+", " ", text).strip()
    return f"“{text[:n]}{'…' if len(text) > n else ''}”"
