"""Listing Score (0–100). Deterministic sections sum to 95; the judge adds up to 5.

Quinn computes it, and CRE recomputes the deterministic part (TypeScript port in cre/) from the
same store snapshot. Keep both implementations in lockstep.
"""

import json
import re
from typing import Any

from . import rules


def _words(html: str) -> list[str]:
    return re.sub(r"<[^>]+>", " ", html or "").split()


def _metafield(product: dict, namespace: str, key: str) -> Any:
    for mf in product.get("metafields", {}).get("nodes", []):
        if mf["namespace"] == namespace and mf["key"] == key:
            try:
                return json.loads(mf["value"])
            except (ValueError, TypeError):
                return mf["value"]
    return None


def _has(text: str, phrase: str) -> bool:
    return phrase.lower() in (text or "").lower()


def score(product: dict[str, Any], keywords: dict[str, Any] | None = None) -> dict[str, Any]:
    """product: the `product` object from the gateway snapshot. keywords: {"primary": str, "secondary": [str]}"""
    kw = keywords or {}
    primary = (kw.get("primary") or "").lower()
    secondary = [s.lower() for s in kw.get("secondary", [])]
    title = product.get("title") or ""
    body = product.get("descriptionHtml") or ""
    body_text = " ".join(_words(body))
    seo = product.get("seo") or {}
    seo_title, seo_desc = seo.get("title") or "", seo.get("description") or ""
    media = [m for m in product.get("media", {}).get("nodes", []) if m.get("mediaContentType") == "IMAGE"]
    faq = _metafield(product, "custom", "faq") or []
    comparison = _metafield(product, "custom", "comparison")
    sections: dict[str, float] = {}

    # Discoverability (22)
    d = 0.0
    d += 4 if 30 <= len(seo_title) <= 60 else 0
    d += 4 if 70 <= len(seo_desc) <= 160 else 0
    handle = product.get("handle") or ""
    d += 2 if re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", handle) and len(handle) <= 60 else 0
    if primary:
        d += 4 if _has(title, primary) else 0
        d += 3 if _has(seo_title, primary) or _has(seo_desc[:160], primary) else 0
        d += 3 if sum(_has(body_text, s) for s in secondary) >= min(3, len(secondary) or 3) else 0
    else:
        d += 4 if 20 <= len(title) <= 70 else 0
        d += 3 if seo_title and seo_desc else 0
        d += 3 if len(body_text.split()) >= 150 else 0
    d += 2 if len(product.get("tags", [])) >= 3 else 0
    sections["discoverability"] = d

    # Persuasion (15 deterministic + 5 judge)
    n_words = len(body_text.split())
    p = 5 if n_words >= 150 else 5 * n_words / 150
    p += 2 if n_words >= 300 else 0
    p += 3 if body.lower().count("<li") >= 3 else 0
    p += 2 if re.search(r"<h[23]", body, re.IGNORECASE) else 0
    p += 3 if 20 <= len(title) <= 70 else 0
    sections["persuasion"] = round(p, 2)

    # Visuals (15)
    v = min(len(media), 5)
    v += 5 * (sum(1 for m in media if (m.get("alt") or "").strip()) / len(media)) if media else 0
    widths = [(m.get("image") or {}).get("width") or 0 for m in media]
    v += 3 if widths and widths[0] >= 1000 else 0
    v += 2 if any(w >= 1500 for w in widths) else 0
    sections["visuals"] = round(v, 2)

    # Trust content (18)
    faq_text = json.dumps(faq).lower()
    t = 5 if isinstance(faq, list) and len(faq) >= 3 else 0
    t += 4 if comparison else 0
    t += 4 if any(_has(body_text + faq_text, w) for w in ("shipping", "returns", "return policy", "delivery")) else 0
    rating_count = _metafield(product, "reviews", "rating_count")
    t += 3 if rating_count and float(rating_count) > 0 else 0
    t += 2 if any(_has(body_text + faq_text, w) for w in ("warranty", "guarantee")) else 0
    sections["trust"] = t

    # Catalog and feed (15)
    c = 5 if product.get("category") else 0
    c += 2 if product.get("productType") else 0
    c += 1 if product.get("vendor") else 0
    attrs = [m for m in product.get("metafields", {}).get("nodes", []) if m["namespace"] == "shopify"]
    c += min(3, len(attrs))
    variants = product.get("variants", {}).get("nodes", [])
    c += 2 if variants and all(v.get("barcode") for v in variants) else 0
    c += 2 if product.get("collections", {}).get("nodes") else 0
    sections["catalog"] = c

    # Compliance (10)
    hits = rules.scan([{"location": "title", "text": title}, {"location": "description", "text": body_text},
                       {"location": "seo", "text": f"{seo_title} {seo_desc}"}])
    high = sum(1 for h in hits if h.severity == "high")
    medium = sum(1 for h in hits if h.severity == "medium")
    sections["compliance"] = max(0, 10 - 3 * high - medium)

    deterministic = round(sum(sections.values()), 2)
    return {"sections": sections, "deterministic": deterministic, "max_deterministic": 95,
            "compliance_hits": [h.__dict__ for h in hits]}
