"""Kai — Search Demand Analyst: keyword map from Google autocomplete, related searches and questions (Serper),
demand signal, brand filter, clusters with intent and on-page roles."""

import csv
import io
import re
from concurrent.futures import ThreadPoolExecutor

from kodosumi.core import forms as F
from uplift_core import llm

from .. import tools
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Product (name and short description)", name="product", required=True),
    F.InputText(label="Product URL (optional)", name="product_url"),
    F.InputText(label="Market (country code, e.g. US, DE, JP)", name="market_country", value="US", required=True),
    F.InputText(label="Language code (e.g. en, de, ja)", name="language", value="en", required=True),
    F.InputArea(label="Seed keywords (one per line, optional)", name="seed_keywords"),
    F.InputArea(label="Competitor brands or domains to exclude (one per line, optional)", name="competitor_domains"),
    F.InputArea(label="Terms to avoid, e.g. other brands (optional)", name="exclude_terms"),
    F.InputArea(label="Your own brand terms (optional)", name="own_brand_terms"),
]

ROLES = ["title", "description", "seo_meta", "blog", "ads_exact", "ads_phrase", "negative"]
INTENTS = ["informational", "commercial", "transactional", "navigational"]


def _product_text(ctx: Context) -> str:
    if ctx.product:
        p = ctx.product
        return f"{p['title']}\n{re.sub('<[^>]+>', ' ', p.get('descriptionHtml') or '')[:3000]}"
    text = ctx.get("product", "")
    if ctx.get("product_url"):
        text += "\n" + tools.scrape(ctx.get("product_url"))["markdown"][:4000]
    return text


SCORES = {"autocomplete": 10, "related": 4, "paa": 2, "seed": 3}


def demand_scores(sources: dict[str, list[dict]]) -> dict[str, float]:
    """Demand signal per keyword from how Google surfaces it: autocomplete rank, related searches, People Also Ask.
    Kept identical to CRE's recomputation (cre/uplift-clearing/src/profiles.ts)."""
    raw = {}
    for kw, srcs in sources.items():
        raw[kw] = sum(max(1, SCORES[s["type"]] - s.get("position", 0)) if s["type"] == "autocomplete"
                      else SCORES[s["type"]] for s in srcs)
    top = max(raw.values(), default=1)
    return {kw: round(100 * v / top, 1) for kw, v in raw.items()}


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("kai", "Kai", ctx)
    country, lang = ctx.get("market_country", "US").upper(), ctx.get("language", "en")
    text = _product_text(ctx)

    tracer.markdown_sync("**Kai** · finding seed terms")
    seeds = llm.structured(
        f"Product:\n{text}\n\nList the attributes, use cases and 10–20 short seed search terms (2–4 words) a shopper "
        "would type.",
        {"type": "object", "properties": {
            "attributes": {"type": "array", "items": {"type": "string"}},
            "use_cases": {"type": "array", "items": {"type": "string"}},
            "seeds": {"type": "array", "items": {"type": "string"}}}, "required": ["seeds"]},
    )["seeds"] + ctx.lines("seed_keywords")
    seeds = list(dict.fromkeys(s.lower().strip() for s in seeds if s.strip()))[:12]

    tracer.markdown_sync(f"Expanding {len(seeds)} seeds with Google autocomplete, related searches and questions")
    sources: dict[str, list[dict]] = {}

    def add(kw: str, src: dict) -> None:
        kw = re.sub(r"\s+", " ", kw.lower()).strip()
        if 2 <= len(kw) <= 80:
            sources.setdefault(kw, []).append(src)

    def expand(seed: str) -> None:
        add(seed, {"type": "seed", "query": seed})
        for pos, sug in enumerate(tools.google_autocomplete(seed, country, lang)):
            add(sug, {"type": "autocomplete", "query": seed, "position": pos})
        serp = tools.google_search(seed, country, lang)
        for rel in serp.get("relatedSearches", []):
            add(rel["query"], {"type": "related", "query": seed})
        for q in serp.get("peopleAlsoAsk", []):
            add(q["question"], {"type": "paa", "query": seed})

    with ThreadPoolExecutor(4) as pool:
        list(pool.map(expand, seeds))
    demand = demand_scores(sources)
    keywords = [{"keyword": kw, "demand": demand[kw], "sources": srcs} for kw, srcs in sources.items()]
    keywords = sorted(keywords, key=lambda k: -k["demand"])[:300]
    if not keywords:
        raise RuntimeError("No keywords found for this product and market")

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
        f"Roles: {', '.join(ROLES)}. Use 'negative' for intent the product does not serve. Give each cluster's "
        f"search intent. Also list in off_target_ids every term this product page cannot serve: other languages "
        f"than '{lang}' or markets than {country}, wholesale/bulk, 'near me'/local, word definitions or "
        f"translations, and other product types.\n{listing}",
        {"type": "object", "properties": {
            "clusters": {"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"}, "role": {"type": "string", "enum": ROLES},
                "intent": {"type": "string", "enum": INTENTS},
                "ids": {"type": "array", "items": {"type": "integer"}}}, "required": ["name", "role", "intent", "ids"]}},
            "off_target_ids": {"type": "array", "items": {"type": "integer"}}},
         "required": ["clusters", "off_target_ids"]}, max_tokens=8000)
    off_target = set(groups["off_target_ids"])
    groups = groups["clusters"]
    for g in groups:
        for i in g["ids"]:
            if 0 <= i < len(keywords) and "cluster" not in keywords[i]:
                keywords[i] |= {"cluster": g["name"], "role": g["role"], "intent": g["intent"]}
    for k in keywords:
        k.setdefault("cluster", "Other")
        k.setdefault("role", "description")
        k.setdefault("intent", "commercial")
    for i, k in enumerate(keywords):
        if k["brand"] or i in off_target:
            k["role"] = "negative"

    primary = next((k for k in keywords if k["role"] == "title"), keywords[0])
    secondary = [k["keyword"] for k in keywords if k["role"] in ("title", "description", "seo_meta")
                 and k is not primary][:12]
    fields = ("keyword", "demand", "intent", "cluster", "role")
    keyword_map = {"market": country, "language": lang, "primary": primary["keyword"], "secondary": secondary,
                   "demand_signal": "0–100, from Google autocomplete rank, related searches and People Also Ask",
                   "keywords": [{x: k[x] for x in fields} for k in keywords]}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(fields))
    w.writeheader()
    w.writerows(keyword_map["keywords"])
    negatives = sorted({k["keyword"] for k in keywords if k["role"] == "negative"})

    out.artifact("keyword_map.json", keyword_map)
    out.artifact("keyword_map.csv", buf.getvalue(), "text/csv")
    out.artifact("negatives.txt", "\n".join(negatives))
    out.bundle = {
        "country": country, "language": lang, "brand_terms": sorted(brands),
        "keywords": [{"keyword": k["keyword"], "demand": k["demand"], "intent": k["intent"], "cluster": k["cluster"],
                      "role": k["role"], "sources": k["sources"]} for k in keywords[:150]],
    }
    clusters = sorted({(k["cluster"], k["role"]) for k in keywords if k["role"] != "negative"})
    summary = (f"**Primary keyword:** {primary['keyword']} (demand {primary['demand']}/100)\n\n"
               f"**{len(keywords)} keywords** from Google autocomplete, related searches and questions, in "
               f"{len(clusters)} clusters for {country}.\n\n"
               + "\n".join(f"- {c} → {r}" for c, r in clusters[:15])
               + (f"\n\n{len(negatives)} brand/irrelevant terms moved to negatives." if negatives else ""))
    return out.finalize(summary)
