"""Thin clients for the external services the agents use. Keys come from the service environment."""

import base64
import io
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from PIL import Image
from uplift_core import llm

TIMEOUT = httpx.Timeout(60, connect=10)


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not configured")
    return value


# --- Uplift Connection Gateway (store reads) -------------------------------------------------

def gateway(path: str, body: dict[str, Any], read_token: str) -> dict[str, Any]:
    resp = httpx.post(f"{_env('GATEWAY_URL')}{path}", json=body, timeout=TIMEOUT,
                      headers={"Authorization": f"Bearer {read_token}"})
    if resp.status_code == 409:
        raise RuntimeError("STORE_REAUTH_REQUIRED")
    resp.raise_for_status()
    return resp.json()


def store_query(read_token: str, query: str, variables: dict | None = None) -> dict[str, Any]:
    return gateway("/v1/read/graphql", {"query": query, "variables": variables or {}}, read_token)


# --- DataForSEO --------------------------------------------------------------------------------

def _dfs_auth() -> str:
    return base64.b64encode(f"{_env('DATAFORSEO_LOGIN')}:{_env('DATAFORSEO_PASSWORD')}".encode()).decode()


def dataforseo(path: str, task: dict[str, Any]) -> list[dict[str, Any]]:
    """Live endpoint: returns `tasks[0].result` (a list)."""
    resp = httpx.post(f"https://api.dataforseo.com/v3/{path}", json=[task], timeout=httpx.Timeout(120),
                      headers={"Authorization": f"Basic {_dfs_auth()}"})
    resp.raise_for_status()
    t = resp.json()["tasks"][0]
    if t["status_code"] >= 40000:
        raise RuntimeError(f"DataForSEO {path}: {t['status_message']}")
    return t.get("result") or []


def dataforseo_task(post_path: str, get_path: str, task: dict[str, Any], wait_s: int = 240) -> list[dict]:
    """Task endpoint (task_post → task_get) for Merchant and Business Data APIs."""
    headers = {"Authorization": f"Basic {_dfs_auth()}"}
    posted = httpx.post(f"https://api.dataforseo.com/v3/{post_path}", json=[task], headers=headers,
                        timeout=TIMEOUT).json()["tasks"][0]
    if posted["status_code"] >= 40000:
        raise RuntimeError(f"DataForSEO {post_path}: {posted['status_message']}")
    deadline = time.time() + wait_s
    while time.time() < deadline:
        time.sleep(8)
        got = httpx.get(f"https://api.dataforseo.com/v3/{get_path}/{posted['id']}", headers=headers,
                        timeout=TIMEOUT).json()["tasks"][0]
        if got["status_code"] == 20000:
            return got.get("result") or []
        if got["status_code"] >= 40000 and got["status_code"] not in (40601, 40602):  # 4060x = in queue
            raise RuntimeError(f"DataForSEO {get_path}: {got['status_message']}")
    raise TimeoutError(f"DataForSEO task {posted['id']} did not finish")


# --- Web pages -------------------------------------------------------------------------------

def scrape(url: str, schema: dict | None = None, formats: list | None = None) -> dict[str, Any]:
    fmts: list[Any] = formats or ["markdown"]
    if schema:
        fmts = [*fmts, {"type": "json", "schema": schema}]
    resp = httpx.post("https://api.firecrawl.dev/v2/scrape", json={"url": url, "formats": fmts},
                      headers={"Authorization": f"Bearer {_env('FIRECRAWL_API_KEY')}"}, timeout=httpx.Timeout(120))
    resp.raise_for_status()
    return resp.json()["data"]


def fetch_bytes(url: str) -> bytes:
    resp = httpx.get(url, timeout=TIMEOUT, follow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0 (compatible; UpliftBot/1.0; +https://uplift.example)"})
    resp.raise_for_status()
    return resp.content


# --- Reviews and discussions -----------------------------------------------------------------

def amazon_reviews(url: str, max_reviews: int = 300) -> list[dict[str, Any]]:
    """Bright Data Amazon Reviews scraper (dataset gd_le8e811kzy4ggddlq)."""
    headers = {"Authorization": f"Bearer {_env('BRIGHTDATA_API_KEY')}"}
    resp = httpx.post(
        "https://api.brightdata.com/datasets/v3/scrape?dataset_id=gd_le8e811kzy4ggddlq&format=json",
        json=[{"url": url, "max_reviews": max_reviews}], headers=headers, timeout=httpx.Timeout(90),
    )
    if resp.status_code == 202:
        snapshot = resp.json()["snapshot_id"]
        for _ in range(60):
            time.sleep(10)
            resp = httpx.get(f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot}?format=json",
                             headers=headers, timeout=TIMEOUT)
            if resp.status_code == 200:
                break
    resp.raise_for_status()
    return resp.json()


THREAD_URL = re.compile(r"^https://(?:www\.|old\.)?reddit\.com/r/[^/]+/comments/[a-z0-9]+")
AGE = re.compile(r"[•·]\s*(\d+)\s*(y|mo|w|d|h|min)\s+ago")
AGE_DAYS = {"y": 365, "mo": 30, "w": 7, "d": 1, "h": 0, "min": 0}
REDDIT_SCHEMA = {"type": "object", "properties": {"quotes": {"type": "array", "items": {"type": "object", "properties": {
    "text": {"type": "string", "description": "copied character-for-character from the thread, one opinion"},
    "about": {"type": "string", "description": "product or brand the opinion is about, or 'category'"},
    "sentiment": {"type": "string", "enum": ["positive", "negative", "mixed", "neutral"]},
    "kind": {"type": "string", "enum": ["experience", "complaint", "praise", "wish", "comparison", "recommendation"]}},
    "required": ["text", "about", "sentiment", "kind"]}}}, "required": ["quotes"]}


def _tavily(path: str, body: dict[str, Any]) -> dict[str, Any]:
    for attempt in range(3):
        resp = httpx.post(f"https://api.tavily.com/{path}", json=body, timeout=httpx.Timeout(120),
                          headers={"Authorization": f"Bearer {_env('TAVILY_API_KEY')}"})
        if resp.status_code not in (429, 500, 502, 503, 504):
            resp.raise_for_status()
            return resp.json()
        time.sleep(2 ** attempt * 3)
    resp.raise_for_status()
    return resp.json()


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def reddit_discussions(query: str, threads: int = 8) -> list[dict[str, Any]]:
    """Shopper opinions from Reddit threads: Tavily finds threads and extracts their full text, Sonnet returns
    structured quotes, and only quotes found verbatim in the thread are kept."""
    found = _tavily("search", {"query": f"{query} reddit experience review", "search_depth": "advanced",
                               "include_domains": ["reddit.com"], "max_results": 20})["results"]
    by_thread = {m.group(0): r["url"] for r in reversed(found) if (m := THREAD_URL.match(r["url"]))}  # full URL;
    urls = list(dict.fromkeys(by_thread[m.group(0)] for r in found  # extract fails on the slug-less form
                              if (m := THREAD_URL.match(r["url"]))))[:threads]
    if not urls:
        return []
    pages = _tavily("extract", {"urls": urls, "format": "text", "extract_depth": "advanced"})["results"]

    def quotes(page: dict[str, Any]) -> list[dict[str, Any]]:
        raw = page.get("raw_content") or ""
        if len(raw) < 200:
            return []
        out = llm.structured(
            f"This is a Reddit thread about '{query}'. Extract up to 15 shopper opinions (experiences, complaints, "
            "praise, wishes, comparisons, recommendations) from the post and comments. Copy each quote exactly as "
            "written — one to three consecutive sentences, no edits, no ellipses. Skip ads, navigation, usernames "
            f"and off-topic chatter.\n\n{raw[:30000]}", REDDIT_SCHEMA, max_tokens=4000)["quotes"]
        page_text, age = _squash(raw), AGE.search(raw)
        date = None
        if age:
            date = (datetime.now(UTC) - timedelta(days=int(age.group(1)) * AGE_DAYS[age.group(2)])).date().isoformat()
        title = re.sub(r"\s+", " ", raw.split(" : r/")[0].replace("Skip to main content", "")).strip()[:200]
        return [{"text": q["text"].strip(), "url": page["url"], "date": date, "thread": title,
                 "about": q["about"], "sentiment": q["sentiment"], "kind": q["kind"]}
                for q in out if len(q["text"]) > 20 and _squash(q["text"]) in page_text]

    with ThreadPoolExecutor(4) as pool:
        return [q for batch in pool.map(quotes, pages) for q in batch]


# --- Language (Sonnet 5.5) ---------------------------------------------------------------------

def translate(texts: list[str], target: str, html: bool = False) -> list[str]:
    out = llm.structured(
        f"Translate each item into the language of locale '{target}'. Natural, fluent shopper-facing wording; keep "
        "brand names, numbers and units as written" + ("; keep every HTML tag and attribute exactly" if html else "")
        + ". Return the translations in the same order.\n" + json.dumps(texts, ensure_ascii=False),
        {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "string"}}},
         "required": ["items"]}, max_tokens=8000)["items"]
    if len(out) != len(texts):
        raise RuntimeError("translation returned a different number of items")
    return out


def grammar_issues(text: str, language: str = "en-US") -> list[dict[str, Any]]:
    return llm.structured(
        f"List the grammar, spelling and punctuation errors in this {language} product copy. Ignore style "
        f"preferences and intentional brand spellings.\n\n{text[:12000]}",
        {"type": "object", "properties": {"issues": {"type": "array", "items": {"type": "object", "properties": {
            "excerpt": {"type": "string"}, "message": {"type": "string"}, "suggestion": {"type": "string"}},
            "required": ["excerpt", "message"]}}}, "required": ["issues"]})["issues"]


# --- Images: Grok vision (reading), remove.bg (cut-outs and shadows), Gemini (scene backgrounds) ----------

RETRYABLE = {429, 500, 502, 503, 504}


def _request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    """HTTP call with exponential backoff on throttling and transient errors."""
    for attempt in range(5):
        try:
            resp = httpx.request(method, url, timeout=httpx.Timeout(300, connect=10), **kwargs)
        except httpx.TransportError:
            if attempt == 4:
                raise
        else:
            if resp.status_code not in RETRYABLE or attempt == 4:
                resp.raise_for_status()
                return resp
        time.sleep(min(30, 2 ** attempt))
    raise RuntimeError("unreachable")


def _shrink(image: bytes, max_pixels: int, fmt: str = "PNG") -> bytes:
    """Downscale to a pixel budget (remove.bg ≤ 25 MP; Bedrock image blocks ≤ 3.75 MB)."""
    img = Image.open(io.BytesIO(image))
    if img.width * img.height <= max_pixels and len(image) < 3_500_000:
        return image
    scale = min(1.0, (max_pixels / (img.width * img.height)) ** 0.5)
    img = img.resize((max(64, int(img.width * scale)), max(64, int(img.height * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    (img if fmt == "PNG" else img.convert("RGB")).save(buf, fmt, **({"quality": 90} if fmt == "JPEG" else {}))
    return buf.getvalue()


def ocr(image: bytes) -> str:
    """All text visible in an image (overlays, badges, packaging), line by line."""
    lines = llm.structured("Transcribe every piece of text visible in this image, one line per text element.",
                           {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
                            "required": ["lines"]}, images=[_shrink(image, 2_000_000, "JPEG")])["lines"]
    return "\n".join(lines)


def cut_out(image: bytes, shadow: bool = False) -> bytes:
    """remove.bg: transparent PNG of the product, cropped to the subject; optionally with its AI drop shadow.
    `size=auto` returns the highest resolution the account's credits allow."""
    params = {"size": "auto", "type": "product", "format": "png", "crop": "true", "semitransparency": "true"}
    if shadow:
        params |= {"shadow_type": "drop", "shadow_opacity": "auto"}
    return _request("POST", "https://api.remove.bg/v1.0/removebg", data=params,
                    files={"image_file": ("image.jpg", _shrink(image, 25_000_000, "JPEG"))},
                    headers={"X-API-Key": _env("REMOVEBG_API_KEY")}).content


def generate_scene(prompt: str, product_reference: bytes) -> bytes:
    """An empty photographic background (no product) for the real product to be composited into: Gemini Nano Banana 2.1
    via the Interactions API, with the product photo as a reference for scale, lighting and style."""
    resp = _request("POST", "https://generativelanguage.googleapis.com/v1beta/interactions",
                    headers={"x-goog-api-key": _env("GEMINI_API_KEY")}, json={
        "model": "gemini-nano-banana-2.1",
        "input": [
            {"type": "text", "text": (
                f"Photograph an empty product-photography set: {prompt}. The reference image shows the product "
                "that will be placed here later — match its scale, lighting and style, but do NOT include the "
                "product or any similar object. Leave a clear, flat surface in the lower centre of the frame. "
                "Photorealistic, natural light, no people, no text, no logos.")},
            {"type": "image", "mime_type": "image/png",
             "data": base64.b64encode(_shrink(product_reference, 2_000_000)).decode()},
        ],
        "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "1:1", "image_size": "2K"},
    }).json()
    images = [c for step in resp.get("steps", []) if step.get("type") == "model_output"
              for c in step.get("content", []) if c.get("type") == "image"]
    if not images:
        raise RuntimeError(f"Gemini returned no image (status {resp.get('status')})")
    return base64.b64decode(images[-1]["data"])


# --- Misc ----------------------------------------------------------------------------------------

def public_holidays(year: int, country: str) -> list[dict[str, Any]]:
    resp = httpx.get(f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country.upper()}", timeout=TIMEOUT)
    return resp.json() if resp.status_code == 200 else []


def pagespeed(url: str) -> dict[str, Any]:
    resp = httpx.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed", timeout=httpx.Timeout(120),
                     params={"url": url, "strategy": "mobile", "key": _env("GOOGLE_API_KEY")})
    resp.raise_for_status()
    audits = resp.json()["lighthouseResult"]["audits"]
    return {
        "score": resp.json()["lighthouseResult"]["categories"]["performance"]["score"],
        "lcp_ms": audits["largest-contentful-paint"]["numericValue"],
        "cls": audits["cumulative-layout-shift"]["numericValue"],
        "opportunities": [a["title"] for a in audits.values()
                          if a.get("details", {}).get("type") == "opportunity" and (a.get("score") or 1) < 0.9][:5],
    }
