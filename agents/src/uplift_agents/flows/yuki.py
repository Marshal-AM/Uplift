"""Yuki — Localization & Transcreation Specialist: one locale per run."""

import re

from kodosumi.core import forms as F
from uplift_core import llm

from .. import tools
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Source copy (skip if your store is connected)", name="source_copy"),
    F.InputText(label="Target locale (e.g. de, ja, fr)", name="target_locale", required=True),
    F.InputText(label="Target market (country code, e.g. DE, JP)", name="target_market", required=True),
    F.InputArea(label="Locked terms kept verbatim (one per line)", name="locked_terms"),
    F.InputArea(label="Local keywords (optional, one per line)", name="local_keywords"),
    F.InputText(label="Market notes: tone, formality (optional)", name="market_notes"),
]

KEYS = ["title", "body_html", "meta_title", "meta_description"]
TRANSLATABLE = """query($id: ID!) { translatableResource(resourceId: $id) {
  translatableContent { key value digest locale } } }"""


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("yuki", "Yuki", ctx)
    locale = ctx.get("target_locale").lower()
    market = ctx.get("target_market").upper()
    locked = ctx.lines("locked_terms")
    product = ctx.product

    source: dict[str, dict] = {}
    if product and ctx.read_token:
        tracer.markdown_sync("**Yuki** · reading translatable content")
        enabled = tools.store_query(ctx.read_token, "{ shopLocales { locale published } }")["shopLocales"]
        if locale not in {loc["locale"].split("-")[0] for loc in enabled}:
            raise RuntimeError(f"INPUT_MISSING: enable the '{locale}' language in your store settings first")
        content = tools.store_query(ctx.read_token, TRANSLATABLE, {"id": product["id"]})
        for item in content["translatableResource"]["translatableContent"]:
            if item["key"] in KEYS and item["value"]:
                source[item["key"]] = {"value": item["value"], "digest": item["digest"]}
    else:
        text = ctx.get("source_copy", "")
        title, _, body = text.partition("\n")
        source = {"title": {"value": title, "digest": None}, "body_html": {"value": body, "digest": None}}
    if not source:
        raise RuntimeError("INPUT_MISSING: no source copy to localize")

    tracer.markdown_sync(f"Finding {market} search terms")
    kai = ctx.upstream_artifact("kai", "keyword_map.json")
    seeds = [kai["primary"], *kai["secondary"][:4]] if kai else [source["title"]["value"]]
    local = ctx.lines("local_keywords")
    if not local:
        seeds_local = tools.translate(seeds, locale)
        local = list(dict.fromkeys(s for seed in seeds_local[:3]
                                   for s in tools.google_autocomplete(seed, market, locale.split("-")[0])))[:10] \
            or seeds_local
    primary_local = local[0]

    tracer.markdown_sync("Transcreating")
    keys = list(source)
    final = llm.structured(
        f"Transcreate this product copy for {market} shoppers in '{locale}'. Keep these terms exactly: {locked}. "
        f"Use the local primary keyword '{primary_local}' in the title, meta title/description and first paragraph; "
        f"weave in: {local[1:6]}. Convert units/date formats. Keep HTML structure. Notes: {ctx.get('market_notes', '-')}.\n"
        "Limits: title ≤70, meta_title ≤60, meta_description ≤155 characters.\n"
        + "\n".join(f"[{k}] SOURCE: {source[k]['value'][:6000]}" for k in keys),
        {"type": "object", "properties": {k: {"type": "string"} for k in keys}, "required": keys}, max_tokens=6000)

    back = tools.translate([final[k] for k in keys], "EN-US" if locale != "en" else "DE", html=True)
    drift = llm.structured(
        "Compare each original with its back-translation. Flag keys whose meaning changed materially.\n"
        + "\n".join(f"[{k}] ORIGINAL: {source[k]['value'][:2000]}\n[{k}] BACK: {b[:2000]}" for k, b in zip(keys, back)),
        {"type": "object", "properties": {"drifted": {"type": "array", "items": {"type": "string"}}},
         "required": ["drifted"]})["drifted"]

    if product:
        out.changeset.append({"op": "translations.register", "resource_id": product["id"], "translations": [
            {"locale": locale, "key": k, "value": final[k], "translatableContentDigest": source[k]["digest"]}
            for k in keys if source[k]["digest"]]})
    out.artifact(f"translations_{locale}.json", {k: final[k] for k in keys})
    out.artifact(f"local_keywords_{locale}.csv", "keyword\n" + "\n".join(local), "text/csv")
    out.artifact("qa_report.md", f"Back-translation drift: {', '.join(drift) or 'none'}", "text/markdown")
    out.bundle = {"locale": locale, "market": market,
                  "locked_terms": locked, "primary_local": primary_local, "local_keywords": local[:3],
                  "source": {k: {"value": source[k]["value"][:6000], "digest": source[k]["digest"]} for k in keys},
                  "translated": {k: final[k][:6000] for k in keys}}
    plain = re.sub("<[^>]+>", " ", final.get("body_html", ""))[:160]
    return out.finalize(f"**{locale.upper()} title:** {final.get('title')}\n\n{plain}…\n\n"
                        f"Local primary keyword: **{primary_local}** · drift flags: {', '.join(drift) or 'none'}")
