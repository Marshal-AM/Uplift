"""Where does my product rank in my store's own search? Find it by any unique detail and print its details and ranks.

    uv run python e2e/rank.py steel-lunch-box                      # handle
    uv run python e2e/rank.py 8786058510497                        # product ID (or the full gid)
    uv run python e2e/rank.py LB-900                               # SKU, or any words from the title
    uv run python e2e/rank.py steel-lunch-box -q "bento lunch box, lunch box with bamboo lid"
    uv run python e2e/rank.py steel-lunch-box --baseline           # save these ranks as "before"

Ranks use the same check as rank-check.ps1 and Quinn: Shopify Admin `products(query:, sortKey: RELEVANCE)`, top 50.
Without -q it reuses the phrases saved with the baseline (or, for a new product, its title, type and tags). The first run for a product, or any run
with --baseline, saves the ranks to data/ranks/<handle>.json; later runs show them as "before".
"""

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
API = "2026-10"
TOP = 50
FIELDS = """id legacyResourceId handle title status vendor productType tags totalInventory onlineStoreUrl
  category { fullName } seo { title description } media(first: 50) { nodes { id } }
  priceRangeV2 { minVariantPrice { amount currencyCode } maxVariantPrice { amount } }
  variants(first: 10) { nodes { sku price inventoryItem { unitCost { amount } } } }
  collections(first: 10) { nodes { title } }"""


class Store:
    def __init__(self, shop: str):
        env = {k: v.strip().strip("'") for k, v in (line.split("=", 1) for line in
               (ROOT / "services" / "gateway" / ".env").read_text().splitlines() if "=" in line and line[0] != "#")}
        self.url = f"https://{shop}/admin/api/{API}/graphql.json"
        token = httpx.post(f"https://{shop}/admin/oauth/access_token", timeout=30, data={
            "grant_type": "client_credentials", "client_id": env["SHOPIFY_CLIENT_ID"],
            "client_secret": env["SHOPIFY_CLIENT_SECRET"]}).raise_for_status().json()["access_token"]
        self.headers = {"X-Shopify-Access-Token": token}

    def query(self, gql: str, **variables) -> dict:
        body = httpx.post(self.url, headers=self.headers, timeout=60, json={"query": gql, "variables": variables}).json()
        if body.get("errors"):
            raise SystemExit(f"Shopify error: {body['errors']}")
        return body["data"]


def find(store: Store, ident: str) -> dict:
    """Product ID, gid, handle, SKU, then title words — the first that matches exactly one product."""
    ident = ident.strip()
    if re.fullmatch(r"\d+", ident) or ident.startswith("gid://"):
        gid = ident if ident.startswith("gid://") else f"gid://shopify/Product/{ident}"
        if p := store.query(f"query($id: ID!) {{ product(id: $id) {{ {FIELDS} }} }}", id=gid)["product"]:
            return p
    if p := store.query(f"query($h: String!) {{ productByIdentifier(identifier: {{handle: $h}}) {{ {FIELDS} }} }}",
                        h=ident)["productByIdentifier"]:
        return p
    for search in (f'sku:"{ident}"', f'title:*{ident}*', ident):
        hits = store.query(f"query($q: String!) {{ products(first: 10, query: $q) {{ nodes {{ {FIELDS} }} }} }}",
                           q=search)["products"]["nodes"]
        if len(hits) == 1:
            return hits[0]
        if hits:
            names = "\n".join(f"  {h['handle']:<34} {h['title']}" for h in hits)
            raise SystemExit(f"'{ident}' matches {len(hits)} products — use one of these handles:\n{names}")
    raise SystemExit(f"No product matches '{ident}' (tried ID, handle, SKU and title).")


def default_phrases(p: dict) -> list[str]:
    """Title (minus model codes like LB-900), type and tags — a fallback; pass -q with real shopper phrases."""
    title = re.sub(r"\s*\b(?=[A-Za-z0-9-]*\d)[A-Za-z]+-?\d[\w-]*\b", "", p["title"]).strip()
    phrases = [title, p["productType"], *p["tags"]]
    seen, out = set(), []
    for ph in (x.strip() for x in phrases if x and x.strip()):
        if ph.lower() not in seen:
            seen.add(ph.lower())
            out.append(ph)
    return out[:8]


def ranks(store: Store, handle: str, phrases: list[str]) -> list[dict]:
    rows = []
    for ph in phrases:
        nodes = store.query(f"query($q: String!) {{ products(first: {TOP}, query: $q, sortKey: RELEVANCE) "
                            "{ nodes { handle title } } }", q=ph)["products"]["nodes"]
        handles = [n["handle"] for n in nodes]
        pos = handles.index(handle) + 1 if handle in handles else None
        rows.append({"phrase": ph, "rank": pos, "results": len(nodes),
                     "ahead": [n["title"] for n in nodes[: (pos or len(nodes) + 1) - 1]][:1]})
    return rows


def money(amount: str | None, cur: str = "") -> str:
    return f"{float(amount):.2f} {cur}".strip() if amount not in (None, "") else "—"


def details(p: dict) -> Table:
    price = p["priceRangeV2"]
    lo, hi, cur = price["minVariantPrice"]["amount"], price["maxVariantPrice"]["amount"], \
        price["minVariantPrice"]["currencyCode"]
    variants = p["variants"]["nodes"]
    cost = next((v["inventoryItem"]["unitCost"]["amount"] for v in variants
                 if (v.get("inventoryItem") or {}).get("unitCost")), None)
    margin = f" · margin {100 * (1 - float(cost) / float(lo)):.0f}%" if cost and float(lo) else ""
    t = Table.grid(padding=(0, 2))
    t.add_column(style="bold cyan", no_wrap=True)
    t.add_column(overflow="fold")
    for k, v in [
        ("Title", p["title"]),
        ("Handle", p["handle"]),
        ("Product ID", f"{p['legacyResourceId']}  ({p['status'].lower()})"),
        ("SKU", ", ".join(v["sku"] for v in variants if v["sku"]) or "—"),
        ("Price", (money(lo, cur) if lo == hi else f"{money(lo)}–{money(hi, cur)}")
         + (f" · cost {money(cost, cur)}{margin}" if cost else "")),
        ("Vendor / type", f"{p['vendor'] or '—'} / {p['productType'] or '—'}"),
        ("Category", (p.get("category") or {}).get("fullName") or "—"),
        ("Collections", ", ".join(c["title"] for c in p["collections"]["nodes"]) or "—"),
        ("Tags", ", ".join(p["tags"]) or "—"),
        ("Images", str(len(p["media"]["nodes"]))),
        ("SEO title", p["seo"]["title"] or "— (uses product title)"),
        ("SEO description", (p["seo"]["description"] or "—")[:160]),
        ("Store URL", p["onlineStoreUrl"] or "— (not on the Online Store)"),
    ]:
        t.add_row(k, v)
    return t


def rank_table(rows: list[dict], before: dict | None) -> Table:
    t = Table(box=box.SIMPLE_HEAD, expand=True, pad_edge=False)
    t.add_column("Search phrase", overflow="fold", ratio=3)
    if before:
        t.add_column("Before", justify="center", no_wrap=True)
    t.add_column("Now", justify="center", no_wrap=True)
    t.add_column("Results", justify="right", no_wrap=True)
    t.add_column("Ranked above it", overflow="ellipsis", no_wrap=True, ratio=3, style="dim")
    fmt = lambda r: f"#{r}" if r else f"not in top {TOP}"  # noqa: E731
    for r in rows:
        now = fmt(r["rank"])
        style = "bold green" if r["rank"] == 1 else "yellow" if r["rank"] else "red"
        cells = [r["phrase"]]
        if before:
            b = before["ranks"].get(r["phrase"].lower(), "—")
            cells.append(fmt(b) if b != "—" else "—")
            if b != "—" and (r["rank"] or TOP + 1) < (b or TOP + 1):
                now += " ▲"
            elif b != "—" and (r["rank"] or TOP + 1) > (b or TOP + 1):
                now += " ▼"
        cells += [f"[{style}]{now}[/]", str(r["results"]), ", ".join(r["ahead"]) or ""]
        t.add_row(*cells)
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("product", help="product ID, gid, handle, SKU, or words from the title")
    ap.add_argument("-q", "--phrases", help="comma-separated search phrases (default: from the product)")
    ap.add_argument("--baseline", action="store_true", help="save these ranks as the 'before' snapshot")
    ap.add_argument("--shop", default="uplift-d8k3b2rn.myshopify.com")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the box")
    a = ap.parse_args()

    store = Store(a.shop)
    p = find(store, a.product)
    snap_file = ROOT / "data" / "ranks" / f"{p['handle']}.json"
    saved = json.loads(snap_file.read_text()) if snap_file.exists() else None
    if a.phrases:
        phrases = [x.strip() for x in a.phrases.split(",") if x.strip()]
    elif saved:  # same phrases as the baseline, so before and after compare like for like
        phrases = saved.get("phrases") or list(saved["ranks"])
    else:
        phrases = default_phrases(p)
    rows = ranks(store, p["handle"], phrases)
    before = saved if saved and not a.baseline else None
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    if a.baseline or not snap_file.exists():
        snap_file.parent.mkdir(parents=True, exist_ok=True)
        snap_file.write_text(json.dumps({"at": now, "title": p["title"], "phrases": phrases,
                                         "ranks": {r["phrase"].lower(): r["rank"] for r in rows}}, indent=1))

    if a.json:
        print(json.dumps({"product": {k: p[k] for k in ("legacyResourceId", "handle", "title", "status")},
                          "checked_at": now, "ranks": rows, "before": before}, indent=1))
        return
    ranked = sum(1 for r in rows if r["rank"])
    top = sum(1 for r in rows if r["rank"] == 1)
    summary = (f"[bold]{ranked}/{len(rows)}[/] phrases find it · [bold green]#1 for {top}[/] · "
               f"store search, top {TOP}, checked {now}")
    summary += f"\n[dim]Before = {before['at']}[/]" if before else "\n[dim]Saved as the baseline: later runs show these ranks as Before.[/]"
    Console().print(Panel(Group(details(p), "", rank_table(rows, before), summary),
                          title=f"[bold]{p['title']}[/]", subtitle=a.shop, box=box.ROUNDED, padding=(1, 2)))


if __name__ == "__main__":
    main()
