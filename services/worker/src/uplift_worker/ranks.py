"""Store-search rank of a Task's product when the run starts and after it ends (the /live rank card).

The same check as e2e/rank.py and Quinn: Shopify Admin `products(query:, sortKey: RELEVANCE)`, top 50, read through
the Uplift gateway with the store's own Shopify access token. It runs on a background thread and is best-effort:
it never holds up or fails a Task.

- start: as soon as the run knows its product. Phrases: the ones the merchant listed in the brief, else five
  generic shopper phrases for this kind of product (chosen once, reused at the end).
- end: 30 s after the Task completes, and once more at 3 min (Shopify's search index can lag a publish).
"""

import json
import logging
import threading
import time
from typing import Any

from uplift_core import llm, trace

from . import db, runs
from .clients import gateway
from .config import settings

log = logging.getLogger("uplift.worker")
TOP = 50
END_CHECKS_S = (30, 180)  # after completion: first look, then once Shopify's search index has settled
RANK_QUERY = (f"query Rank($q: String!) {{ products(first: {TOP}, query: $q, sortKey: RELEVANCE) "
              "{ nodes { handle title } } }")
FIELDS = """id legacyResourceId handle title status vendor productType tags onlineStoreUrl
  category { fullName } seo { title description } media(first: 50) { nodes { id } }
  priceRangeV2 { minVariantPrice { amount currencyCode } maxVariantPrice { amount } }
  variants(first: 10) { nodes { sku price inventoryItem { unitCost { amount } } } }
  collections(first: 10) { nodes { title } }"""
MINIMAL = "id legacyResourceId handle title status vendor productType tags onlineStoreUrl"


def _read(task: dict, query: str, variables: dict | None = None) -> dict:
    user_id, org_id = runs.owner(task)
    return gateway("/v1/read/graphql", {"user_id": user_id, "org_id": org_id, "query": query,
                                        "variables": variables or {}})


def _details(task: dict, product_id: str) -> tuple[dict, str]:
    """The product as rank.py shows it, and the store's myshopify domain. Falls back to fewer fields if the
    connection's scopes do not cover one of them."""
    for fields in (FIELDS, MINIMAL):
        try:
            data = _read(task, f"query($id: ID!) {{ shop {{ myshopifyDomain }} product(id: $id) {{ {fields} }} }}",
                         {"id": product_id})
            return data["product"], data["shop"]["myshopifyDomain"]
        except Exception:
            if fields == MINIMAL:
                raise
    raise RuntimeError("unreachable")


def _phrases(task: dict, product: dict) -> list[str]:
    out = llm.structured(
        f"A merchant's Task brief:\n{task.get('name')}\n{task.get('description')}\n\n"
        f"Product: {product.get('title')} ({product.get('productType') or 'no type'})\n"
        "Return the store-search phrases to track this product's rank for. If the brief lists search phrases or "
        "keywords to rank or track, return exactly those (up to 8). Otherwise return 5 generic phrases (2–4 words, "
        "lowercase) a shopper would type into this store's search to find this kind of product: no brand names, no "
        "model codes, and not the product's full title.",
        {"type": "object", "properties": {"phrases": {"type": "array", "items": {"type": "string"}}},
         "required": ["phrases"]}, max_tokens=600, purpose="Choosing the shopper search phrases to track")
    seen: list[str] = []
    for p in out["phrases"]:
        p = p.strip().strip('"')
        if p and p.lower() not in (s.lower() for s in seen):
            seen.append(p)
    return seen[:8]


def _ranks(task: dict, handle: str, phrases: list[str]) -> list[dict]:
    rows = []
    for phrase in phrases:
        nodes = _read(task, RANK_QUERY, {"q": phrase})["products"]["nodes"]
        handles = [n["handle"] for n in nodes]
        pos = handles.index(handle) + 1 if handle in handles else None
        rows.append({"phrase": phrase, "rank": pos, "results": len(nodes),
                     "ahead": [n["title"] for n in nodes[: (pos or len(nodes) + 1) - 1]][:2]})
    return rows


def capture(task: dict, role: str, product_id: str, stage: str) -> dict:
    """Check and store the ranks for one stage ("start" or "end")."""
    label = "at the start of the run" if stage == "start" else "after the run"
    with trace.span("Shopify", f"Checking store-search rank {label}", "Admin API products search, sorted by relevance",
                    task=task["id"], agent=role, kind=f"rank.{stage}") as s:
        product, shop = _details(task, product_id)
        start = db.one("select data->'phrases' as phrases from rank_checks where task_id = %s and stage = 'start'",
                       task["id"])
        phrases = start["phrases"] if start else _phrases(task, product)
        rows = _ranks(task, product["handle"], phrases)
        endpoint = f"POST https://{shop}/admin/api/{settings().shopify_api_version}/graphql.json"
        record = {"product": product, "phrases": phrases, "ranks": rows, "endpoint": endpoint,
                  "query": RANK_QUERY, "shop": shop}
        db.execute(
            """insert into rank_checks (task_id, stage, checked_at, data) values (%s, %s, now(), %s)
               on conflict (task_id, stage) do update set checked_at = now(), data = excluded.data""",
            task["id"], stage, json.dumps(record))
        found, top = sum(1 for r in rows if r["rank"]), sum(1 for r in rows if r["rank"] == 1)
        s.detail = f"{found}/{len(rows)} phrases find it · #1 for {top} · {product['handle']}"
        s.meta |= {"endpoint": endpoint, "phrases": phrases}
    return record


def _safely(fn, *args) -> None:
    try:
        fn(*args)
    except Exception:
        log.exception("rank check failed (the Task is unaffected)")


def _end(task: dict, role: str, product_id: str) -> None:
    waited = 0
    for at in END_CHECKS_S:
        time.sleep(at - waited)
        waited = at
        _safely(capture, task, role, product_id, "end")


def track(task: dict, role: str, st: dict[str, Any], phase: str) -> None:
    """Called on every journal save: start the rank check once the run has a product, and the end check once it
    completes. Flags live in the run state, so a resumed run does not check twice. Never raises."""
    try:
        product_id = st.get("product_id")
        if not product_id:
            return
        if not st.get("rank_start"):
            st["rank_start"] = time.time()
            threading.Thread(target=_safely, args=(capture, task, role, product_id, "start"), daemon=True).start()
        if phase == "done" and not st.get("rank_end"):
            st["rank_end"] = time.time()
            threading.Thread(target=_end, args=(task, role, product_id), daemon=True).start()
    except Exception:
        log.exception("rank tracking skipped")
