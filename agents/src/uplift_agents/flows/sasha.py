"""Sasha — Paid Ads Strategist (Google Ads in v1): break-even bids, keywords, negatives, copy, Editor import."""

import csv
import io
from urllib.parse import urlencode

from kodosumi.core import forms as F
from uplift_core import llm

from .. import tools
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Product facts and price (skip if your store is connected)", name="product_facts"),
    F.InputText(label="Campaign types (search, shopping)", name="campaign_types", value="search,shopping", required=True),
    F.InputNumber(label="Monthly budget cap", name="budget_cap", required=True),
    F.InputNumber(label="Target ROAS (e.g. 3) — or leave empty and set target CPA", name="target_roas"),
    F.InputNumber(label="Target CPA (optional)", name="target_cpa"),
    F.InputNumber(label="Margin % (if not computed by Marcus)", name="margin_pct"),
    F.InputNumber(label="Product page conversion rate % (optional)", name="conversion_rate"),
    F.InputText(label="Market (country code)", name="market_country", value="US", required=True),
    F.InputArea(label="Keywords to target (optional, one per line, e.g. from Kai)", name="keywords"),
]

DEFAULT_CVR = 0.02  # used only when neither GA4 nor the merchant gives one; flagged in the plan


def negative_blocks(negative: str, match: str, positive: str) -> bool:
    """Would this negative keyword stop the positive keyword's queries from serving?"""
    n, p = negative.lower().split(), positive.lower().split()
    if match == "exact":
        return n == p
    if match == "phrase":
        return any(p[i:i + len(n)] == n for i in range(len(p) - len(n) + 1))
    return set(n) <= set(p)  # broad negative: all words present in any order


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("sasha", "Sasha", ctx)
    product = ctx.product or {}
    country = ctx.get("market_country", "US").upper()
    price = float(product["variants"]["nodes"][0]["price"]) if product.get("variants") else None
    margin = None
    if ctx.get("margin_pct"):
        margin = float(ctx.get("margin_pct")) / 100
    elif product.get("variants"):
        v = product["variants"]["nodes"][0]
        cost = (v.get("inventoryItem") or {}).get("unitCost")
        if cost:
            margin = (float(v["price"]) - float(cost["amount"])) / float(v["price"])
    if not price:
        price = float(llm.structured(f"Extract the product price as a number:\n{ctx.get('product_facts', '')}",
                                     {"type": "object", "properties": {"price": {"type": "number"}},
                                      "required": ["price"]})["price"])
    if not margin:
        raise RuntimeError("INPUT_MISSING: margin % is required (or connect the store with unit costs)")
    cvr = float(ctx.get("conversion_rate")) / 100 if ctx.get("conversion_rate") else DEFAULT_CVR
    breakeven_cpa = price * margin
    target_cpa = float(ctx.get("target_cpa")) if ctx.get("target_cpa") else (
        price / float(ctx.get("target_roas")) if ctx.get("target_roas") else breakeven_cpa * 0.7)
    target_cpa = min(target_cpa, breakeven_cpa)
    max_cpc = round(target_cpa * cvr, 2)
    budget = float(ctx.get("budget_cap"))
    daily = round(budget / 30.4, 2)

    tracer.markdown_sync("**Sasha** · selecting profitable keywords")
    kai = ctx.upstream_artifact("kai", "keyword_map.json")
    if kai:
        kws = [k for k in kai["keywords"] if k["role"] in ("ads_exact", "ads_phrase", "title", "description")]
        negatives = [k["keyword"] for k in kai["keywords"] if k["role"] == "negative"]
    else:  # merchant's keywords, else what shoppers type for this kind of product (Google autocomplete)
        seeds = ctx.lines("keywords") or llm.structured(
            f"Product: {product.get('title', '')}\n{ctx.get('product_facts', '')[:1500]}\nGive 3 generic 2–4 word phrases "
            "a shopper would type into Google to buy this kind of product (no brand or model names).",
            {"type": "object", "properties": {"phrases": {"type": "array", "items": {"type": "string"}}},
             "required": ["phrases"]})["phrases"][:3]
        found = seeds if ctx.lines("keywords") else [*seeds, *(k for seed in seeds
                                                              for k in tools.google_autocomplete(seed, country, "en"))]
        kws = [{"keyword": k.lower(), "cluster": "core", "role": "ads_phrase"} for k in dict.fromkeys(found) if k]
        negatives = []
    affordable = kws[:60]  # every keyword is bid at max_cpc, which is capped by break-even economics
    competitor_brands = (ctx.upstream_artifact("rafael", "competitor_set.json") or {}).get("brands", [])
    negatives = list(dict.fromkeys(negatives + [b.lower() for b in competitor_brands]))
    negatives = [n for n in negatives if not any(negative_blocks(n, "phrase", k["keyword"]) for k in affordable)]

    tracer.markdown_sync("Writing ad copy")
    angles = [w["action"] for w in (ctx.upstream_artifact("priya", "win_plan.json") or [])
              if "ad" in w["action_type"].lower()][:5]
    facts = ctx.upstream_artifact("clara", "facts.json") or ctx.get("product_facts", "")
    copy = llm.structured(
        f"Product: {product.get('title') or ''}\nFacts: {facts}\nAngles: {angles}\n"
        "Write Google Ads responsive search ad assets: 15 headlines (≤30 chars), 4 descriptions (≤90 chars), "
        "and a Performance Max long headline (≤90). Claims from facts only; no ALL CAPS words, no '!!'.",
        {"type": "object", "properties": {"headlines": {"type": "array", "items": {"type": "string"}},
                                          "descriptions": {"type": "array", "items": {"type": "string"}},
                                          "long_headline": {"type": "string"}},
         "required": ["headlines", "descriptions", "long_headline"]})
    headlines = [h for h in copy["headlines"] if len(h) <= 30][:15]
    descriptions = [d for d in copy["descriptions"] if len(d) <= 90][:4]

    shop = ((ctx.snapshot or {}).get("shop", {}).get("primaryDomain") or {}).get("url", "")
    final_url = product.get("onlineStoreUrl") or (f"{shop}/products/{product.get('handle')}" if shop else "")
    final_url += ("&" if "?" in final_url else "?") + urlencode(
        {"utm_source": "google", "utm_medium": "cpc", "utm_campaign": f"uplift-{ctx.run_id[:12]}"})
    types = [t.strip() for t in ctx.get("campaign_types", "search").split(",")]
    split = {"search": 0.6, "shopping": 0.4} if len(types) > 1 else {types[0]: 1.0}
    campaigns = []
    rows = []
    name = product.get("title") or "Product"
    if "search" in types:
        c = {"name": f"Uplift · {name} · Search", "type": "Search", "daily_budget": round(daily * split["search"], 2),
             "bid_strategy": "Maximize clicks", "max_cpc": max_cpc}
        campaigns.append(c)
        for cluster in sorted({k["cluster"] for k in affordable}):
            group = [k for k in affordable if k["cluster"] == cluster]
            ag = f"{cluster}"[:60]
            for k in group:
                match = "Exact" if k["role"] == "ads_exact" else "Phrase"
                rows.append({"Campaign": c["name"], "Campaign Type": "Search", "Campaign Status": "Paused",
                             "Budget": c["daily_budget"], "Bid Strategy Type": c["bid_strategy"], "Ad Group": ag,
                             "Max CPC": max_cpc, "Keyword": k["keyword"], "Criterion Type": match})
            ad = {"Campaign": c["name"], "Ad Group": ag, "Final URL": final_url, "Ad type": "Responsive search ad"}
            ad |= {f"Headline {i + 1}": h for i, h in enumerate(headlines)}
            ad |= {f"Description {i + 1}": d for i, d in enumerate(descriptions)}
            rows.append(ad)
        for n in negatives:
            rows.append({"Campaign": c["name"], "Keyword": n, "Criterion Type": "Negative Phrase"})
    if "shopping" in types:
        campaigns.append({"name": f"Uplift · {name} · Performance Max", "type": "Performance Max",
                          "daily_budget": round(daily * split["shopping"], 2), "bid_strategy": "Maximize conversion value",
                          "target_roas": round(price / target_cpa, 2), "long_headline": copy["long_headline"][:90]})
        rows.append({"Campaign": campaigns[-1]["name"], "Campaign Type": "Performance Max", "Campaign Status": "Paused",
                     "Budget": campaigns[-1]["daily_budget"], "Bid Strategy Type": "Maximize conversion value",
                     "Target ROAS": f"{campaigns[-1]['target_roas'] * 100:.0f}%", "Final URL": final_url})

    cols = sorted({k for r in rows for k in r}, key=lambda c: (c not in ("Campaign", "Campaign Type"), c))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    economics = {"price": price, "margin": round(margin, 4), "breakeven_cpa": round(breakeven_cpa, 2),
                 "target_cpa": round(target_cpa, 2), "conversion_rate": cvr, "cvr_source":
                 "merchant" if ctx.get("conversion_rate") else "category default (connect GA4 for real data)",
                 "max_cpc": max_cpc, "monthly_budget": budget, "daily_budget": daily}
    out.artifact("unit_economics.json", economics)
    out.artifact("google_ads_editor.csv", buf.getvalue(), "text/csv")
    out.artifact("ad_copy.json", {"headlines": headlines, "descriptions": descriptions,
                                  "long_headline": copy["long_headline"]})
    out.artifact("ads_plan.md", "# Google Ads plan (all campaigns paused)\n\n" + "\n".join(
        f"- **{c['name']}** · {c['type']} · {c['daily_budget']}/day" for c in campaigns)
        + f"\n\nBreak-even CPA {breakeven_cpa:.2f}; max CPC {max_cpc}.", "text/markdown")
    out.artifact("tracking_checklist.md", "- GA4 purchase conversion imported into Google Ads\n"
                 "- Auto-tagging on (gclid)\n- UTM campaign matches the plan\n", "text/markdown")
    out.bundle = {"economics": economics, "campaigns": campaigns,
                  "keywords": [{"keyword": k["keyword"], "match": "exact" if k["role"] == "ads_exact" else "phrase",
                                "cpc": k.get("cpc")} for k in affordable],
                  "negatives": negatives, "headlines": headlines, "descriptions": descriptions,
                  "final_url": final_url, "shop_url": shop}
    return out.finalize(
        f"**Break-even CPA** {breakeven_cpa:.2f} · **max CPC** {max_cpc} · **budget** {budget}/month\n\n"
        + "\n".join(f"- {c['name']} ({c['daily_budget']}/day, paused)" for c in campaigns)
        + f"\n\n{len(affordable)} keywords, {len(negatives)} negatives, {len(headlines)} headlines. "
          "Import the CSV in Google Ads Editor; everything starts paused.")
