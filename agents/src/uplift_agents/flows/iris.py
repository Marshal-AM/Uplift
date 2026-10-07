"""Iris — Product Visual Designer: audit (Grok vision), studio shots and lifestyle scenes rendered from the product photo
(Gemini Nano Banana 2.1), a fidelity check of every render against the original (Grok vision), channel exports, alt
text."""

import io
from concurrent.futures import ThreadPoolExecutor

import imagehash
import numpy as np
from kodosumi.core import forms as F
from PIL import Image
from uplift_core import llm

from .. import tools
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Image URLs, one per line (skip if your store is connected)", name="image_urls"),
    F.InputText(label="Product name", name="product_name", required=True),
    F.InputText(label="Category", name="category", required=True),
    F.InputText(label="Channels (comma separated: store, google_shopping, google_ads, amazon, social)",
                name="channels", value="store,google_shopping,google_ads"),
    F.InputArea(label="Brand style: palette, mood (optional)", name="brand_style"),
    F.InputArea(label="Scene ideas, one per line (optional)", name="scene_briefs"),
    F.InputNumber(label="Lifestyle scenes (0–4)", name="lifestyle_count", value="3"),
    F.InputText(label="Features that must be visible (optional)", name="must_show"),
]

CHANNELS = {
    "store": [("store", (2048, 2048), "white")],
    "google_shopping": [("google_shopping", (1500, 1500), "white")],
    "google_ads": [("google_ads_square", (1200, 1200), "scene"), ("google_ads_landscape", (1200, 628), "scene")],
    "amazon": [("amazon_main", (1600, 1600), "white")],
    "social": [("social", (1080, 1080), "scene")],
}

AUDIT_SCHEMA = {"type": "object", "properties": {
    "shot_type": {"type": "string", "enum": ["hero", "angle", "detail", "scale", "lifestyle", "infographic",
                                             "packaging", "other"]},
    "background": {"type": "string"}, "lighting_ok": {"type": "boolean"}, "sharp": {"type": "boolean"},
    "has_text_overlay": {"type": "boolean"}, "has_watermark": {"type": "boolean"}, "issues": {"type": "array",
                                                                                              "items": {"type": "string"}}},
    "required": ["shot_type", "has_text_overlay", "issues"]}


def _jpg(img: Image.Image, quality: int = 90) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue()


FIDELITY_SCHEMA = {"type": "object", "properties": {
    "fidelity": {"type": "number", "minimum": 0, "maximum": 1},
    "differences": {"type": "array", "items": {"type": "string"}}}, "required": ["fidelity", "differences"]}


def _fidelity(original: Image.Image, render: Image.Image, name: str) -> dict:
    """Grok vision: is the product in the generated image exactly the merchant's product?"""
    return llm.structured(
        f"Image 1 is the merchant's original photo of '{name}'. Image 2 is a generated product image. Compare only "
        "the product: shape, proportions, colour, material, finish, logos, text and markings. Score 1.0 if it is "
        "the same product with no visible changes, lower for every change; list each difference.",
        FIDELITY_SCHEMA, images=[_jpg(_bounded(original)), _jpg(_bounded(render))])


def _bounded(img: Image.Image, side: int = 1024) -> Image.Image:
    scale = min(1.0, side / max(img.size))
    return img.resize((int(img.width * scale), int(img.height * scale))) if scale < 1 else img


def _crop_white(img: Image.Image) -> Image.Image:
    """Crop a white-background studio shot to the product (and its shadow)."""
    box = Image.fromarray((np.asarray(img.convert("L")) < 245).astype(np.uint8) * 255).getbbox()
    return img.crop(box) if box else img


def _fit(img: Image.Image, size: tuple[int, int], fill: float = 0.85) -> Image.Image:
    """Center the subject on a white canvas filling `fill` of the shorter side."""
    canvas = Image.new("RGB", size, (255, 255, 255))
    scale = min(size[0] * fill / img.width, size[1] * fill / img.height)
    resized = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    canvas.paste(resized, ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2))
    return canvas


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    scale = max(size[0] / img.width, size[1] / img.height)
    resized = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    left, top = (resized.width - size[0]) // 2, (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def _border_mean(img: Image.Image) -> float:
    a = np.asarray(img.convert("L"), dtype=np.float32)
    return float(np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]]).mean())


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("iris", "Iris", ctx)
    product = ctx.product or {}
    name = product.get("title") or ctx.get("product_name")
    channels = [c.strip() for c in ctx.get("channels", "store,google_shopping").split(",") if c.strip() in CHANNELS]
    sources = [{"id": m["id"], "url": m["image"]["url"], "alt": m.get("alt")}
               for m in product.get("media", {}).get("nodes", []) if m.get("image")] or \
              [{"id": None, "url": u, "alt": None} for u in ctx.lines("image_urls")]
    sources = sources[:8]
    if not sources:
        raise RuntimeError("INPUT_MISSING: add product image URLs or connect your store")

    tracer.markdown_sync(f"**Iris** · auditing {len(sources)} images")
    raw = [tools.fetch_bytes(s["url"]) for s in sources]
    images = [Image.open(io.BytesIO(b)).convert("RGB") for b in raw]
    hashes = [imagehash.phash(i) for i in images]

    def audit(i: int) -> dict:
        a = llm.structured(f"Audit this e-commerce product photo of '{name}'.", AUDIT_SCHEMA,
                           images=[_jpg(images[i].resize((min(1024, images[i].width),
                                    int(images[i].height * min(1024, images[i].width) / images[i].width))), 85)])
        a["width"], a["height"] = images[i].size
        a["duplicate_of"] = next((j for j in range(i) if hashes[i] - hashes[j] <= 4), None)
        return a

    with ThreadPoolExecutor(4) as pool:
        audits = list(pool.map(audit, range(len(images))))
    have = {a["shot_type"] for a in audits}
    wanted = ["hero", "angle", "detail", "scale", "lifestyle"]
    missing = [w for w in wanted if w not in have]

    hero_idx = next((i for i, a in enumerate(audits) if a["shot_type"] == "hero"), 0)
    tracer.markdown_sync("Re-shooting the product on white")
    renders = [{"name": "clean_hero", "prompt": "white studio shot",
                "image": Image.open(io.BytesIO(tools.studio_shot(raw[hero_idx]))).convert("RGB")}]

    count = max(0, min(4, int(ctx.get("lifestyle_count", 3) or 0)))
    briefs = ctx.lines("scene_briefs")
    if count and len(briefs) < count:
        win = ctx.upstream_artifact("priya", "win_plan.json") or []
        briefs += llm.structured(
            f"Product: {name} ({ctx.get('category')}). Brand style: {ctx.get('brand_style', 'natural, bright')}. "
            f"Must show: {ctx.get('must_show', '-')}. Proof ideas: {[w['action'] for w in win if 'image' in w['action_type'].lower()]}\n"
            f"Write {count - len(briefs)} short photographic background scene prompts (no people, product stays as is).",
            {"type": "object", "properties": {"scenes": {"type": "array", "items": {"type": "string"}}},
             "required": ["scenes"]}, purpose="Writing lifestyle scene ideas for the product")["scenes"]
    briefs = briefs[:count]

    tracer.markdown_sync(f"Placing the product in {len(briefs)} lifestyle scenes")
    with ThreadPoolExecutor(2) as pool:
        shots = list(pool.map(lambda brief: tools.scene_shot(raw[hero_idx], brief), briefs))
    renders += [{"name": f"scene_{i + 1}", "prompt": brief, "image": Image.open(io.BytesIO(shot)).convert("RGB")}
                for i, (brief, shot) in enumerate(zip(briefs, shots))]

    tracer.markdown_sync("Checking every new image against the original photo")
    with ThreadPoolExecutor(4) as pool:
        verdicts = list(pool.map(lambda r: _fidelity(images[hero_idx], r["image"], name), renders))
    for r, v in zip(renders, verdicts):
        r |= v
    kept = [r for r in renders if r["fidelity"] >= 0.90]
    studio = next((r["image"] for r in kept if r["name"] == "clean_hero"), None)
    scenes = [r for r in kept if r["name"] != "clean_hero"]
    product_on_white = _crop_white(studio) if studio else None

    tracer.markdown_sync("Exporting channel versions and writing alt text")
    exports, stats = [], []
    for ch in channels:
        for label, size, kind in CHANNELS[ch]:
            if kind == "white":
                if product_on_white is None:
                    continue  # white-background channels need a studio shot that passed the fidelity check
                img = _fit(product_on_white, size, 0.85 if ch != "amazon" else 0.9)
            elif scenes:
                img = _cover(scenes[0]["image"], size)
            else:
                img = _cover(studio or images[hero_idx], size)
            url = out.artifact(f"{label}.jpg", _jpg(img), "image/jpeg")
            arr = np.asarray(img.convert("L"))
            fill = float((arr < 245).mean())
            stats.append({"name": label, "channel": ch, "width": size[0], "height": size[1],
                          "border_mean": _border_mean(img), "fill_ratio": fill, "kind": kind})
            exports.append({"name": label, "url": url, "image": img})

    new_media = [{"name": r["name"], "image": r["image"]} for r in kept]

    def alt_for(img: Image.Image) -> str:
        return llm.structured(f"Write alt text (≤125 chars) for this image of '{name}'. Describe what is visible, "
                              "include the product name, no 'image of'.",
                              {"type": "object", "properties": {"alt": {"type": "string"}}, "required": ["alt"]},
                              images=[_jpg(img.resize((768, int(img.height * 768 / img.width))), 85)])["alt"][:125]

    with ThreadPoolExecutor(4) as pool:
        new_alts = list(pool.map(lambda m: alt_for(m["image"]), new_media))
        existing_alts = list(pool.map(alt_for, images))

    media_urls = []
    for m, alt in zip(new_media, new_alts):
        url = out.artifact(f"{m['name']}.jpg", _jpg(m["image"]), "image/jpeg")
        media_urls.append({"url": url, "alt": alt, "name": m["name"]})
    order = llm.structured(
        f"Order these product images for the product page: hero first, then the image that answers the main buyer "
        f"objection, angles, lifestyle, detail. Images: "
        f"{[{'ref': f'existing:{i}', 'type': a['shot_type'], 'alt': existing_alts[i]} for i, a in enumerate(audits) if a['duplicate_of'] is None]}"
        f" + {[{'ref': f'new:{m['name']}', 'alt': m['alt']} for m in media_urls]}",
        {"type": "object", "properties": {"order": {"type": "array", "items": {"type": "string"}}},
         "required": ["order"]})["order"]

    if product.get("id"):
        out.changeset.append({"op": "media.add", "product_id": product["id"],
                              "media": [{"url": m["url"], "alt": m["alt"]} for m in media_urls]})
        files = [{"id": s["id"], "alt": alt} for s, alt in zip(sources, existing_alts) if s["id"]]
        if files:
            out.changeset.append({"op": "media.update_alt", "files": files})
        moves = [{"id": sources[int(r.split(":")[1])]["id"], "newPosition": str(pos)}
                 for pos, r in enumerate(order) if r.startswith("existing:") and r.split(":")[1].isdigit()
                 and int(r.split(":")[1]) < len(sources) and sources[int(r.split(":")[1])]["id"]]
        if moves:
            out.changeset.append({"op": "media.reorder", "product_id": product["id"], "moves": moves})

    out.artifact("visual_audit.json", {"audits": audits, "missing_shot_types": missing})
    out.artifact("alt_text.json", {"existing": existing_alts, "new": new_alts})
    out.artifact("order.json", order)
    out.artifact("fidelity.json", [{"name": r["name"], "prompt": r["prompt"], "fidelity": r["fidelity"],
                                    "differences": r["differences"], "kept": r in kept} for r in renders])
    out.bundle = {
        "product_name": name, "hero_width": audits[hero_idx]["width"],
        "exports": stats, "missing_before": missing,
        "added_types": (["hero"] if studio is not None and "hero" in missing else [])
        + (["lifestyle"] if scenes and "lifestyle" in missing else []),
        "alts": new_alts + existing_alts,
        "scenes": [{"name": r["name"], "fidelity": r["fidelity"]} for r in kept],
        "overlay_flags": {"google_shopping": False},
    }
    return out.finalize(
        f"Audited {len(images)} images · missing shot types: {', '.join(missing) or 'none'}.\n\n"
        f"Added {'a clean white hero and ' if studio is not None else ''}{len(scenes)} lifestyle scene(s), each "
        f"checked against your original photo (fidelity ≥ 0.90). Exported {len(exports)} channel versions and wrote "
        "alt text for every image.")
