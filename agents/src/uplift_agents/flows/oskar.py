"""Oskar — Catalog, Collections & Shopping Feed Specialist."""

import csv
import io
import json
import re

from kodosumi.core import forms as F
from uplift_core import llm

from ..runtime import Context, Deliverable, need_store, tools

FIELDS = [
    F.InputArea(label="Attributes not in your store yet: material, color, size, age group, gender, GTIN/MPN/brand",
                name="attributes"),
    F.Select(label="Collections", name="collection_strategy", option=[
        F.InputOption(name="existing", label="Use existing collections only", value=True),
        F.InputOption(name="create", label="Create a category collection if useful")]),
]

GOOGLE_REQUIRED = ["id", "title", "description", "link", "image_link", "price", "availability", "brand",
                   "gtin_or_mpn", "condition", "google_product_category"]


def gtin_valid(code: str) -> bool:
    digits = re.sub(r"\D", "", code or "")
    if len(digits) not in (8, 12, 13, 14):
        return False
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("oskar", "Oskar", ctx)
    token = need_store(ctx)
    product = ctx.product
    if not product:
        raise RuntimeError("INPUT_MISSING: choose a product from your connected store")
    kai = ctx.upstream_artifact("kai", "keyword_map.json")
    text = f"{product['title']}\n{re.sub('<[^>]+>', ' ', product.get('descriptionHtml') or '')[:2000]}\n" \
           f"Extra attributes: {ctx.get('attributes', '')}"

    tracer.markdown_sync("**Oskar** · finding the right product category")
    terms = llm.structured(f"Product:\n{text}\nGive 3 short search terms for its product category, starting with the "
                           "plain generic name of the product (e.g. 'water bottle', 'sofa', 'running shoes') without "
                           "materials or features.",
                           {"type": "object", "properties": {"terms": {"type": "array", "items": {"type": "string"}}},
                            "required": ["terms"]}, purpose="Search terms for the product's category")["terms"][:3]
    candidates = []
    for term in terms:
        found = tools.store_query(token, "query($q: String!) { taxonomy { categories(search: $q, first: 10) "
                                         "{ nodes { id fullName } } } }", {"q": term})
        candidates += found["taxonomy"]["categories"]["nodes"]
    candidates = list({c["id"]: c for c in candidates}.values())
    pick = llm.structured(
        f"Product:\n{text}\nPick the single best category id from:\n" + "\n".join(f"{c['id']}: {c['fullName']}"
                                                                                for c in candidates)
        + "\nAlso recommend attribute values (name → value) for this category and a concise product type.",
        {"type": "object", "properties": {"category_id": {"type": "string"}, "product_type": {"type": "string"},
                                          "attributes": {"type": "object", "additionalProperties": {"type": "string"}}},
         "required": ["category_id", "product_type"]}, purpose="Choosing the Google product category")
    category = next((c for c in candidates if c["id"] == pick["category_id"]), candidates[0] if candidates else None)

    tracer.markdown_sync("Reviewing tags, identifiers and collections")
    vocab = [e["node"] for e in tools.store_query(token, "{ productTags(first: 250) { edges { node } } }")
             ["productTags"]["edges"]]
    tag_pick = llm.structured(
        f"Product:\n{text}\nKeyword clusters: {sorted({k['cluster'] for k in kai['keywords']})[:20] if kai else '-'}\n"
        f"Existing store tags: {vocab}\nSuggest up to 8 taxonomy/merchandising tags. Reuse existing tags exactly "
        "when they fit; avoid case or plural variants of existing tags.",
        {"type": "object", "properties": {"tags": {"type": "array", "items": {"type": "string"}}}, "required": ["tags"]}, purpose="Suggesting merchandising tags")
    lower_vocab = {t.lower(): t for t in vocab}
    tags = [lower_vocab.get(t.lower(), t) for t in tag_pick["tags"]]
    tags = [t for t in dict.fromkeys(tags) if t not in product.get("tags", [])][:8]

    variants = product.get("variants", {}).get("nodes", [])
    barcode_rows = [{"variant_id": v["id"], "sku": v.get("sku"), "barcode": v.get("barcode") or "",
                     "valid": gtin_valid(v.get("barcode") or "")} for v in variants]

    collections = tools.store_query(token, "{ collections(first: 100) { nodes { id title handle "
                                           "ruleSet { appliedDisjunctively } productsCount { count } } } }")[
        "collections"]["nodes"]
    current = {c["id"] for c in product.get("collections", {}).get("nodes", [])}
    manual = [c for c in collections if not c["ruleSet"] and c["id"] not in current]
    plan = llm.structured(
        f"Product:\n{text}\nManual collections it is not in yet: {[(c['id'], c['title']) for c in manual]}\n"
        f"Collection strategy: {ctx.get('collection_strategy', 'existing')}\nKeyword clusters: "
        f"{sorted({k['cluster'] for k in kai['keywords']})[:15] if kai else '-'}\n"
        "Pick only collections of this same kind of product (a collection named after another product type, e.g. "
        "bottles for a tumbler, is wrong even when they share a material). Return none if nothing fits. If the "
        "strategy allows creating one and none fit, "
        "propose one category collection with an SEO title (≤60) and description (≤155).",
        {"type": "object", "properties": {
            "add_to": {"type": "array", "items": {"type": "string"}},
            "create": {"type": "object", "properties": {"title": {"type": "string"}, "seo_title": {"type": "string"},
                                                        "seo_description": {"type": "string"},
                                                        "description_html": {"type": "string"}}}},
         "required": ["add_to"]}, purpose="Choosing collections to add the product to")
    add_to = [cid for cid in plan["add_to"] if cid in {c["id"] for c in manual}]

    tracer.markdown_sync("Linking related and complementary products")
    catalog = tools.store_query(token, "{ products(first: 150, query: \"status:active\") { nodes { id title "
                                       "productType tags totalInventory } } }")["products"]["nodes"]
    catalog = [p for p in catalog if p["id"] != product["id"] and (p.get("totalInventory") or 0) > 0]
    links = llm.structured(
        f"Product:\n{product['title']}\nCatalog: {[(p['id'], p['title'], p['productType']) for p in catalog]}\n"
        "Pick up to 4 related (alternatives) and up to 4 complementary (bought together) products by id.",
        {"type": "object", "properties": {"related": {"type": "array", "items": {"type": "string"}},
                                          "complementary": {"type": "array", "items": {"type": "string"}}},
         "required": ["related", "complementary"]}, purpose="Picking related and complementary products")
    ids = {p["id"] for p in catalog}
    related = [i for i in links["related"] if i in ids][:4]
    complementary = [i for i in links["complementary"] if i in ids][:4]

    fields = {}
    if category and (product.get("category") or {}).get("id") != category["id"]:
        fields["category"] = category["id"]
    if pick["product_type"] and pick["product_type"] != product.get("productType"):
        fields["productType"] = pick["product_type"]
    if fields:
        out.changeset.append({"op": "product.update", "product_id": product["id"], "fields": fields})
    if tags:
        out.changeset.append({"op": "product.taxonomy_tags_add", "product_id": product["id"], "tags": tags})
    for cid in add_to:
        out.changeset.append({"op": "collection.add_products", "collection_id": cid, "product_ids": [product["id"]]})
    if ctx.get("collection_strategy") == "create" and plan.get("create") and not add_to:
        c = plan["create"]
        out.changeset.append({"op": "collection.create", "input": {
            "title": c["title"], "descriptionHtml": c.get("description_html", ""),
            "seo": {"title": c.get("seo_title", "")[:60], "description": c.get("seo_description", "")[:155]},
            "products": [product["id"]]}})
    mfs = []
    ns = "shopify--discovery--product_recommendation"
    if related:
        mfs.append({"namespace": ns, "key": "related_products", "type": "list.product_reference",
                    "value": json.dumps(related)})
    if complementary:
        mfs.append({"namespace": ns, "key": "complementary_products", "type": "list.product_reference",
                    "value": json.dumps(complementary)})
    if mfs:
        out.changeset.append({"op": "metafields.set", "owner_id": product["id"], "metafields": mfs})

    feed = {"id": product["id"].split("/")[-1], "title": product["title"],
            "google_product_category": category["fullName"] if category else "",
            "product_type": pick["product_type"], "brand": product.get("vendor"),
            "gtin_or_mpn": next((v["barcode"] for v in variants if gtin_valid(v.get("barcode") or "")), ""),
            "condition": "new"}
    missing = [f for f in GOOGLE_REQUIRED if f in feed and not feed[f]]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(feed))
    w.writeheader()
    w.writerow(feed)
    bbuf = io.StringIO()
    bw = csv.DictWriter(bbuf, fieldnames=["variant_id", "sku", "barcode", "valid"])
    bw.writeheader()
    bw.writerows(barcode_rows)

    out.artifact("catalog_changes.json", {"category": category, "product_type": pick["product_type"],
                                          "recommended_attributes": pick.get("attributes", {}), "tags": tags,
                                          "related": related, "complementary": complementary})
    out.artifact("collections_plan.md", "\n".join([f"- add to {c['title']}" for c in manual if c["id"] in add_to])
                 or "No new collections needed.", "text/markdown")
    out.artifact("feed_report.json", {"missing_google_fields": missing, "barcodes": barcode_rows})
    out.artifact("google_supplemental.csv", buf.getvalue(), "text/csv")
    out.artifact("barcode_fixes.csv", bbuf.getvalue(), "text/csv")
    out.bundle = {"category_id": category["id"] if category else None, "category_candidates": [c["id"] for c in candidates],
                  "tags": tags, "existing_tags": product.get("tags", []), "related": related,
                  "complementary": complementary, "add_to": add_to,
                  "new_collection": plan.get("create") if any(o["op"] == "collection.create" for o in out.changeset)
                  else None, "feed": feed}
    return out.finalize(
        f"**Category:** {category['fullName'] if category else 'unchanged'} · **Type:** {pick['product_type']}\n\n"
        f"{len(tags)} tags, {len(add_to)} collections, {len(related)} related and {len(complementary)} "
        f"complementary products linked. Google feed fields missing: {', '.join(missing) or 'none'}.")
