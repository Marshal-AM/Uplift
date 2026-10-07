"""Quinn — Store Auditor & Performance Analyst: listing score, ranking snapshot, diagnosis, before/after."""

import os
from urllib.parse import urlparse

from kodosumi.core import forms as F
from uplift_core import llm
from uplift_core.score import score

from .. import tools
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputText(label="Product URL (skip if your store is connected)", name="product_url"),
    F.Select(label="Mode", name="mode", option=[
        F.InputOption(name="audit", label="Audit", value=True),
        F.InputOption(name="diagnose", label="Diagnose (uses your sales data)"),
        F.InputOption(name="before_after", label="Before/after report")]),
    F.InputText(label="Market (country code)", name="market_country", value="US"),
    F.InputArea(label="Competitor URLs for benchmark (optional)", name="competitor_urls"),
    F.InputArea(label="Store search phrases to track (one per line, optional)", name="store_queries"),
]

PRICES = {"kai": 1.25, "rafael": 1.25, "priya": 1.5, "marcus": 1.25, "clara": 2.0, "iris": 2.5, "oskar": 1.5,
          "yuki": 1.0, "leo": 2.0, "sasha": 1.5, "ruth": 0.25}

PAGE_SCHEMA = {"type": "object", "properties": {
    "title": {"type": "string"}, "description_html": {"type": "string"}, "meta_title": {"type": "string"},
    "meta_description": {"type": "string"}, "images": {"type": "array", "items": {"type": "object", "properties": {
        "url": {"type": "string"}, "alt": {"type": "string"}}}}, "tags": {"type": "array", "items": {"type": "string"}},
    "has_faq": {"type": "boolean"}, "review_count": {"type": "integer"}, "category": {"type": "string"}}}


def _from_page(url: str) -> dict:
    """Public-URL audit: map the rendered page onto the snapshot shape the score expects."""
    data = tools.scrape(url, schema=PAGE_SCHEMA).get("json") or {}
    path = urlparse(url).path.rstrip("/")
    return {"title": data.get("title", ""), "handle": path.split("/")[-1], "descriptionHtml": data.get("description_html", ""),
            "seo": {"title": data.get("meta_title", ""), "description": data.get("meta_description", "")},
            "tags": data.get("tags", []), "onlineStoreUrl": url,
            "media": {"nodes": [{"mediaContentType": "IMAGE", "alt": i.get("alt"), "image": {"url": i["url"], "width": 0}}
                                for i in data.get("images", []) if i.get("url")]},
            "metafields": {"nodes": ([{"namespace": "custom", "key": "faq", "value": "[1,2,3]"}] if data.get("has_faq") else [])
                           + ([{"namespace": "reviews", "key": "rating_count", "value": str(data["review_count"])}]
                              if data.get("review_count") else [])},
            "variants": {"nodes": []}, "collections": {"nodes": []},
            "category": {"fullName": data["category"]} if data.get("category") else None}


def judge_persuasion(product: dict) -> float:
    r = llm.structured(
        f"Rate how persuasive and clear this product page copy is for shoppers, 0–5.\nTitle: {product.get('title')}\n"
        f"Description: {product.get('descriptionHtml', '')[:6000]}",
        {"type": "object", "properties": {"score": {"type": "number", "minimum": 0, "maximum": 5},
                                          "reason": {"type": "string"}}, "required": ["score"]})
    return max(0.0, min(5.0, float(r["score"])))


def ranking_snapshot(product: dict, keywords: list[str], country: str) -> list[dict]:
    """Google organic position of the product's store domain for each keyword (Serper, top 20)."""
    domain = urlparse(product.get("onlineStoreUrl") or "").netloc.removeprefix("www.")
    rows = []
    for kw in keywords[:5]:
        organic = tools.google_search(kw, country, "en", num=20).get("organic", [])
        domains = [urlparse(o["link"]).netloc.removeprefix("www.") for o in organic]
        pos = next((o["position"] for o, d in zip(organic, domains) if domain and domain in d), None)
        rows.append({"keyword": kw, "organic_position": pos, "outranked_by": domains[:3]})
    return rows


STORE_RANK_QUERY = ("query Rank($q: String!) { products(first: 50, query: $q, sortKey: RELEVANCE) "
                    "{ nodes { handle } } }")


def store_search_ranks(read_token: str, handle: str, keywords: list[str]) -> list[dict]:
    """The product's position in the store's own relevance-ranked product search for each keyword."""
    rows = []
    for kw in keywords[:6]:
        handles = [n["handle"] for n in tools.store_query(read_token, STORE_RANK_QUERY, {"q": kw})["products"]["nodes"]]
        rows.append({"keyword": kw, "rank": handles.index(handle) + 1 if handle in handles else None,
                     "results": len(handles)})
    return rows


MODES = {"audit": "Auditing the listing", "before_after": "Comparing the listing before and after"}

def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("quinn", "Quinn", ctx)
    mode = ctx.get("mode", "audit")
    country = ctx.get("market_country", "US").upper()

    tracer.markdown_sync(f"**Quinn** · {MODES.get(mode, mode)}")
    product = ctx.product or (_from_page(ctx.get("product_url")) if ctx.get("product_url") else None)
    if not product:
        raise RuntimeError("INPUT_MISSING: give a product URL or connect your store")
    kai = ctx.upstream_artifact("kai", "keyword_map.json")
    keywords = {"primary": kai["primary"], "secondary": kai["secondary"]} if kai else \
        ctx.envelope.get("keywords") or None
    result = score(product, keywords)
    judge = judge_persuasion(product)
    total = round(result["deterministic"] + judge, 1)

    kw_list = [keywords["primary"], *keywords["secondary"][:4]] if keywords else llm.structured(
        f"Give the 5 most likely shopper search queries for: {product.get('title')}",
        {"type": "object", "properties": {"q": {"type": "array", "items": {"type": "string"}}}, "required": ["q"]})["q"]
    ranks = ranking_snapshot(product, kw_list, country) if product.get("onlineStoreUrl") else []
    store_kws = ctx.lines("store_queries") or kw_list
    store_ranks = store_search_ranks(ctx.read_token, product["handle"], store_kws) \
        if ctx.read_token and product.get("handle") else []

    speed = None
    if product.get("onlineStoreUrl") and os.environ.get("GOOGLE_API_KEY"):
        try:
            speed = tools.pagespeed(product["onlineStoreUrl"])
        except Exception:
            speed = None

    sales = None
    if mode == "diagnose" and ctx.read_token:
        data = tools.store_query(ctx.read_token, 'query { shopifyqlQuery(query: "FROM sales SHOW total_sales, orders '
                                                 'GROUP BY product_title SINCE -28d ORDER BY total_sales DESC") '
                                                 '{ tableData { columns { name } rows } parseErrors } }')
        sales = data["shopifyqlQuery"]
        out.bundle["sales_query"] = "FROM sales SHOW total_sales, orders GROUP BY product_title SINCE -28d " \
                                    "ORDER BY total_sales DESC"

    plan = llm.structured(
        f"Listing score sections: {result['sections']} (max: discoverability 22, persuasion 20, visuals 15, trust 18, "
        f"catalog 15, compliance 10). Compliance hits: {result['compliance_hits']}\nRankings: {ranks}\n"
        f"Sales (28 days): {sales}\nPage speed (info only): {speed}\n"
        f"Write a prioritized fix plan. Each fix names exactly one specialist from {list(PRICES)} "
        "(kai keywords, rafael competitors, priya competitor reviews, marcus pricing/promotions, clara copy, iris "
        "images, oskar catalog/collections/feed, yuki translation, leo FAQ/content/email, sasha ads, ruth compliance). "
        "If sales data is given, diagnose: traffic, conversion, or basket-size problem.",
        {"type": "object", "properties": {
            "diagnosis": {"type": "string"},
            "fixes": {"type": "array", "items": {"type": "object", "properties": {
                "fix": {"type": "string"}, "specialist": {"type": "string", "enum": list(PRICES)},
                "impact": {"type": "string", "enum": ["high", "medium", "low"]}}, "required": ["fix", "specialist",
                                                                                              "impact"]}}},
         "required": ["fixes"]}, max_tokens=3000, purpose="Writing the prioritized fix plan")
    fixes = [{**f, "price": PRICES[f["specialist"]]} for f in plan["fixes"]]

    report = {"mode": mode, "score": total, "deterministic": result["deterministic"], "judge": judge,
              "sections": result["sections"], "compliance_hits": result["compliance_hits"], "rankings": ranks,
              "store_search_ranks": store_ranks,
              "page_speed": speed, "sales": sales, "diagnosis": plan.get("diagnosis"), "fixes": fixes}
    if mode == "before_after":
        before = ctx.envelope.get("baseline") or ctx.upstream_artifact("quinn", "audit_report.json") or {}
        report["before"] = {"score": before.get("score"), "sections": before.get("sections"),
                            "store_search_ranks": before.get("store_search_ranks", [])}
        report["delta"] = round(total - (before.get("score") or 0), 1)
    out.artifact("audit_report.json", report)
    md = [f"# Listing score: {total}/100", *(f"- {k}: {v}" for k, v in result["sections"].items()),
          f"- persuasion (judge): +{judge}", "", "## Rankings",
          *(f"- {r['keyword']}: {'#' + str(r['organic_position']) if r['organic_position'] else 'not in top 20'}"
            for r in ranks), "", "## Store search rank (Shopify, relevance)",
          *(f"- {r['keyword']}: {'#' + str(r['rank']) if r['rank'] else 'not found'} of {r['results']}"
            for r in store_ranks), "", "## Fix plan",
          *(f"- [{f['impact']}] {f['fix']} → {f['specialist']} ({f['price']} credits)" for f in fixes)]
    if speed:
        md += ["", f"## Page speed (info)\nScore {speed['score']}, LCP {speed['lcp_ms'] / 1000:.1f}s"]
    if mode == "before_after":
        md.insert(1, f"Before: {report['before']['score']} → After: {total} (Δ {report['delta']:+})")
    out.artifact("audit_report.md", "\n".join(md), "text/markdown")
    out.artifact("fix_plan.json", fixes)
    out.bundle |= {"product": product, "keywords": keywords, "deterministic": result["deterministic"],
                   "sections": result["sections"], "judge": judge, "score": total, "rankings": ranks,
                   "country": country, "store_search_ranks": store_ranks, "fixes": fixes, "sales": sales}
    head = f"**Listing score {total}/100**" + (f" (was {report['before']['score']})" if mode == "before_after" else "")
    return out.finalize(head + "\n\n" + "\n".join(f"- [{f['impact']}] {f['fix']} → {f['specialist']}"
                                                  for f in fixes[:6]))
