"""CRE ↔ Python lockstep: canonical change hashes, rule hits and listing scores must match exactly.

Run: uv run python e2e/cre_parity.py   (needs bun and `bun install` in cre/uplift-clearing)
"""

import json
import subprocess
from pathlib import Path

from uplift_core import rules
from uplift_core.hashing import change_hash
from uplift_core.score import score

ROOT = Path(__file__).resolve().parents[1]

PRODUCT = {
    "title": "Ceramic Pour-Over Coffee Dripper — Size 02, Matte White",
    "handle": "ceramic-pour-over-dripper-02",
    "descriptionHtml": "<h2>Brew better</h2><p>" + "Slow, even extraction for a clean cup. " * 30 + "</p>"
                       "<ul><li>Fits size 02 filters</li><li>Free shipping and easy returns</li><li>Lifetime warranty"
                       "</li></ul><p>The best dripper ever, 100% safe and eco-friendly.</p>",
    "seo": {"title": "Ceramic Pour-Over Coffee Dripper | Size 02",
            "description": "Hand-glazed ceramic pour-over dripper for size 02 filters. Even extraction, clean cups, "
                           "dishwasher safe."},
    "tags": ["coffee", "pour over", "ceramic"], "productType": "Coffee Drippers", "vendor": "Acme",
    "category": {"fullName": "Home & Garden > Kitchen > Coffee"},
    "media": {"nodes": [{"mediaContentType": "IMAGE", "alt": "White ceramic dripper", "image": {"width": 2048}},
                        {"mediaContentType": "IMAGE", "alt": "", "image": {"width": 800}}]},
    "metafields": {"nodes": [{"namespace": "custom", "key": "faq",
                              "value": json.dumps([{"q": "Shipping?", "a": "2 days"}] * 3)},
                             {"namespace": "reviews", "key": "rating_count", "value": "12"},
                             {"namespace": "shopify", "key": "color-pattern", "value": "[]"}]},
    "variants": {"nodes": [{"barcode": "0012345678905"}]}, "collections": {"nodes": [{"id": "1"}]},
}
CHANGESET = [
    {"op": "product.update", "product_id": "gid://shopify/Product/1",
     "fields": {"title": "Café Dripper ☕ — “Size 02”", "seo": {"title": "x", "description": "y"}}},
    {"op": "metafields.set", "owner_id": "gid://shopify/Product/1", "metafields": [
        {"namespace": "custom", "key": "faq", "type": "json", "value": json.dumps({"price": 19.9, "n": 1e21})}]},
    {"op": "discount.create", "input": {"code": "SPRING10", "percentage": 0.1, "startsAt": "2026-11-01T00:00:00Z"}},
]
CASES = [
    {"product": PRODUCT, "keywords": {"primary": "pour over coffee dripper", "secondary": ["ceramic", "size 02",
                                                                                       "filters", "clean cup"]},
     "changeset": CHANGESET,
     "segments": [{"location": "title", "text": PRODUCT["title"]},
                  {"location": "ad.h1", "text": "BUY NOW!! Best Hario alternative", "kind": "ad"}],
     "brand_terms": ["Hario"]},
    {"product": {**PRODUCT, "seo": {}, "media": {"nodes": []}, "tags": []}, "keywords": None, "changeset": [],
     "segments": [{"location": "description", "text": "Clinically proven, cures anxiety. Ends tonight!"}],
     "brand_terms": []},
]


def main() -> None:
    out = subprocess.run(["bun", "parity.ts"], input=json.dumps(CASES), capture_output=True, text=True, check=True,
                         cwd=ROOT / "cre" / "uplift-clearing").stdout
    ts = json.loads(out)
    for i, (case, got) in enumerate(zip(CASES, ts, strict=True)):
        py_score = score(case["product"], case["keywords"])
        py_hits = [f"{h.rule_id}@{h.location}" for h in rules.scan(case["segments"], case["brand_terms"])]
        assert got["canonical_hash"] == change_hash(case["changeset"]), f"case {i}: change hash differs"
        assert got["score"]["sections"] == py_score["sections"], f"case {i}: {got['score']} != {py_score['sections']}"
        assert got["score"]["deterministic"] == py_score["deterministic"], f"case {i}: total differs"
        assert got["hits"] == py_hits, f"case {i}: {got['hits']} != {py_hits}"
        print(f"case {i}: hash ✓ score {py_score['deterministic']} ✓ hits {len(py_hits)} ✓")


if __name__ == "__main__":
    main()
