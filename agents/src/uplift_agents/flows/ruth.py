"""Ruth — Claims & Compliance Reviewer. The rule engine decides; the LLM only writes rewrites."""

import re

from kodosumi.core import forms as F
from uplift_core import llm, rules

from .. import tools
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Copy, HTML or ad text to review", name="assets"),
    F.InputArea(label="Page or image URLs to review (one per line)", name="asset_urls"),
    F.InputText(label="Markets (comma separated, e.g. US, EU, UK)", name="markets", value="US,EU", required=True),
    F.InputText(label="Category (general, supplements, cosmetics, food contact, kids, electronics)", name="category",
                value="general", required=True),
    F.InputArea(label="Your trademarks (one per line, optional)", name="own_trademarks"),
    F.InputArea(label="Competitor brands (one per line, optional)", name="competitor_brands"),
    F.InputArea(label="Substantiation you hold: certificates, test reports (optional)", name="substantiation"),
]

IMAGE_EXT = re.compile(r"\.(png|jpe?g|webp)(\?|$)", re.IGNORECASE)


def segments_from_changeset(changeset: list[dict]) -> list[dict]:
    segs = []
    for op in changeset:
        name = op["op"]
        if name == "product.update":
            f = op["fields"]
            for k in ("title", "descriptionHtml"):
                if f.get(k):
                    segs.append({"location": f"product.{k}", "text": re.sub("<[^>]+>", " ", f[k]), "kind": "copy"})
            if f.get("seo"):
                segs.append({"location": "product.seo", "text": " ".join(f["seo"].values()), "kind": "copy"})
        elif name == "metafields.set":
            for m in op["metafields"]:
                if m["namespace"] == "custom":
                    segs.append({"location": f"metafield.{m['key']}", "text": m["value"], "kind": "copy"})
        elif name == "translations.register":
            for t in op["translations"]:
                segs.append({"location": f"translation.{t['locale']}.{t['key']}",
                             "text": re.sub("<[^>]+>", " ", t["value"]), "kind": "copy"})
        elif name == "article.create":
            segs.append({"location": "article", "text": re.sub("<[^>]+>", " ", op["input"]["body"]), "kind": "copy"})
        elif name == "media.add":
            segs += [{"location": f"media.alt.{i}", "text": m.get("alt", ""), "kind": "copy"}
                     for i, m in enumerate(op["media"])]
        elif name == "discount.create":
            segs.append({"location": "discount.title", "text": op["input"]["title"], "kind": "copy"})
    return segs


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("ruth", "Ruth", ctx)
    segments: list[dict] = list(ctx.envelope.get("review_segments", []))
    segments += segments_from_changeset(ctx.envelope.get("review_changeset", []))
    if ctx.get("assets"):
        segments.append({"location": "assets", "text": re.sub("<[^>]+>", " ", ctx.get("assets")), "kind": "copy"})
    product = ctx.product or {}
    if not segments and product:  # nothing pasted: review the live listing from the connected store
        seo = product.get("seo") or {}
        segments += [{"location": f"product.{k}", "text": re.sub("<[^>]+>", " ", v), "kind": "copy"}
                     for k, v in (("title", product.get("title")), ("descriptionHtml", product.get("descriptionHtml")),
                                  ("seo.title", seo.get("title")), ("seo.description", seo.get("description"))) if v]

    tracer.markdown_sync("**Ruth** · extracting text from pages and images")
    for url in ctx.lines("asset_urls"):
        if IMAGE_EXT.search(url):
            segments.append({"location": url, "text": tools.ocr(tools.fetch_bytes(url)), "kind": "shopping_image"})
        else:
            segments.append({"location": url, "text": tools.scrape(url)["markdown"][:20000], "kind": "copy"})
    if not segments:
        raise RuntimeError("INPUT_MISSING: give copy, URLs or images to review")

    substantiated: set[str] = set()
    if ctx.get("substantiation"):
        ids = [r["id"] for r in rules.load()["rules"] if r.get("substantiable")]
        substantiated = set(llm.structured(
            f"Which of these rule ids does the merchant's evidence substantiate? Evidence:\n{ctx.get('substantiation')}\n"
            f"Rules: {[(r['id'], r['message']) for r in rules.load()['rules'] if r['id'] in ids]}",
            {"type": "object", "properties": {"rule_ids": {"type": "array", "items": {"type": "string"}}},
             "required": ["rule_ids"]})["rule_ids"]) & set(ids)

    own = {t.lower() for t in ctx.lines("own_trademarks")}
    brands = [b for b in ctx.lines("competitor_brands")
              + ((ctx.upstream_artifact("rafael", "competitor_set.json") or {}).get("brands", []))
              if b and b.lower() not in own]
    tracer.markdown_sync(f"Checking {len(segments)} text segments against uplift-rules v{rules.load()['version']}")
    hits = rules.scan(segments, brands, substantiated)

    rewrites = []
    if hits:
        proposed = llm.structured(
            "Rewrite each flagged excerpt so it keeps the selling point but breaks no rule. Do not invent facts.\n"
            + "\n".join(f"[{i}] {h.rule_id} ({h.message}): \"{h.excerpt}\"" for i, h in enumerate(hits)),
            {"type": "object", "properties": {"rewrites": {"type": "array", "items": {"type": "object", "properties": {
                "index": {"type": "integer"}, "rewrite": {"type": "string"}}, "required": ["index", "rewrite"]}}},
             "required": ["rewrites"]})["rewrites"]
        for r in proposed:
            if 0 <= r["index"] < len(hits):
                h = hits[r["index"]]
                clean = not rules.scan([{"location": h.location, "text": r["rewrite"]}], brands, substantiated)
                rewrites.append({"rule_id": h.rule_id, "location": h.location, "excerpt": h.excerpt,
                                 "rewrite": r["rewrite"], "passes": clean})
    high = [h for h in hits if h.severity == "high"]
    fixed = {(r["rule_id"], r["location"]) for r in rewrites if r["passes"]}
    blocked = any((h.rule_id, h.location) not in fixed for h in high)

    report = [f"# Compliance review — {'BLOCKED' if blocked else 'pass with fixes' if hits else 'pass'}",
              f"Markets: {ctx.get('markets')} · Category: {ctx.get('category')} · rules v{rules.load()['version']}", ""]
    for h in hits:
        rw = next((r["rewrite"] for r in rewrites if r["rule_id"] == h.rule_id and r["location"] == h.location), "")
        report.append(f"- **{h.severity.upper()} {h.rule_id}** in `{h.location}`: {h.message}\n  > {h.excerpt}\n"
                      + (f"  ✏️ {rw}" if rw else ""))
    out.artifact("compliance_report.md", "\n".join(report), "text/markdown")
    out.artifact("compliance_report.json", {"blocked": blocked, "hits": [h.__dict__ for h in hits],
                                            "rewrites": rewrites, "rules_version": rules.load()["version"]})
    out.bundle = {"segments": segments, "brand_terms": brands, "substantiated": sorted(substantiated),
                  "hits": [{"rule_id": h.rule_id, "location": h.location, "severity": h.severity} for h in hits],
                  "rewrites": rewrites, "blocked": blocked}
    out.self_checks = {"blocked": blocked, "high": len(high),
                       "unresolved": [{"rule_id": h.rule_id, "location": h.location} for h in high
                                      if (h.rule_id, h.location) not in fixed]}
    return out.finalize(f"**{'Blocked' if blocked else 'Pass'}** · {len(hits)} findings "
                        f"({len(high)} high), {sum(r['passes'] for r in rewrites)} safe rewrites.")
