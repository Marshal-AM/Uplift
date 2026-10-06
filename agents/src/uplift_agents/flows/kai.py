"""Kai — Search Demand Analyst: clustered keyword map, intent, seasonality, peak windows."""

import csv
import io
import re

import numpy as np
from kodosumi.core import forms as F
from uplift_core import llm

from .. import tools
from ..markets import location_code
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Product (name and short description)", name="product", required=True),
    F.InputText(label="Product URL (optional)", name="product_url"),
    F.InputText(label="Market (country code, e.g. US, DE, JP)", name="market_country", value="US", required=True),
    F.InputText(label="Language code (e.g. en, de, ja)", name="language", value="en", required=True),
    F.InputArea(label="Seed keywords (one per line, optional)", name="seed_keywords"),
    F.InputArea(label="Competitor domains (one per line, optional)", name="competitor_domains"),
    F.InputArea(label="Terms to avoid, e.g. other brands (optional)", name="exclude_terms"),
    F.InputArea(label="Your own brand terms (optional)", name="own_brand_terms"),
]

ROLES = ["title", "description", "seo_meta", "blog", "ads_exact", "ads_phrase", "negative"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _product_text(ctx: Context) -> str:
    if ctx.product:
        p = ctx.product
        return f"{p['title']}\n{re.sub('<[^>]+>', ' ', p.get('descriptionHtml') or '')[:3000]}"
    text = ctx.get("product", "")
    if ctx.get("product_url"):
        text += "\n" + tools.scrape(ctx.get("product_url"))["markdown"][:4000]
    return text


def _items(results: list[dict]) -> list[dict]:
    out = []
    for r in results:
        out.extend(r.get("items") or [])
    return out


def _row(item: dict) -> dict | None:
    data = item.get("keyword_data", item)  # ranked_keywords nests under keyword_data
    info = data.get("keyword_info") or {}
    if not data.get("keyword") or not info.get("search_volume"):
        return None
    return {
        "keyword": data["keyword"].lower(),
        "volume": info["search_volume"],
        "cpc": info.get("cpc"),
        "competition": info.get("competition"),
        "kd": (data.get("keyword_properties") or {}).get("keyword_difficulty"),
        "intent": (data.get("search_intent_info") or {}).get("main_intent") or "unknown",
        "monthly": [m["search_volume"] or 0 for m in sorted(
            info.get("monthly_searches") or [], key=lambda m: (m["year"], m["month"]))][-12:],
        "monthly_index": [(m["year"], m["month"]) for m in sorted(
            info.get("monthly_searches") or [], key=lambda m: (m["year"], m["month"]))][-12:],
    }


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("kai", "Kai", ctx)
    loc, lang = location_code(ctx.get("market_country", "US")), ctx.get("language", "en")
    text = _product_text(ctx)

    tracer.markdown_sync("**Kai** · finding seed terms")
    seeds = llm.structured(
        f"Product:\n{text}\n\nList the attributes, use cases and 10–30 seed search terms a shopper would type.",
        {"type": "object", "properties": {
            "attributes": {"type": "array", "items": {"type": "string"}},
            "use_cases": {"type": "array", "items": {"type": "string"}},
            "seeds": {"type": "array", "items": {"type": "string"}}}, "required": ["seeds"]},
    )["seeds"] + ctx.lines("seed_keywords")
    seeds = list(dict.fromkeys(s.lower().strip() for s in seeds if s.strip()))[:30]

    tracer.markdown_sync(f"Expanding {len(seeds)} seeds with DataForSEO")
    base = {"location_code": loc, "language_code": lang}
    raw = _items(tools.dataforseo("dataforseo_labs/google/keyword_ideas/live",
                                  {**base, "keywords": seeds[:20], "limit": 400}))
    for seed in seeds[:5]:
        raw += _items(tools.dataforseo("dataforseo_labs/google/keyword_suggestions/live",
                                       {**base, "keyword": seed, "limit": 60}))
    for domain in ctx.lines("competitor_domains")[:3]:
        raw += _items(tools.dataforseo("dataforseo_labs/google/ranked_keywords/live",
                                       {**base, "target": domain, "limit": 100}))
    rows = {}
    for item in raw:
        row = _row(item)
        if row and row["keyword"] not in rows:
            rows[row["keyword"]] = row
    keywords = sorted(rows.values(), key=lambda r: -r["volume"])[:300]
    if not keywords:
        raise RuntimeError("No keywords with search volume found for this product and market")

    tracer.markdown_sync("Filtering other brands and trademarks")
    own = {t.lower() for t in ctx.lines("own_brand_terms")}
    brands = {t.lower() for t in ctx.lines("exclude_terms")}
    brands |= {d.lower().split(".")[0].replace("www", "") for d in ctx.lines("competitor_domains")}
    detected = llm.structured(
        "Which of these search terms contain a brand or company name? Return the brand names only.\n"
        + "\n".join(k["keyword"] for k in keywords[:300]),
        {"type": "object", "properties": {"brands": {"type": "array", "items": {"type": "string"}}},
         "required": ["brands"]},
    )["brands"]
    brands = {b.lower() for b in brands | set(detected) if b} - own
    brand_re = re.compile(r"\b(" + "|".join(re.escape(b) for b in sorted(brands)) + r")\b") if brands else None
    for k in keywords:
        k["brand"] = bool(brand_re and brand_re.search(k["keyword"]))

    tracer.markdown_sync("Clustering by meaning")
    listing = "\n".join(f"{i}: {k['keyword']}" for i, k in enumerate(keywords))
    groups = llm.structured(
        f"Product:\n{text[:1500]}\n\nGroup these search terms into clusters of the same shopper need (usually "
        f"8–25 clusters). Put every id in exactly one cluster. Name each cluster and give its best use. "
        f"Roles: {', '.join(ROLES)}. Use 'negative' for intent the product does not serve.\n{listing}",
        {"type": "object", "properties": {"clusters": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "role": {"type": "string", "enum": ROLES},
            "ids": {"type": "array", "items": {"type": "integer"}}}, "required": ["name", "role", "ids"]}}},
         "required": ["clusters"]}, max_tokens=8000)["clusters"]
    for g in groups:
        for i in g["ids"]:
            if 0 <= i < len(keywords) and "cluster" not in keywords[i]:
                keywords[i] |= {"cluster": g["name"], "role": g["role"]}
    for k in keywords:
        k.setdefault("cluster", "Other")
        k.setdefault("role", "description")
        if k["brand"]:
            k["role"] = "negative"

    tracer.markdown_sync("Computing seasonality")
    top = [k for k in keywords if k["monthly"] and not k["brand"]][:50]
    totals = np.zeros(12)
    for k in top:
        series = np.array(k["monthly"][-12:] + [0] * (12 - len(k["monthly"][-12:])))
        totals += series
    months = [m for (_, m) in top[0]["monthly_index"]] if top else list(range(1, 13))
    by_month = {months[i]: float(totals[i]) for i in range(min(12, len(months)))}
    peak_months = sorted(by_month, key=lambda m: -by_month[m])[:3]
    windows = [{"peak": MONTHS[m - 1], "start_promo": MONTHS[(m - 3) % 12] + " (6 weeks before)"} for m in peak_months]

    primary = next((k for k in keywords if k["role"] == "title"), keywords[0])
    secondary = [k["keyword"] for k in keywords if k["role"] in ("title", "description", "seo_meta")
                 and k is not primary][:12]
    keyword_map = {"market": ctx.get("market_country"), "language": lang, "primary": primary["keyword"],
                   "secondary": secondary,
                   "keywords": [{x: k[x] for x in ("keyword", "volume", "cpc", "kd", "intent", "cluster", "role")}
                                for k in keywords]}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["keyword", "volume", "cpc", "kd", "intent", "cluster", "role"])
    w.writeheader()
    w.writerows(keyword_map["keywords"])
    negatives = sorted({k["keyword"] for k in keywords if k["role"] == "negative"})

    out.artifact("keyword_map.json", keyword_map)
    out.artifact("keyword_map.csv", buf.getvalue(), "text/csv")
    out.artifact("seasonality.json", {"by_month": {MONTHS[m - 1]: v for m, v in by_month.items()},
                                      "peak_months": [MONTHS[m - 1] for m in peak_months], "windows": windows})
    out.artifact("negatives.txt", "\n".join(negatives))
    out.bundle = {
        "location_code": loc, "language_code": lang, "brand_terms": sorted(brands),
        "keywords": [{"keyword": k["keyword"], "volume": k["volume"], "intent": k["intent"],
                      "cluster": k["cluster"], "role": k["role"], "monthly": k["monthly"]} for k in keywords[:150]],
        "peak_months": peak_months, "months": months,
    }
    clusters = sorted({(k["cluster"], k["role"]) for k in keywords if k["role"] != "negative"})
    summary = (f"**Primary keyword:** {primary['keyword']} ({primary['volume']:,}/mo)\n\n"
               f"**{len(keywords)} keywords** in {len(clusters)} clusters for {ctx.get('market_country')}.\n\n"
               + "\n".join(f"- {c} → {r}" for c, r in clusters[:15])
               + f"\n\n**Peak months:** {', '.join(MONTHS[m - 1] for m in peak_months)}"
               + (f"\n\n{len(negatives)} brand/irrelevant terms moved to negatives." if negatives else ""))
    return out.finalize(summary)
