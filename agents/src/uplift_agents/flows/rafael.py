"""Rafael — Competitor & Market Analyst: who ranks, what they charge and promise, where the gaps are."""

import csv
import io
import re
import statistics
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from kodosumi.core import forms as F
from uplift_core import llm

from .. import tools
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Product (name and short description)", name="product", required=True),
    F.InputText(label="Product URL (optional)", name="product_url"),
    F.InputText(label="Market (country code)", name="market_country", value="US", required=True),
    F.InputText(label="Language code", name="language", value="en", required=True),
    F.InputArea(label="Known competitors (domains or product URLs, optional)", name="known_competitors"),
    F.InputNumber(label="Your price (optional)", name="price_point"),
    F.InputNumber(label="Max competitors", name="max_competitors", value="8"),
]

PAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "price": {"type": "number"}, "compare_at_price": {"type": "number"},
        "currency": {"type": "string"}, "claims": {"type": "array", "items": {"type": "string"}},
        "guarantees": {"type": "array", "items": {"type": "string"}}, "shipping_returns": {"type": "string"},
        "bundle_offers": {"type": "array", "items": {"type": "string"}}, "image_count": {"type": "integer"},
        "has_video": {"type": "boolean"}, "review_count": {"type": "integer"}, "rating": {"type": "number"},
        "brand": {"type": "string"},
    },
}


def _domain(url: str) -> str:
    return urlparse(url if "//" in url else f"https://{url}").netloc.removeprefix("www.")


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("rafael", "Rafael", ctx)
    country, lang = ctx.get("market_country", "US").upper(), ctx.get("language", "en")
    max_n = int(ctx.get("max_competitors", 8) or 8)
    product = ctx.product["title"] if ctx.product else ctx.get("product", "")
    own_domain = _domain((ctx.snapshot or {}).get("shop", {}).get("primaryDomain", {}).get("url", "") or "x")

    kai = ctx.upstream_artifact("kai", "keyword_map.json")
    queries = ([kai["primary"], *kai["secondary"][:4]] if kai else llm.structured(
        f"Product: {product}\nGive 5 head search queries shoppers use to find this product.",
        {"type": "object", "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
         "required": ["queries"]})["queries"][:5])

    tracer.markdown_sync(f"**Rafael** · reading Google results for {len(queries)} queries")
    serp_rows, paa = [], set()
    for q in queries:
        serp = tools.google_search(q, country, lang, num=20)
        for item in serp.get("organic", []):
            serp_rows.append({"query": q, "rank": item["position"], "domain": _domain(item["link"]),
                              "url": item["link"], "title": item.get("title")})
        paa |= {p["question"] for p in serp.get("peopleAlsoAsk", [])}
    offers = [o for o in tools.google_shopping(queries[0], country, lang) if o.get("price_value")]

    tracer.markdown_sync("Choosing the competitor set")
    visibility: dict[str, float] = {}
    urls: dict[str, str] = {}
    for row in serp_rows:
        if row["domain"].removeprefix("www.") == own_domain:
            continue
        visibility[row["domain"]] = visibility.get(row["domain"], 0) + 1 / row["rank"]
        urls.setdefault(row["domain"], row["url"])
    for known in ctx.lines("known_competitors"):
        d = _domain(known)
        visibility[d] = visibility.get(d, 0) + 10
        if "/" in known.split("//")[-1]:
            urls[d] = known if "//" in known else f"https://{known}"
    competitors = sorted(visibility, key=lambda d: -visibility[d])[:max_n]

    tracer.markdown_sync(f"Reading {len(competitors)} competitor product pages")

    def read(domain: str) -> dict:
        url = urls.get(domain) or f"https://{domain}"
        try:
            page = tools.scrape(url, schema=PAGE_SCHEMA)
            data = page.get("json") or {}
        except Exception as exc:  # blocked page: keep the row, mark unavailable
            return {"domain": domain, "url": url, "unavailable": str(exc)[:120]}
        return {"domain": domain, "url": url, **data}

    with ThreadPoolExecutor(8) as pool:
        matrix = list(pool.map(read, competitors))
    for row in matrix:
        if row.get("price"):
            out.cite(f"{row['domain']} price {row['price']}", row["url"], row.get("title", ""))

    prices = sorted([r["price"] for r in matrix if r.get("price")] + [o["price_value"] for o in offers])
    bands = {}
    if prices:
        q = statistics.quantiles(prices, n=4) if len(prices) >= 4 else [prices[0], statistics.median(prices),
                                                                          prices[-1]]
        bands = {"min": prices[0], "p25": q[0], "median": statistics.median(prices), "p75": q[-1],
                 "max": prices[-1], "n": len(prices)}

    claims: dict[str, int] = {}
    for r in matrix:
        for c in r.get("claims") or []:
            key = re.sub(r"\s+", " ", c.lower()).strip()[:80]
            claims[key] = claims.get(key, 0) + 1
    synthesis = llm.structured(
        f"Our product: {product}\nOur price: {ctx.get('price_point') or 'unknown'}\nPrice bands: {bands}\n"
        f"Competitors: {matrix}\nCommon claims: {claims}\nPeople also ask: {sorted(paa)[:20]}\n"
        "Write a positioning analysis: positioning map, offer patterns, content gaps, and where this product can win.",
        {"type": "object", "properties": {
            "positioning": {"type": "string"}, "offer_patterns": {"type": "array", "items": {"type": "string"}},
            "content_gaps": {"type": "array", "items": {"type": "string"}},
            "opportunities": {"type": "array", "items": {"type": "string"}}},
         "required": ["positioning", "content_gaps", "opportunities"]}, max_tokens=3000)

    buf = io.StringIO()
    cols = ["domain", "url", "title", "price", "currency", "rating", "review_count", "image_count", "has_video",
            "shipping_returns", "unavailable"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(matrix)
    competitor_set = {
        "products": [{"domain": r["domain"], "url": r["url"], "title": r.get("title")}
                     for r in matrix if not r.get("unavailable")],
        "google_shopping": [{"title": o.get("title"), "product_id": o.get("productId"), "seller": o.get("source"),
                             "price": o["price_value"], "rating": o.get("rating"),
                             "rating_count": o.get("ratingCount")} for o in offers[:10]],
        "brands": sorted({r.get("brand") for r in matrix if r.get("brand")}),
    }
    out.artifact("competitor_matrix.json", matrix)
    out.artifact("competitor_matrix.csv", buf.getvalue(), "text/csv")
    out.artifact("price_bands.json", bands)
    out.artifact("positioning.md", synthesis["positioning"], "text/markdown")
    out.artifact("gaps.md", "\n".join(f"- {g}" for g in synthesis["content_gaps"]), "text/markdown")
    out.artifact("competitor_set.json", competitor_set)
    out.bundle = {
        "country": country, "language": lang, "queries": queries,
        "top_domains": [r["domain"] for r in sorted(serp_rows, key=lambda r: r["rank"]) if r["query"] == queries[0]][:5],
        "evidence": [{"url": r["url"], "title": r.get("title"), "price": r.get("price")}
                     for r in matrix if not r.get("unavailable")],
        "prices": prices, "bands": bands,
        "coverage": [{"domain": r["domain"], "filled": sum(1 for c in cols if r.get(c) not in (None, "", []))}
                     for r in matrix],
    }
    summary = (f"**{len(competitors)} competitors** across {len(queries)} queries.\n\n"
               + (f"**Price bands:** {bands['min']:.2f}–{bands['max']:.2f} (median {bands['median']:.2f})\n\n"
                  if bands else "")
               + "**Where to win:**\n" + "\n".join(f"- {o}" for o in synthesis["opportunities"][:6]))
    return out.finalize(summary)
