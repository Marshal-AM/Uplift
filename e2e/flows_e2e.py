"""Run one specialist flow against the real services and check its Deliverable Manifest.

    railway run --service kodosumi -- uv run python e2e/flows_e2e.py kai
    railway run --service kodosumi -- uv run python e2e/flows_e2e.py clara --upstream kai=<result_hash> priya=<hash>

(`railway run` injects Kodosumi's service keys locally; nothing is printed.) Upstream hashes come from earlier runs.
"""

import argparse
import json
import time

import httpx
from uplift_agents.flows import clara, iris, kai, leo, marcus, oskar, priya, quinn, rafael, ruth, sasha, yuki
from uplift_core.hashing import result_hash, sha256_hex

PRODUCT = "Bamboo-lid insulated stainless steel water bottle, 500 ml"
FACTS = ("Double-wall vacuum-insulated 18/8 stainless steel bottle; natural bamboo lid with leak-proof silicone seal; "
         "500 ml; keeps drinks cold 24 hours and hot 12 hours; BPA-free; fits most cup holders; hand-wash the lid; "
         "price 34 USD; 1-year warranty.")
COPY = ("Stagg X Pour-Over Dripper\n<p>The best dripper in the world. 100% safe and eco-friendly. Double-wall "
        "stainless steel keeps heat steady for a balanced cup. Fits size 02 filters.</p>")
FLOWS = {"kai": kai, "rafael": rafael, "priya": priya, "marcus": marcus, "clara": clara, "iris": iris,
         "oskar": oskar, "yuki": yuki, "leo": leo, "sasha": sasha, "ruth": ruth, "quinn": quinn}
INPUTS = {
    "kai": {"product": PRODUCT, "market_country": "US", "language": "en", "seed_keywords": "bamboo water bottle",
            "competitor_domains": "hydroflask.com\nyeti.com"},
    "rafael": {"product": PRODUCT, "market_country": "US", "language": "en", "price_point": "34", "max_competitors": "6"},
    "priya": {"category": "insulated bamboo water bottle", "market_country": "US", "language": "en",
              "my_product": PRODUCT, "competitor_domains": "hydroflask.com", "include_social": "yes"},
    "marcus": {"product": PRODUCT, "goal": "launch", "margin_floor_pct": "35", "unit_cost": "11", "price": "34",
               "shipping_cost": "4", "market_country": "US"},
    "clara": {"current_copy": COPY, "product_facts": FACTS, "target_keywords": "pour over dripper\nstainless steel dripper",
              "audience": "home coffee brewers", "locale": "en-US"},
    "iris": {"image_urls": "https://cdn.shopify.com/s/files/1/0308/4763/1493/files/IMG_3459.jpg\nhttps://cdn.shopify.com/s/files/1/0308/4763/1493/files/IMG_3461.jpg\nhttps://cdn.shopify.com/s/files/1/0308/4763/1493/files/IMG_3464.jpg\nhttps://cdn.shopify.com/s/files/1/0308/4763/1493/files/IMG_3470.jpg",
             "product_name": "Hario V60 Cookies & Cream dripper", "category": "coffee equipment", "lifestyle_count": "1"},
    "yuki": {"source_copy": COPY, "target_locale": "de", "target_market": "DE", "locked_terms": "Stagg\nFellow", "local_keywords": "pour over handfilter\nkaffee handfilter edelstahl\nhandfilter kaffee"},
    "leo": {"product_facts": FACTS, "deliverables": "faq,email,social", "audience": "home coffee brewers"},
    "sasha": {"product_facts": FACTS, "campaign_types": "search", "budget_cap": "600", "margin_pct": "55",
              "market_country": "US"},
    "ruth": {"assets": COPY, "markets": "US,EU", "category": "kitchen", "competitor_brands": "Hario\nKalita"},
    "quinn": {"product_url": "https://fellowproducts.com/products/stagg-x-pour-over-dripper", "mode": "audit",
              "market_country": "US"},
}


class Tracer:
    def markdown_sync(self, text: str) -> None:
        print(f"  · {text.splitlines()[0][:110]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("role", choices=sorted(FLOWS))
    ap.add_argument("--upstream", nargs="*", default=[], help="role=result_hash")
    a = ap.parse_args()
    envelope = {"job_or_task_id": f"e2e-{a.role}-{int(time.time())}", "fields": INPUTS.get(a.role, {}),
                "upstream": dict(u.split("=", 1) for u in a.upstream)}
    started = time.time()
    text = FLOWS[a.role].run({**INPUTS.get(a.role, {}), "context": json.dumps(envelope)}, Tracer())
    manifest = json.loads(text)
    bundle = httpx.get(manifest["verification_bundle"]["url"], timeout=60).text
    assert sha256_hex(bundle) == manifest["verification_bundle"]["sha256"], "bundle hash mismatch"
    assert manifest["role"] == a.role
    print(f"\n{a.role} finished in {time.time() - started:.0f}s · result_hash {result_hash(text)}")
    print(f"artifacts: {[x['name'] for x in manifest['artifacts']]}")
    print(f"changeset ops: {[op['op'] for op in manifest['changeset']]} · bundle {len(bundle) // 1024} KB")
    print(f"self_checks: {json.dumps(manifest['self_checks'])[:300]}")
    print(f"\n{manifest['summary_md'][:1500]}")


if __name__ == "__main__":
    main()
