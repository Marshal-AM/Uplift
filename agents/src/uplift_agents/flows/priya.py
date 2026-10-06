"""Priya — Competitor Review & Sentiment Analyst. Analyses competitors' customers only."""

import hashlib
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from kodosumi.core import forms as F
from uplift_core import llm

from .. import tools
from ..markets import location_code
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Competitor products (URLs or Amazon ASINs, one per line, up to 5)", name="competitor_products"),
    F.InputText(label="…or a product category to discover competitors", name="category"),
    F.InputArea(label="Competitor brand domains for Trustpilot (optional)", name="competitor_domains"),
    F.InputText(label="Market (country code)", name="market_country", value="US", required=True),
    F.InputText(label="Language code", name="language", value="en", required=True),
    F.InputArea(label="Your product, for context only (optional)", name="my_product"),
    F.InputText(label="Aspects to focus on (optional, comma separated)", name="focus_aspects"),
    F.Checkbox(label="Include Reddit discussions", name="include_social", option="yes", value=True),
]

CODE_SCHEMA = {
    "type": "object",
    "properties": {"reviews": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"},
        "aspects": {"type": "array", "items": {"type": "object", "properties": {
            "aspect": {"type": "string"}, "polarity": {"type": "integer", "minimum": -2, "maximum": 2}},
            "required": ["aspect", "polarity"]}},
        "is_wish": {"type": "boolean"}, "is_dealbreaker": {"type": "boolean"},
        "switch_reason": {"type": "string"}, "use_case": {"type": "string"}, "buyer_type": {"type": "string"}},
        "required": ["id", "aspects"]}}},
    "required": ["reviews"],
}


def _rid(source: str, text: str) -> str:
    return hashlib.sha1(f"{source}|{text}".encode()).hexdigest()[:12]


def _asin(value: str) -> str | None:
    m = re.search(r"(?:/dp/|/gp/product/|^)([A-Z0-9]{10})(?:[/?]|$)", value.strip())
    return m.group(1) if m else None


def collect(ctx: Context, competitors: list[str], shopping: list[dict], tracer) -> list[dict]:
    own = urlparse((ctx.snapshot or {}).get("shop", {}).get("primaryDomain", {}).get("url", "") or "").netloc
    reviews: list[dict] = []
    loc, lang = location_code(ctx.get("market_country", "US")), ctx.get("language", "en")

    def amazon(ref: str) -> list[dict]:
        asin = _asin(ref)
        url = ref if ref.startswith("http") else f"https://www.amazon.com/dp/{asin}"
        return [{"source": "amazon", "competitor": r.get("product_name") or asin, "text": r.get("review_text") or "",
                 "rating": r.get("rating"), "date": r.get("review_posted_date"), "url": r.get("url") or url}
                for r in tools.amazon_reviews(url)]

    def storefront(url: str) -> list[dict]:
        data = tools.scrape(url, schema={"type": "object", "properties": {"product": {"type": "string"},
            "reviews": {"type": "array", "items": {"type": "object", "properties": {
                "text": {"type": "string"}, "rating": {"type": "number"}, "date": {"type": "string"}}}}}}).get("json") or {}
        return [{"source": "storefront", "competitor": data.get("product") or urlparse(url).netloc, "url": url, **r}
                for r in data.get("reviews") or []]

    def google(item: dict) -> list[dict]:
        res = tools.dataforseo_task("merchant/google/reviews/task_post", "merchant/google/reviews/task_get/advanced",
                                    {"gid": item["gid"], "location_code": loc, "language_code": lang, "depth": 100})
        return [{"source": "google_shopping", "competitor": item.get("title"), "text": r.get("review_text") or "",
                 "rating": (r.get("rating") or {}).get("value"), "date": r.get("timestamp"),
                 "url": r.get("url") or "https://shopping.google.com"} for x in res for r in x.get("items") or []]

    def trustpilot(domain: str) -> list[dict]:
        res = tools.dataforseo_task("business_data/trustpilot/reviews/task_post",
                                    "business_data/trustpilot/reviews/task_get", {"domain": domain, "depth": 200})
        return [{"source": "trustpilot", "competitor": domain, "text": r.get("review_text") or "",
                 "rating": (r.get("rating") or {}).get("value"), "date": r.get("timestamp"),
                 "url": r.get("url") or f"https://www.trustpilot.com/review/{domain}"}
                for x in res for r in x.get("items") or []]

    jobs = []
    for ref in competitors:
        if own and own in ref:
            continue  # never analyse the merchant's own reviews
        jobs.append((amazon if _asin(ref) and ("amazon." in ref or not ref.startswith("http")) else storefront, ref))
    jobs += [(google, s) for s in shopping if s.get("gid")][:3]
    jobs += [(trustpilot, d) for d in ctx.lines("competitor_domains") if d not in own][:3]

    tracer.markdown_sync(f"**Priya** · collecting reviews from {len(jobs)} competitor sources")
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda j: _safe(j[0], j[1]), jobs))
    for batch in results:
        reviews.extend(batch)

    if ctx.get("include_social") in (True, "on", "yes"):
        topic = ctx.get("category") or (competitors[0] if competitors else "")
        for q in _safe(tools.reddit_discussions, topic):
            reviews.append({"source": "reddit", "competitor": q["about"] if q["about"] != "category"
                            else "category discussion", "text": q["text"], "date": q["date"], "url": q["url"]})

    seen, clean = set(), []
    for r in reviews:
        text = re.sub(r"\s+", " ", r.get("text") or "").strip()
        key = text.lower()[:200]
        if len(text.split()) < 5 or key in seen or (own and own in (r.get("url") or "")):
            continue
        seen.add(key)
        clean.append({**r, "text": text, "id": _rid(r["source"], text)})
    return clean


def _safe(fn, *args) -> list:
    try:
        return fn(*args)
    except Exception:
        return []


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("priya", "Priya", ctx)
    competitors = ctx.lines("competitor_products")[:5]
    shopping: list[dict] = []
    rafael = ctx.upstream_artifact("rafael", "competitor_set.json")
    if rafael:
        competitors = competitors or [p["url"] for p in rafael["products"]][:5]
        shopping = rafael.get("google_shopping", [])
    if not competitors and ctx.get("category"):
        loc, lang = location_code(ctx.get("market_country", "US")), ctx.get("language", "en")
        found = tools.dataforseo_task("merchant/google/products/task_post", "merchant/google/products/task_get/advanced",
                                      {"keyword": ctx.get("category"), "location_code": loc, "language_code": lang,
                                       "depth": 40})
        offers = sorted([i for r in found for i in r.get("items") or []],
                        key=lambda i: -((i.get("product_rating") or {}).get("votes_count") or 0))
        shopping = offers[:5]
        competitors = [o["url"] for o in offers[:5] if o.get("url")]
    if not competitors and not shopping:
        raise RuntimeError("INPUT_MISSING: give competitor products or a category")

    reviews = collect(ctx, competitors, shopping, tracer)
    if not reviews:
        raise RuntimeError("No competitor reviews could be collected from the given sources")

    tracer.markdown_sync(f"Coding {len(reviews)} reviews by aspect and sentiment")
    focus = ctx.get("focus_aspects", "")
    coded: dict[str, dict] = {}
    batches = [reviews[i:i + 50] for i in range(0, len(reviews), 50)]

    def code(batch: list[dict]) -> list[dict]:
        text = "\n".join(f"[{r['id']}] ({r['source']}, {r.get('rating')}★) {r['text'][:600]}" for r in batch)
        return llm.structured(
            "Code each competitor customer review. Use short, reusable aspect names "
            f"(e.g. leaks, insulation, taste, cleaning, size, durability, price/value, shipping){'; focus on ' + focus if focus else ''}.\n"
            f"{text}", CODE_SCHEMA, max_tokens=8000)["reviews"]

    with ThreadPoolExecutor(4) as pool:
        for batch_result in pool.map(code, batches):
            for c in batch_result:
                coded[c["id"]] = c

    tracer.markdown_sync("Aggregating findings")
    now = datetime.now(UTC)
    weight = {}
    for r in reviews:
        try:
            recent = datetime.fromisoformat(str(r.get("date")).replace("Z", "+00:00")) > now - timedelta(days=548)
        except ValueError:
            recent = False
        weight[r["id"]] = 2 if recent else 1
    pos, neg, wishes, breakers = Counter(), Counter(), Counter(), Counter()
    examples: dict[tuple, list[str]] = defaultdict(list)
    for rid, c in coded.items():
        for a in c.get("aspects", []):
            name = a["aspect"].lower().strip()
            if a["polarity"] > 0:
                pos[name] += weight.get(rid, 1)
                examples[("love", name)].append(rid)
            elif a["polarity"] < 0:
                neg[name] += weight.get(rid, 1)
                examples[("complaint", name)].append(rid)
                if c.get("is_dealbreaker"):
                    breakers[name] += 1
                    examples[("dealbreaker", name)].append(rid)
            if c.get("is_wish"):
                wishes[name] += 1
                examples[("wish", name)].append(rid)
    by_id = {r["id"]: r for r in reviews}

    def finding(kind: str, counter: Counter, n: int) -> list[dict]:
        rows = []
        for aspect, count in counter.most_common(n):
            quotes = [{"text": by_id[i]["text"][:300], "source_url": by_id[i]["url"], "rating": by_id[i].get("rating"),
                       "date": by_id[i].get("date"), "review_id": i} for i in examples[(kind, aspect)][:4]]
            rows.append({"id": f"{kind}:{aspect}", "kind": kind, "aspect": aspect, "weighted_count": count,
                         "quotes": quotes})
        return rows

    findings = (finding("love", pos, 6) + finding("complaint", neg, 8) + finding("wish", wishes, 5)
                + finding("dealbreaker", breakers, 4))
    for f in findings:
        for q in f["quotes"][:1]:
            out.cite(f"{f['kind']}: {f['aspect']}", q["source_url"], q["text"])

    synth = llm.structured(
        f"Findings from competitor reviews (counts are recency-weighted):\n{json.dumps(findings)[:30000]}\n"
        f"Coded review sample:\n{json.dumps(list(coded.values())[:120])[:20000]}\n"
        f"Our product (context only): {ctx.get('my_product', 'not given')}\n"
        "1) Build 2–4 buyer personas ONLY from coded reviews; every attribute must cite ≥3 review ids.\n"
        "2) For each finding give one 'how to win' action: listing claim (only if our product supports it), "
        "FAQ, proof image, offer/guarantee, ad angle, or product improvement.",
        {"type": "object", "properties": {
            "personas": {"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"}, "attributes": {"type": "array", "items": {"type": "object", "properties": {
                    "attribute": {"type": "string"}, "review_ids": {"type": "array", "items": {"type": "string"}}},
                    "required": ["attribute", "review_ids"]}}}, "required": ["name", "attributes"]}},
            "win_plan": {"type": "array", "items": {"type": "object", "properties": {
                "finding_id": {"type": "string"}, "action_type": {"type": "string"}, "action": {"type": "string"}},
                "required": ["finding_id", "action_type", "action"]}}},
         "required": ["personas", "win_plan"]}, max_tokens=6000)

    report = ["# Competitor customer sentiment", f"{len(reviews)} reviews from {len({r['source'] for r in reviews})} "
              "sources. Your own reviews are not included.", ""]
    for kind, title in (("love", "What customers love"), ("complaint", "Top complaints"),
                        ("wish", "Unmet wishes"), ("dealbreaker", "Deal-breakers")):
        report.append(f"## {title}")
        for f in [f for f in findings if f["kind"] == kind]:
            report.append(f"- **{f['aspect']}** ({f['weighted_count']})")
            report += [f"  > \"{q['text'][:200]}\" — [{q.get('rating') or ''}★ source]({q['source_url']})"
                       for q in f["quotes"][:2]]
        report.append("")
    report.append("## How to win")
    report += [f"- **{w['action_type']}** ({w['finding_id']}): {w['action']}" for w in synth["win_plan"]]

    out.artifact("competitor_sentiment_report.md", "\n".join(report), "text/markdown")
    out.artifact("findings.json", findings)
    out.artifact("coded_reviews.json", [{**by_id[i], **c} for i, c in coded.items() if i in by_id])
    out.artifact("personas.json", synth["personas"])
    out.artifact("win_plan.json", synth["win_plan"])
    out.bundle = {
        "own_domain": urlparse((ctx.snapshot or {}).get("shop", {}).get("primaryDomain", {}).get("url", "") or "").netloc,
        "sources": sorted({r["url"] for r in reviews})[:200],
        "coded": [{"id": i, "aspects": c.get("aspects", []), "weight": weight.get(i, 1),
                   "is_wish": c.get("is_wish", False), "is_dealbreaker": c.get("is_dealbreaker", False)}
                  for i, c in coded.items()],
        "findings": [{"id": f["id"], "weighted_count": f["weighted_count"]} for f in findings],
        "quotes": [{"text": q["text"], "source_url": q["source_url"], "source": by_id[q["review_id"]]["source"]}
                   for f in findings for q in f["quotes"][:1]],
        "personas": synth["personas"], "win_plan": synth["win_plan"], "review_count": len(reviews),
        "source_count": len({r["source"] for r in reviews}),
    }
    top = [f"- {f['aspect']}" for f in findings if f["kind"] == "complaint"][:5]
    return out.finalize(f"**{len(reviews)} competitor reviews** analysed.\n\n**Top complaints to win on:**\n"
                        + "\n".join(top))
