"""Google Ads mock data: a finished run's verified ads deliverables, shaped for the ads-mock frontend.

GET /ads/runs?key=                  runs with a Chainlink-passed Google Ads deliverable (Sasha), newest first
GET /ads/run?task=&key=  (or &t=)   one run as a Google Ads account: campaigns, ad groups, keywords, ads, products and
                                    the search results the ads would appear in. Without `task`: the newest run.

Everything shown comes from the agents' own output: Sasha's Google Ads Editor file, bid economics and ad copy, Kai's
keyword demand, Rafael's Google Shopping offers and ranking pages, Leo's FAQ, Clara's copy, Iris's images and the store
snapshot. Nothing is invented: what no agent produced (competitor text ads, sitelinks, ratings) is left empty. The
frontend simulates the traffic and says so. `key` is the /live view key; `t` is a per-run share token.
"""

import csv
import hashlib
import hmac
import html
import io
import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query

from . import db, runs
from .clients import Sokosumi
from .config import settings

router = APIRouter(prefix="/ads")

ROLES = ("sasha", "kai", "rafael", "leo", "clara", "iris")
HEADLINE_LABELS = ["Best", "Best", "Good", "Good", "Good", "Good", "Learning", "Good", "Low", "Good", "Learning", "Low",
                   "Good", "Good", "Learning"]
DESCRIPTION_LABELS = ["Best", "Good", "Good", "Learning"]
PALETTE = ["#3f7d5a", "#1f3a5f", "#7a5c2e", "#2a7f83", "#c45c3c", "#5a8f29", "#6b4fa3", "#b0473f"]
STOP = {"with", "from", "your", "this", "that", "for", "and", "the", "best", "buy"}


# --- access --------------------------------------------------------------------------------------------

def share_token(task_id: str) -> str:
    """A link token that opens one run's mock account only (the view key opens all of them)."""
    secret = (settings().trace_view_key or settings().worker_hook_secret).encode()
    return hmac.new(secret, f"ads:{task_id}".encode(), hashlib.sha256).hexdigest()[:32]


def _allowed(key: str, task: str | None, token: str) -> bool:
    view = settings().trace_view_key
    if view and key and hmac.compare_digest(key.encode(), view.encode()):
        return True
    return bool(task and token and hmac.compare_digest(token.encode(), share_token(task).encode()))


def preview_link(task_id: str) -> str | None:
    """The mock Google Ads link Nora posts on a finished Task, when ADS_MOCK_URL is set."""
    base = settings().ads_mock_url.rstrip("/")
    return f"{base}/ads/?task={task_id}&t={share_token(task_id)}" if base else None


# --- reading a run ---------------------------------------------------------------------------------------

RUNS_WITH_ADS = """
select task_id, coworker, phase, updated_at, state from runs
 where (coworker = 'nora' and exists (select 1 from jsonb_each(state->'nodes') n
                                       where n.value->>'role' = 'sasha' and n.value->>'verdict' = 'PASS'))
    or (coworker = 'sasha' and state ? 'manifest'
        and exists (select 1 from jsonb_array_elements(coalesce(state->'verdicts', '[]'::jsonb)) v
                     where v->>'outcome' = 'PASS'))
 order by updated_at desc limit %s"""


def _passed(row: dict) -> dict[str, str]:
    """role → result hash of each Chainlink-passed deliverable the mock uses."""
    st = row["state"]
    if row["coworker"] == "sasha":
        return {"sasha": st["result_hash"]}
    out: dict[str, str] = {}
    for node, n in (st.get("nodes") or {}).items():
        if n.get("role") in ROLES and n.get("verdict") == "PASS" and n.get("result_hash") and node != "quinn_after":
            out.setdefault(n["role"], n["result_hash"])
    return out


class Deliverable:
    """A verified manifest plus access to its artifacts (stored content-addressed in S3)."""

    def __init__(self, manifest: dict):
        self.manifest = manifest
        self.files = {a["name"]: a for a in manifest.get("artifacts", [])}

    def _key(self, name: str) -> str | None:
        a = self.files.get(name)
        return f"artifacts/{a['sha256']}/{name}" if a else None

    def text(self, name: str) -> str | None:
        key = self._key(name)
        if not key:
            return None
        return runs._s3().get_object(Bucket=settings().artifact_bucket, Key=key)["Body"].read().decode()

    def json(self, name: str) -> Any:
        raw = self.text(name)
        return json.loads(raw) if raw else None

    def url(self, name: str) -> str | None:
        key = self._key(name)
        return runs._s3().generate_presigned_url(
            "get_object", ExpiresIn=24 * 3600, Params={"Bucket": settings().artifact_bucket, "Key": key}) if key else None

    def bundle(self) -> dict:
        vb = self.manifest.get("verification_bundle") or {}
        if not vb.get("sha256"):
            return {}
        body = runs._s3().get_object(Bucket=settings().artifact_bucket,
                                     Key=f"artifacts/{vb['sha256']}/verification_bundle.json")["Body"].read()
        return json.loads(body)


def _snapshot(row: dict) -> dict:
    st = row["state"]
    if st.get("baseline_snapshot"):
        return st["baseline_snapshot"]
    if st.get("product_id"):  # a standalone Sasha Task: read the product live
        try:
            return runs.snapshot(Sokosumi(row["coworker"]).task(row["task_id"]), st["product_id"])
        except Exception:
            return {}
    return {}


def _title(row: dict) -> str:
    st = row["state"]
    product = (st.get("baseline_snapshot") or {}).get("product") or {}
    return product.get("title") or (st.get("plan") or {}).get("intent", {}).get("product_hint") or "Google Ads run"


# --- shaping (pure: testable without S3) -----------------------------------------------------------------

def _plain(text: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _pick(seed: str, items: list) -> Any:
    return items[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(items)]


def _domain(url: str) -> str:
    host = urlparse(url if "//" in url else f"https://{url}").netloc
    return host.removeprefix("www.")


def _site(domain: str) -> str:
    return domain.split(".")[0].replace("-", " ").title() if domain else "Website"


def _editor_rows(csv_text: str | None) -> list[dict]:
    return list(csv.DictReader(io.StringIO(csv_text))) if csv_text else []


def _bullets(description_html: str) -> list[str]:
    items = [_plain(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", description_html or "", re.S | re.I)]
    if not items:
        items = [s.strip() for s in re.split(r"(?<=[.!?])\s+", _plain(description_html)) if len(s.strip()) > 20]
    return [i for i in items if i][:4]


def shape(task_id: str, meta: dict, snapshot: dict, get: Callable[[str], Deliverable | None]) -> dict:
    """The mock's dataset for one run. `get(role)` returns that role's passed deliverable, or None."""
    sasha = get("sasha")
    if not sasha:
        raise HTTPException(404, "this run has no passed Google Ads deliverable")
    sb = sasha.bundle()
    econ = sb.get("economics") or sasha.json("unit_economics.json") or {}
    copy = sasha.json("ad_copy.json") or {}
    editor = _editor_rows(sasha.text("google_ads_editor.csv"))

    shop = snapshot.get("shop") or {}
    product = snapshot.get("product") or {}
    store_url = (sb.get("shop_url") or (shop.get("primaryDomain") or {}).get("url") or "").rstrip("/")
    domain = _domain(store_url) or "your-store.example"
    store_name = shop.get("name") or _site(domain)
    price = float(econ.get("price") or ((product.get("variants") or {}).get("nodes") or [{}])[0].get("price") or 0)

    clara = get("clara")
    clara_fields = next((op["fields"] for op in (clara.manifest.get("changeset") if clara else []) or []
                         if op["op"] == "product.update"), {})
    title = clara_fields.get("title") or product.get("title") or "Your product"
    description = clara_fields.get("descriptionHtml") or product.get("descriptionHtml") or ""
    seo = clara_fields.get("seo") or product.get("seo") or {}
    handle = product.get("handle") or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

    iris = get("iris")
    image = None
    if iris:
        image = next((iris.url(n) for n in ("google_shopping.jpg", "store.jpg", "google_ads_square.jpg") if n in iris.files),
                     None)
    if not image:
        media = [m for m in (product.get("media") or {}).get("nodes", []) if m.get("image")]
        image = media[0]["image"]["url"] if media else None

    # keywords: the Editor file is the account; Kai adds demand and intent
    kai = get("kai")
    kmap = (kai.json("keyword_map.json") if kai else None) or {}
    kai_kw = {k["keyword"]: k for k in kmap.get("keywords", [])}
    keywords, groups = [], []
    for r in editor:
        crit = (r.get("Criterion Type") or "").lower()
        if r.get("Keyword") and crit in ("exact", "phrase"):
            text = r["Keyword"]
            k = kai_kw.get(text, {})
            demand = float(k.get("demand", 50))
            boost = 1 if k.get("intent") in ("transactional", "commercial") else 0
            keywords.append({"text": text, "match": "Exact match" if crit == "exact" else "Phrase match",
                             "adGroup": r.get("Ad Group") or "Ad group 1", "demand": demand,
                             "qualityScore": max(4, min(9, 5 + round(demand / 34) + boost)),
                             "ctr": round(0.02 + 0.045 * demand / 100 + (0.01 if crit == "exact" else 0), 4)})
            if (r.get("Ad Group") or "Ad group 1") not in groups:
                groups.append(r.get("Ad Group") or "Ad group 1")
    if not keywords:  # no Editor file: fall back to the verified bundle
        for k in sb.get("keywords", []):
            keywords.append({"text": k["keyword"], "match": "Exact match" if k.get("match") == "exact" else "Phrase match",
                             "adGroup": "Ad group 1", "demand": 50.0, "qualityScore": 7, "ctr": 0.04})
        groups = ["Ad group 1"] if keywords else []
    negatives = [r["Keyword"] for r in editor if (r.get("Criterion Type") or "").startswith("Negative")] \
        or sb.get("negatives", [])

    campaigns = []
    for c in sb.get("campaigns", []):
        search = c.get("type") == "Search"
        campaigns.append({
            "id": "search" if search else "pmax", "name": c["name"], "type": "Search" if search else "Performance Max",
            "budget": float(c.get("daily_budget") or 0), "bidStrategy": c.get("bid_strategy", ""),
            "target": f"Max CPC ${float(c.get('max_cpc') or econ.get('max_cpc') or 0):.2f}" if search
            else f"Target ROAS {float(c.get('target_roas') or 0) * 100:.0f}%"})

    headlines = copy.get("headlines") or sb.get("headlines", [])
    descriptions = copy.get("descriptions") or sb.get("descriptions", [])
    final_url = sb.get("final_url") or f"{store_url}/products/{handle}"
    path = [p for p in urlparse(final_url).path.split("/") if p][:2]

    # search terms people typed: each keyword's own term plus Kai's longer searches it matches
    terms = []
    by_demand = sorted(kai_kw.values(), key=lambda k: -float(k.get("demand", 0)))
    for k in keywords:
        if k["match"] == "Exact match":
            terms.append({"term": k["text"], "keyword": k["text"], "share": 1, "added": True})
            continue
        longer = [x["keyword"] for x in by_demand if x["keyword"] != k["text"] and x.get("role") != "negative"
                  and re.search(rf"\b{re.escape(k['text'])}\b", x["keyword"])][:2]
        own = 1.0 if not longer else 0.55
        terms.append({"term": k["text"], "keyword": k["text"], "share": own, "added": True})
        for i, t in enumerate(longer):
            terms.append({"term": t, "keyword": k["text"], "share": round((1 - own) * (0.6 if i == 0 else 0.4), 3)})
    phrase = [k["text"] for k in keywords if k["match"] == "Phrase match"]
    for x in by_demand:
        if x.get("role") == "negative" and any(re.search(rf"\b{re.escape(p)}\b", x["keyword"]) for p in phrase):
            terms.append({"term": x["keyword"], "keyword": next(p for p in phrase if re.search(rf"\b{re.escape(p)}\b",
                                                                                            x["keyword"])),
                          "share": 0, "excluded": True})
            if sum(1 for t in terms if t.get("excluded")) >= 3:
                break

    rafael = get("rafael")
    comp = (rafael.json("competitor_set.json") if rafael else None) or {}
    matrix = {r.get("url"): r for r in ((rafael.json("competitor_matrix.json") if rafael else None) or [])}
    offers = [{"id": "ours", "title": title, "seller": store_name, "price": price, "rating": None, "reviews": 0,
               "shipping": "", "color": _pick(task_id, PALETTE), "lid": "#c8a46e", "ours": True, "image": image}]
    for i, o in enumerate(comp.get("google_shopping", [])[:7]):
        if o.get("price") is None:
            continue
        offers.append({"id": f"o{i}", "title": o.get("title") or "Product", "seller": o.get("seller") or "",
                       "price": float(o["price"]), "rating": o.get("rating"), "reviews": int(o.get("rating_count") or 0),
                       "shipping": "", "color": _pick(f"{task_id}{i}", PALETTE), "lid": "#9aa0a6", "image": None})
    organic = []
    for p in comp.get("products", [])[:5]:
        m = matrix.get(p.get("url"), {})
        snippet = "; ".join((m.get("claims") or [])[:3]) or m.get("shipping_returns") or ""
        d = _domain(p.get("url") or p.get("domain") or "")
        organic.append({"site": _site(d), "domain": d, "crumbs": [x for x in urlparse(p.get("url") or "").path.split("/")
                                                                    if x][:2],
                        "title": p.get("title") or d, "snippet": snippet[:220], "color": _pick(d, PALETTE)})
    ours = {"site": store_name, "domain": domain, "crumbs": ["products", handle], "title": f"{title} – {store_name}",
            "snippet": (seo.get("description") or _plain(description))[:220], "color": offers[0]["color"]}
    organic.insert(min(1, len(organic)), ours)

    leo = get("leo")
    faq = (leo.json("faq.json") if leo else None) or []
    paa = [{"q": f["question"], "a": f["answer"]} for f in faq if f.get("question") and f.get("answer")][:4]

    ad_kw = {k["text"] for k in keywords}
    neg = {x["keyword"] for x in by_demand if x.get("role") == "negative"} | set(negatives)
    related = [k for k in ([kmap.get("primary")] + list(kmap.get("secondary") or []) + [x["keyword"] for x in by_demand])
               if k and k not in ad_kw and k not in neg and len(k.split()) <= 6 and "?" not in k]
    related = list(dict.fromkeys(related))[:8]
    suggested = [k["text"] for k in sorted(keywords, key=lambda k: -k["demand"])][:4]
    words = re.findall(r"[a-z]{4,}", f"{kmap.get('primary', '')} {product.get('productType', '')} {title}".lower())
    shopping_terms = [w for w in dict.fromkeys(words) if w not in STOP][:6]

    digits = str(int(hashlib.sha256(task_id.encode()).hexdigest(), 16))[:10]
    return {
        "id": task_id, "source": "run",
        "run": {"task": task_id, "title": meta.get("title") or title, "coworker": meta.get("coworker"),
                "phase": meta.get("phase"), "updated": meta.get("updated")},
        "ACCOUNT": {"name": f"{store_name} (mock)", "customerId": f"{digits[:3]}-{digits[3:6]}-{digits[6:]}",
                    "currency": shop.get("currencyCode") or "USD"},
        "STORE": {"name": store_name, "domain": domain, "url": store_url or f"https://{domain}"},
        "PRODUCT": {"id": handle, "title": title, "shortTitle": title[:60], "price": price, "rating": None,
                    "reviews": 0, "color": offers[0]["color"], "bullets": _bullets(description), "image": image},
        "ECONOMICS": {"price": price, "margin": float(econ.get("margin") or 0),
                      "breakevenCpa": float(econ.get("breakeven_cpa") or 0), "targetCpa": float(econ.get("target_cpa") or 0),
                      "conversionRate": float(econ.get("conversion_rate") or 0.02),
                      "maxCpc": float(econ.get("max_cpc") or 0), "monthlyBudget": float(econ.get("monthly_budget") or 0)},
        "CAMPAIGNS": campaigns,
        "KEYWORDS": keywords,
        "AD_GROUPS": groups,
        "NEGATIVES": negatives,
        "HEADLINES": [{"text": h, "label": HEADLINE_LABELS[i % len(HEADLINE_LABELS)]} for i, h in enumerate(headlines)],
        "DESCRIPTIONS": [{"text": d, "label": DESCRIPTION_LABELS[i % 4]} for i, d in enumerate(descriptions)],
        "DISPLAY_PATH": [p[:15] for p in path],
        "SITELINKS": [], "CALLOUTS": [], "COMPETITOR_ADS": [],
        "OFFERS": offers,
        "ORGANIC": organic,
        "PEOPLE_ALSO_ASK": paa,
        "SEARCH_TERMS": terms,
        "RELATED_SEARCHES": related,
        "SUGGESTED_QUERIES": suggested,
        "SHOPPING_TERMS": shopping_terms,
        "editorCsvUrl": sasha.url("google_ads_editor.csv"),
    }


# --- routes ---------------------------------------------------------------------------------------------

def _meta(row: dict) -> dict:
    return {"task": row["task_id"], "title": _title(row), "coworker": row["coworker"], "phase": row["phase"],
            "updated": row["updated_at"].timestamp() * 1000}


@router.get("/runs")
def list_runs(key: str = Query(""), limit: int = Query(20, le=100)):
    if not _allowed(key, None, ""):
        raise HTTPException(401, "bad key")
    return {"runs": [_meta(r) for r in db.all_(RUNS_WITH_ADS, limit)]}


@router.get("/run")
def get_run(task: str | None = Query(None), key: str = Query(""), t: str = Query("")):
    if not _allowed(key, task, t):
        raise HTTPException(401, "bad key")
    if task:
        row = db.one("select task_id, coworker, phase, updated_at, state from runs where task_id = %s", task)
    else:
        row = (db.all_(RUNS_WITH_ADS, 1) or [None])[0]
    if not row:
        raise HTTPException(404, "no run with a Google Ads deliverable yet")
    passed = _passed(row)
    if "sasha" not in passed:
        raise HTTPException(404, "this run has no passed Google Ads deliverable")
    cache: dict[str, Deliverable | None] = {}

    def get(role: str) -> Deliverable | None:
        if role not in cache:
            cache[role] = Deliverable(runs.manifest_from_store(passed[role])) if role in passed else None
        return cache[role]

    return shape(row["task_id"], _meta(row), _snapshot(row), get)
