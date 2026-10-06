"""Clara — Product Page Copywriter: title, description, SEO title/meta, handle, tags. Facts only."""

import html
import re
from concurrent.futures import ThreadPoolExecutor

from kodosumi.core import forms as F
from uplift_core import llm

from .. import tools
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Current copy or product URL (skip if your store is connected)", name="current_copy"),
    F.InputArea(label="Product facts: specs, materials, dimensions, certifications, care, warranty",
                name="product_facts"),
    F.InputArea(label="Target keywords (one per line, optional)", name="target_keywords"),
    F.InputText(label="Audience (optional)", name="audience"),
    F.InputArea(label="Brand voice: samples, do's and don'ts (optional)", name="brand_voice"),
    F.InputArea(label="Forbidden words (optional)", name="forbidden_words"),
    F.InputText(label="Language/locale", name="locale", value="en-US", required=True),
]

VARIANT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "seo_title": {"type": "string"}, "seo_description": {"type": "string"},
        "handle": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}},
        "blocks": {"type": "array", "items": {"type": "object", "properties": {
            "type": {"type": "string", "enum": ["h2", "p", "li"]}, "text": {"type": "string"},
            "fact_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["type", "text", "fact_ids"]}},
    },
    "required": ["title", "seo_title", "seo_description", "handle", "tags", "blocks"],
}


def to_html(blocks: list[dict]) -> str:
    parts, in_list = [], False
    for b in blocks:
        if b["type"] == "li" and not in_list:
            parts.append("<ul>")
            in_list = True
        if b["type"] != "li" and in_list:
            parts.append("</ul>")
            in_list = False
        parts.append(f"<{b['type']}>{html.escape(b['text'])}</{b['type']}>")
    if in_list:
        parts.append("</ul>")
    return "".join(parts)


def rubric(v: dict, primary: str, secondary: list[str], objections: list[str], facts: dict, forbidden: list[str]) -> dict:
    body = " ".join(b["text"] for b in v["blocks"]).lower()
    first100 = " ".join(body.split()[:100])
    claims = [b for b in v["blocks"] if b["type"] in ("p", "li")]
    grounded = sum(1 for b in claims if b["fact_ids"] and all(f in facts for f in b["fact_ids"]))
    s = {
        "title_length": 5 if 20 <= len(v["title"]) <= 70 else 0,
        "seo_title_length": 4 if len(v["seo_title"]) <= 60 else 0,
        "seo_description_length": 4 if 70 <= len(v["seo_description"]) <= 155 else 0,
        "primary_in_title": 5 if primary and primary in v["title"].lower() else 0,
        "primary_in_seo_title": 3 if primary and primary in v["seo_title"].lower() else 0,
        "primary_in_first_100": 3 if primary and primary in first100 else 0,
        "secondary_coverage": 5 if secondary and sum(s in body for s in secondary) >= len(secondary) / 2 else 0,
        "objections_answered": 5 if not objections or sum(o in body for o in objections) >= min(3, len(objections))
        else 0,
        "structure": 4 if any(b["type"] == "h2" for b in v["blocks"]) and
        sum(b["type"] == "li" for b in v["blocks"]) >= 3 else 0,
        "grounded": round(7 * grounded / len(claims), 2) if claims else 0,
    }
    if any(re.search(rf"\b{re.escape(w)}\b", body + v["title"].lower()) for w in forbidden):
        s["forbidden_penalty"] = -45
    return {"items": s, "total": round(sum(s.values()), 2), "grounded_ratio": grounded / len(claims) if claims else 0}


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("clara", "Clara", ctx)
    product = ctx.product or {}
    current = ctx.get("current_copy", "")
    if current.startswith("http"):
        current = tools.scrape(current)["markdown"][:6000]
    if product:
        current = f"{product['title']}\n{re.sub('<[^>]+>', ' ', product.get('descriptionHtml') or '')}"

    tracer.markdown_sync("**Clara** · building the facts ledger")
    facts = {f["id"]: f["fact"] for f in llm.structured(
        f"Extract every verifiable product fact (specs, materials, dimensions, certifications, care, warranty, "
        f"included items). Give each an id F1, F2…\nCurrent copy:\n{current}\nMerchant facts:\n"
        f"{ctx.get('product_facts', '')}",
        {"type": "object", "properties": {"facts": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "fact": {"type": "string"}}, "required": ["id", "fact"]}}}, "required": ["facts"]},
    )["facts"]}
    if len(facts) < 3:
        raise RuntimeError("INPUT_MISSING: add product facts (materials, size, specs) so the copy has no guesses")

    kai = ctx.upstream_artifact("kai", "keyword_map.json")
    if kai:
        primary, secondary = kai["primary"], kai["secondary"][:10]
    elif ctx.lines("target_keywords"):
        primary, secondary = ctx.lines("target_keywords")[0].lower(), [k.lower() for k in ctx.lines("target_keywords")[1:]]
    else:
        tracer.markdown_sync("No keywords given — running a quick keyword pass")
        res = tools.dataforseo("dataforseo_labs/google/keyword_suggestions/live",
                               {"keyword": (product.get("title") or current.split("\n")[0])[:80],
                                "location_code": 2840, "language_code": ctx.get("locale", "en")[:2], "limit": 30})
        ranked = sorted([i for r in res for i in r.get("items") or []],
                        key=lambda i: -((i.get("keyword_info") or {}).get("search_volume") or 0))
        kws = [i["keyword"] for i in ranked[:15]] or [current.split("\n")[0].lower()]
        primary, secondary = kws[0], kws[1:10]
    findings = ctx.upstream_artifact("priya", "findings.json") or []
    objections = [f["aspect"] for f in findings if f["kind"] in ("complaint", "dealbreaker")][:5]
    forbidden = [w.lower() for w in ctx.lines("forbidden_words")]

    tracer.markdown_sync("Writing three variants")
    prompt = (
        f"Write product page copy in {ctx.get('locale', 'en-US')}.\nFacts (cite ids; never claim anything else):\n"
        + "\n".join(f"{k}: {v}" for k, v in facts.items())
        + f"\nPrimary keyword: {primary}\nSecondary keywords: {', '.join(secondary)}\n"
        f"Buyer objections to answer (from competitor reviews): {', '.join(objections) or 'none'}\n"
        f"Audience: {ctx.get('audience', 'general shoppers')}\nBrand voice: {ctx.get('brand_voice', 'clear, warm')}\n"
        f"Never use: {', '.join(forbidden) or '-'}\n"
        "Rules: title ≤70 chars starting with the primary keyword; SEO title ≤60; SEO description 70–155; "
        "handle lowercase-hyphenated ≤60; structure hook → benefits (li) → specs → use cases → objection answers → "
        "care & guarantee; every p/li block lists the fact ids it relies on.")
    styles = ["benefit-led and concise", "story-led and vivid", "spec-led and precise"]
    with ThreadPoolExecutor(3) as pool:
        variants = list(pool.map(lambda st: llm.structured(f"{prompt}\nStyle: {st}", VARIANT_SCHEMA,
                                                           max_tokens=4000, temperature=0.7), styles))
    scored = [(rubric(v, primary.lower(), secondary, objections, facts, forbidden), v) for v in variants]
    best_score, best = max(scored, key=lambda x: x[0]["total"])
    description = to_html(best["blocks"])
    grammar = tools.grammar_issues(re.sub("<[^>]+>", " ", description), ctx.get("locale", "en-US"))

    handle = re.sub(r"[^a-z0-9]+", "-", best["handle"].lower()).strip("-")[:60]
    fields = {"title": best["title"][:70], "descriptionHtml": description,
              "seo": {"title": best["seo_title"][:70], "description": best["seo_description"][:320]}}
    if product.get("handle") and handle and handle != product["handle"]:
        fields["handle"] = handle
    if product.get("id"):
        out.changeset.append({"op": "product.update", "product_id": product["id"], "fields": fields})
        new_tags = [t for t in best["tags"] if t not in product.get("tags", [])][:10]
        if new_tags:
            out.changeset.append({"op": "product.tags_add", "product_id": product["id"], "tags": new_tags})

    out.artifact("copy_variants.json", [{"style": st, "score": sc, **v} for st, (sc, v) in zip(styles, scored)])
    out.artifact("selected_copy.html", f"<h1>{html.escape(best['title'])}</h1>{description}", "text/html")
    out.artifact("facts.json", facts)
    out.artifact("rubric_scores.json", best_score)
    out.self_checks = {"rubric_total": best_score["total"], "grammar_issues": len(grammar)}
    out.bundle = {"title": fields["title"], "seo": fields["seo"], "handle": handle, "blocks": best["blocks"],
                  "facts": facts, "primary": primary, "secondary": secondary, "objections": objections,
                  "forbidden": forbidden, "grammar_issue_count": len(grammar), "locale": ctx.get("locale", "en-US")}
    return out.finalize(f"**Title:** {fields['title']}\n\n**SEO title:** {fields['seo']['title']}\n\n"
                        f"**Meta:** {fields['seo']['description']}\n\nRubric {best_score['total']}/45 · "
                        f"{best_score['grounded_ratio']:.0%} of claims grounded in {len(facts)} facts.")
