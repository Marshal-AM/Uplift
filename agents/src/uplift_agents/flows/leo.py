"""Leo — Content & Email Marketer: FAQ, comparison table, blog article, email sequence, social pack."""

import csv
import io
import json
import re
from urllib.parse import urlencode

from kodosumi.core import forms as F
from uplift_core import llm

from .. import tools
from ..runtime import Context, Deliverable

FIELDS = [
    F.InputArea(label="Product facts (skip if your store is connected)", name="product_facts"),
    F.InputText(label="Deliverables (comma separated: faq, comparison, blog, email, social)", name="deliverables",
                value="faq,comparison,blog,email,social", required=True),
    F.InputText(label="Audience (optional)", name="audience"),
    F.InputArea(label="Brand voice (optional)", name="brand_voice"),
    F.InputText(label="Launch date (YYYY-MM-DD, optional)", name="launch_date"),
    F.InputText(label="Offer, e.g. discount code (optional)", name="offer"),
    F.InputArea(label="Competitors for the comparison (optional)", name="competitors"),
    F.Select(label="Email platform (sets merge tags)", name="email_platform", option=[
        F.InputOption(name="generic", label="Generic", value=True), F.InputOption(name="shopify", label="Shopify Email"),
        F.InputOption(name="mailchimp", label="Mailchimp")]),
    F.InputText(label="Social platforms (comma separated)", name="social_platforms", value="instagram,facebook,x"),
]

UNSUBSCRIBE = {"generic": "{{unsubscribe_url}}", "shopify": "{{ unsubscribe_link }}", "mailchimp": "*|UNSUB|*"}


def utm(url: str, source: str, medium: str, campaign: str, content: str) -> str:
    sep = "&" if "?" in url else "?"
    return url + sep + urlencode({"utm_source": source, "utm_medium": medium, "utm_campaign": campaign,
                                  "utm_content": content})


def run(inputs: dict, tracer) -> str:
    ctx = Context.from_inputs(inputs)
    out = Deliverable("leo", "Leo", ctx)
    wanted = {d.strip() for d in ctx.get("deliverables", "").split(",")}
    product = ctx.product or {}
    shop_url = ((ctx.snapshot or {}).get("shop", {}).get("primaryDomain") or {}).get("url", "")
    product_url = product.get("onlineStoreUrl") or (f"{shop_url}/products/{product.get('handle')}" if shop_url else "")
    campaign = f"uplift-{ctx.run_id[:12]}"
    facts = ctx.upstream_artifact("clara", "facts.json") or {}
    if not facts:  # no Clara fact sheet: number the merchant's own facts so every claim can cite one
        raw = ctx.get("product_facts", "") or re.sub("<[^>]+>", " ", product.get("descriptionHtml") or "")
        parts = [x.strip(" .") for x in re.split(r"[;\n]|(?<=\.)\s+", raw) if len(x.strip(" .")) > 3]
        facts = {f"f{i + 1}": x for i, x in enumerate(parts)}
    facts_text = "\n".join(f"{k}: {v}" for k, v in facts.items())
    title = product.get("title") or ctx.get("product_facts", "").split("\n")[0]
    kai = ctx.upstream_artifact("kai", "keyword_map.json")
    findings = ctx.upstream_artifact("priya", "findings.json") or []
    objections = [f["aspect"] for f in findings if f["kind"] in ("complaint", "dealbreaker", "wish")][:8]
    offer = ctx.get("offer") or ", ".join(c["code"] for c in (ctx.upstream_artifact("marcus", "promo_calendar.json")
                                                             or [])[:1])
    voice = ctx.get("brand_voice", "clear, warm, confident")

    tracer.markdown_sync("**Leo** · researching what people ask")
    head = kai["primary"] if kai else llm.text(
        f"Product: {title}\nFacts:\n{facts_text}\nReply with only the generic 3–6 word phrase a shopper would type into "
        "Google to find this kind of product (no brand or model names).", max_tokens=400).strip().strip('"')
    paa: list[str] = []
    outline: list[str] = []
    serp = tools.google_search(head, "US", "en")
    paa += [p["question"] for p in serp.get("peopleAlsoAsk", [])]
    outline += [o.get("title", "") for o in serp.get("organic", [])]
    questions = [k["keyword"] for k in (kai["keywords"] if kai else []) if k["intent"] == "informational"][:10]

    if "faq" in wanted:
        tracer.markdown_sync("Writing the FAQ")
        faq = llm.structured(
            f"Product: {title}\nFacts (cite ids):\n{facts_text}\nShopper questions: {paa + questions}\n"
            f"Objections from competitor reviews: {objections}\nWrite 6–10 FAQ entries answering real questions and "
            "objections using only the facts. Answer each question directly in the first sentence; skip questions the facts "
            "cannot answer. Each answer lists the fact ids it relies on.",
            {"type": "object", "properties": {"faq": {"type": "array", "items": {"type": "object", "properties": {
                "question": {"type": "string"}, "answer": {"type": "string"},
                "fact_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["question", "answer", "fact_ids"]}}}, "required": ["faq"]})["faq"]
        out.artifact("faq.json", faq)
        out.bundle["faq"] = faq
        if product.get("id"):
            out.changeset.append({"op": "metafields.set", "owner_id": product["id"], "metafields": [
                {"namespace": "custom", "key": "faq", "type": "json",
                 "value": json.dumps([{"q": f["question"], "a": f["answer"]} for f in faq])}]})

    if "comparison" in wanted:
        matrix = ctx.upstream_artifact("rafael", "competitor_matrix.json") or []
        rows = [r for r in matrix if not r.get("unavailable")][:4]
        if rows:
            comp = llm.structured(
                f"Our product: {title}\nFacts: {facts_text}\nCompetitors (use only these values): {rows}\n"
                "Build a comparison table: 5–8 attributes, our value (facts only) vs each competitor's value.",
                {"type": "object", "properties": {"attributes": {"type": "array", "items": {"type": "object",
                    "properties": {"attribute": {"type": "string"}, "ours": {"type": "string"},
                                   "competitors": {"type": "array", "items": {"type": "object", "properties": {
                                       "domain": {"type": "string"}, "value": {"type": "string"}},
                                       "required": ["domain", "value"]}}},
                    "required": ["attribute", "ours", "competitors"]}}}, "required": ["attributes"]})
            evidence = {r["domain"]: r["url"] for r in rows}
            table = {"competitors": [{"domain": r["domain"], "url": r["url"]} for r in rows], **comp}
            out.artifact("comparison.json", table)
            out.bundle["comparison"] = {"table": comp["attributes"], "evidence": evidence}
            if product.get("id"):
                out.changeset.append({"op": "metafields.set", "owner_id": product["id"], "metafields": [
                    {"namespace": "custom", "key": "comparison", "type": "json", "value": json.dumps(table)}]})

    if "blog" in wanted:
        tracer.markdown_sync("Writing the blog article")
        article = llm.structured(
            f"Write an SEO blog article (1200–1800 words) targeting '{head}'. Product: {title}. Facts: {facts_text}\n"
            f"Outline inspiration from ranking pages: {outline}\nAnswer: {paa[:6]}\nVoice: {voice}\n"
            f"Link to the product with PRODUCT_URL and mention the offer '{offer or 'none'}' once if given. "
            "Use H2/H3 headings and put the keyword in the H1 and first 100 words.",
            {"type": "object", "properties": {"title": {"type": "string"}, "summary": {"type": "string"},
                                              "html": {"type": "string"},
                                              "tags": {"type": "array", "items": {"type": "string"}}},
             "required": ["title", "summary", "html"]}, max_tokens=8000)
        body = article["html"].replace("PRODUCT_URL", utm(product_url or "#", "blog", "content", campaign, "article"))
        out.artifact("blog_article.html", body, "text/html")
        out.bundle["article"] = {"title": article["title"], "word_count": len(re.sub("<[^>]+>", " ", body).split()),
                                 "keyword": head, "links": re.findall(r'href="([^"]+)"', body),
                                 "first_100": " ".join(re.sub("<[^>]+>", " ", body).split()[:100])}
        if ctx.read_token:
            blogs = tools.store_query(ctx.read_token, "{ blogs(first: 10) { nodes { id title } } }")["blogs"]["nodes"]
            blog_id = ctx.get("blog_id") or (blogs[0]["id"] if blogs else None)
            if blog_id:
                out.changeset.append({"op": "article.create", "input": {
                    "blogId": blog_id, "title": article["title"], "body": body, "summary": article["summary"],
                    "tags": article.get("tags", [])[:8], "isPublished": False, "author": {"name": "Uplift"}}})

    if "email" in wanted:
        tracer.markdown_sync("Writing the launch emails")
        platform = ctx.get("email_platform", "generic")
        emails = llm.structured(
            f"Write a launch email sequence (announcement + reminder) for {title}. Facts: {facts_text}\n"
            f"Offer: {offer or 'none'}. Launch: {ctx.get('launch_date', 'soon')}. Audience: "
            f"{ctx.get('audience', 'subscribers')}. Voice: {voice}. Use CTA_URL for the button link. "
            "Also write flow blueprints (welcome, browse abandonment, cart abandonment) with step timing and copy, "
            "and two SMS messages (≤160 chars).",
            {"type": "object", "properties": {
                "emails": {"type": "array", "items": {"type": "object", "properties": {
                    "name": {"type": "string"}, "subject": {"type": "string"}, "preheader": {"type": "string"},
                    "body_html": {"type": "string"}, "body_text": {"type": "string"}},
                    "required": ["name", "subject", "preheader", "body_html", "body_text"]}},
                "flows_markdown": {"type": "string"}, "sms": {"type": "array", "items": {"type": "string"}}},
             "required": ["emails", "flows_markdown", "sms"]}, max_tokens=8000)
        footer = f'<p style="font-size:12px"><a href="{UNSUBSCRIBE[platform]}">Unsubscribe</a></p>'
        for i, e in enumerate(emails["emails"]):
            cta = utm(product_url or "#", "email", "email", campaign, f"email-{i + 1}")
            out.artifact(f"emails/{i + 1}-{re.sub('[^a-z0-9]+', '-', e['name'].lower())}.html",
                         e["body_html"].replace("CTA_URL", cta) + footer, "text/html")
            out.artifact(f"emails/{i + 1}.txt", e["body_text"].replace("CTA_URL", cta)
                         + f"\n\nUnsubscribe: {UNSUBSCRIBE[platform]}", "text/plain")
        out.artifact("flow_blueprints.md", emails["flows_markdown"], "text/markdown")
        out.artifact("sms.txt", "\n".join(emails["sms"]))
        out.bundle["emails"] = [{"subject": e["subject"], "preheader": e["preheader"],
                                 "has_unsubscribe": True, "has_text": bool(e["body_text"])} for e in emails["emails"]]

    if "social" in wanted:
        platforms = [p.strip() for p in ctx.get("social_platforms", "instagram").split(",") if p.strip()]
        posts = llm.structured(
            f"Write 5 social posts for each of {platforms} launching {title}. Facts: {facts_text}. Offer: "
            f"{offer or 'none'}. Voice: {voice}. Include hashtags. Use LINK where the link goes.",
            {"type": "object", "properties": {"posts": {"type": "array", "items": {"type": "object", "properties": {
                "platform": {"type": "string"}, "copy": {"type": "string"},
                "hashtags": {"type": "array", "items": {"type": "string"}}},
                "required": ["platform", "copy"]}}}, "required": ["posts"]})["posts"]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["platform", "copy", "hashtags", "link"])
        w.writeheader()
        for i, p in enumerate(posts):
            link = utm(product_url or "#", p["platform"], "social", campaign, f"post-{i + 1}")
            w.writerow({"platform": p["platform"], "copy": p["copy"].replace("LINK", link),
                        "hashtags": " ".join(p.get("hashtags", [])), "link": link})
        out.artifact("social_pack.csv", buf.getvalue(), "text/csv")

    out.bundle |= {"campaign": campaign, "shop_url": shop_url, "paa": paa[:10], "question_keywords": questions,
                   "facts": facts, "objections": objections}
    done = [d for d in ("faq", "comparison", "blog", "email", "social") if d in wanted]
    notes = ["the blog article is saved unpublished" if "blog" in done else "",
             "emails are ready to import" if "email" in done else "",
             "the FAQ goes on the product page once you approve" if out.changeset else ""]
    return out.finalize(f"Delivered: {', '.join(done)}. All links carry `utm_campaign={campaign}`"
                        + "".join(f"; {n}" for n in notes if n) + ".")
