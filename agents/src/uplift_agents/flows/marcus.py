"""Marcus — Pricing & Promotions Strategist: positioning, promo calendar, margin-safe discount codes."""

import csv
import io
import statistics
from datetime import UTC, date, datetime, timedelta

from kodosumi.core import forms as F
from uplift_core import llm

from .. import tools
from ..markets import location_code
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Product (or connect your store)", name="product"),
    F.Select(label="Goal", name="goal", option=[
        F.InputOption(name="launch", label="Launch", value=True), F.InputOption(name="seasonal", label="Seasonal"),
        F.InputOption(name="clearance", label="Clearance"), F.InputOption(name="aov", label="Grow order value")]),
    F.InputText(label="Promotion window start (YYYY-MM-DD, optional)", name="promo_start"),
    F.InputText(label="Promotion window end (YYYY-MM-DD, optional)", name="promo_end"),
    F.InputNumber(label="Margin floor %", name="margin_floor_pct", value="35", required=True),
    F.InputNumber(label="Unit cost (if not in your store)", name="unit_cost"),
    F.InputNumber(label="Price (if not in your store)", name="price"),
    F.InputNumber(label="Shipping cost per order", name="shipping_cost", value="0"),
    F.InputText(label="Discount limits (e.g. max 25%, one per customer)", name="discount_limits"),
    F.InputText(label="Market (country code)", name="market_country", value="US", required=True),
]

RETAIL_EVENTS = [(1, 1, "New Year"), (2, 14, "Valentine's Day"), (5, 10, "Mother's Day (approx.)"),
                 (7, 15, "Prime Day (approx.)"), (11, 11, "Singles' Day"), (11, 27, "Black Friday (approx.)"),
                 (12, 1, "Cyber Monday (approx.)"), (12, 24, "Holiday gifting")]


def margin(price: float, discount: float, cost: float, shipping: float) -> float:
    net = price - discount
    return (net - cost - shipping) / net if net > 0 else -1.0


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("marcus", "Marcus", ctx)
    floor = float(ctx.get("margin_floor_pct", 35)) / 100
    shipping = float(ctx.get("shipping_cost", 0) or 0)
    country = ctx.get("market_country", "US")

    tracer.markdown_sync("**Marcus** · reading prices and unit costs")
    product = ctx.product or {}
    variants = product.get("variants", {}).get("nodes", [])
    price = float(variants[0]["price"]) if variants else float(ctx.get("price") or 0)
    cost_node = (variants[0].get("inventoryItem") or {}).get("unitCost") if variants else None
    cost = float(cost_node["amount"]) if cost_node else float(ctx.get("unit_cost") or 0)
    if not price or not cost:
        raise RuntimeError("INPUT_MISSING: price and unit cost are required (connect the store or enter them)")

    bands = ctx.upstream_artifact("rafael", "price_bands.json")
    if not bands:
        found = tools.dataforseo_task(
            "merchant/google/products/task_post", "merchant/google/products/task_get/advanced",
            {"keyword": product.get("title") or ctx.get("product"), "location_code": location_code(country),
             "language_code": "en", "depth": 40})
        prices = sorted(i["price"] for r in found for i in r.get("items") or [] if i.get("price"))
        bands = {"min": prices[0], "median": statistics.median(prices), "max": prices[-1], "n": len(prices)} \
            if prices else {}
    season = ctx.upstream_artifact("kai", "seasonality.json") or {}

    tracer.markdown_sync("Modelling discount scenarios against your margin")
    scenarios = []
    for pct in (5, 10, 15, 20, 25, 30, 40):
        d = price * pct / 100
        m = margin(price, d, cost, shipping)
        base_m = margin(price, 0, cost, shipping)
        lift = (d / price) / (base_m - d / price) if base_m - d / price > 0 else None
        scenarios.append({"mechanic": f"{pct}% off", "discount_pct": pct, "net_price": round(price - d, 2),
                          "margin": round(m, 4), "breakeven_volume_lift": round(lift, 3) if lift else None,
                          "allowed": m >= floor})
    max_pct = max([s["discount_pct"] for s in scenarios if s["allowed"]], default=0)

    today = date.today()
    holidays = tools.public_holidays(today.year, country) + tools.public_holidays(today.year + 1, country)
    events = [{"date": f"{y}-{m:02d}-{d:02d}", "name": n} for y in (today.year, today.year + 1)
              for m, d, n in RETAIL_EVENTS if date(y, m, d) > today][:8]
    window = (ctx.get("promo_start"), ctx.get("promo_end"))

    strategy = llm.structured(
        f"Product: {product.get('title') or ctx.get('product')}\nPrice {price}, unit cost {cost}, shipping {shipping}, "
        f"margin floor {floor:.0%}. Max allowed discount: {max_pct}%.\nMarket price bands: {bands}\n"
        f"Seasonality: {season}\nUpcoming retail events: {events}\nPublic holidays: "
        f"{[h['date'] + ' ' + h['localName'] for h in holidays if h['date'] > str(today)][:10]}\n"
        f"Goal: {ctx.get('goal', 'launch')}. Merchant window: {window}. Limits: {ctx.get('discount_limits', 'none')}\n"
        "Recommend positioning (premium/parity/value) with advisory list-price guidance, and 1–4 promotions. "
        f"Each promotion's percentage MUST be ≤ {max_pct}. Dates must be in the future (YYYY-MM-DD).",
        {"type": "object", "properties": {
            "positioning": {"type": "string", "enum": ["premium", "parity", "value"]},
            "price_guidance": {"type": "string"}, "rationale": {"type": "string"},
            "promotions": {"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"}, "code": {"type": "string"}, "percentage": {"type": "number"},
                "starts": {"type": "string"}, "ends": {"type": "string"}, "usage_limit": {"type": "integer"},
                "once_per_customer": {"type": "boolean"}, "why": {"type": "string"}},
                "required": ["name", "code", "percentage", "starts", "ends"]}}},
         "required": ["positioning", "price_guidance", "promotions"]}, max_tokens=3000)

    now = datetime.now(UTC)
    codes = []
    for p in strategy["promotions"]:
        starts = datetime.fromisoformat(p["starts"]).replace(tzinfo=UTC)
        ends = datetime.fromisoformat(p["ends"]).replace(tzinfo=UTC) + timedelta(hours=23, minutes=59)
        pct = float(p["percentage"])
        if margin(price, price * pct / 100, cost, shipping) < floor or starts <= now or ends <= starts:
            continue  # never ship a code that breaks the floor or isn't schedulable
        code = p["code"].upper().replace(" ", "")[:20]
        codes.append({**p, "code": code, "starts": starts.isoformat(), "ends": ends.isoformat()})
        out.changeset.append({"op": "discount.create", "input": {
            "title": p["name"], "code": code, "startsAt": starts.isoformat(), "endsAt": ends.isoformat(),
            "customerGets": {"value": {"percentage": round(pct / 100, 4)},
                             "items": {"products": {"productsToAdd": [product["id"]]}} if product.get("id")
                             else {"all": True}},
            "context": {"all": "ALL"},
            "appliesOncePerCustomer": bool(p.get("once_per_customer", True)),
            **({"usageLimit": p["usage_limit"]} if p.get("usage_limit") else {}),
        }})

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(scenarios[0]))
    w.writeheader()
    w.writerows(scenarios)
    ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Uplift//Marcus//EN"]
    for c in codes:
        ics += ["BEGIN:VEVENT", f"SUMMARY:{c['name']} ({c['code']})",
                f"DTSTART;VALUE=DATE:{c['starts'][:10].replace('-', '')}",
                f"DTEND;VALUE=DATE:{c['ends'][:10].replace('-', '')}", "END:VEVENT"]
    ics.append("END:VCALENDAR")

    out.artifact("pricing_strategy.md", f"# Pricing strategy\n\n**Positioning:** {strategy['positioning']}\n\n"
                 f"**List price guidance (advisory):** {strategy['price_guidance']}\n\n{strategy.get('rationale', '')}",
                 "text/markdown")
    out.artifact("scenarios.csv", buf.getvalue(), "text/csv")
    out.artifact("promo_calendar.json", codes)
    out.artifact("promo_calendar.ics", "\r\n".join(ics), "text/calendar")
    out.artifact("discount_codes.json", [op["input"] for op in out.changeset])
    out.bundle = {"price": price, "unit_cost": cost, "shipping": shipping, "floor": floor, "bands": bands,
                  "positioning": strategy["positioning"], "scenarios": scenarios,
                  "codes": [{"code": c["code"], "percentage": c["percentage"], "starts": c["starts"],
                             "ends": c["ends"]} for c in codes]}
    return out.finalize(
        f"**Positioning:** {strategy['positioning']} · price {price} vs market median {bands.get('median', 'n/a')}\n\n"
        f"**{len(codes)} scheduled discount codes**, all above your {floor:.0%} margin floor:\n"
        + "\n".join(f"- {c['code']}: {c['percentage']}% · {c['starts'][:10]} → {c['ends'][:10]}" for c in codes))
