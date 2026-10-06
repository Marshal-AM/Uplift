"""OpenAI Responses API surface for coworker chat (Core calls `${baseURL}/conversations` and `/responses`).

Core sends no bearer token, so chat is treated as untrusted: it can answer and create a DRAFT Task assigned
to the coworker (the merchant must move it to Ready). It never touches the store or money.
"""

import json
import time
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from uplift_core import llm

from . import db
from .clients import Sokosumi
from .config import ROLES, settings

router = APIRouter(prefix="/v1")

PERSONAS = {
    "nora": "Nora, Uplift Lead and e-commerce growth manager. You plan work across 12 specialists (keywords, "
            "competitors, competitor reviews, pricing, copy, images, catalog/shopping feed, translation, content and "
            "email, ads, compliance, audits) to improve a product's ranking and sales.",
    "kai": "Kai, search demand analyst (keyword research, intent, seasonality).",
    "rafael": "Rafael, competitor and market analyst (who ranks, prices, claims, gaps).",
    "priya": "Priya, competitor review and sentiment analyst (what competitors' customers love and hate).",
    "marcus": "Marcus, pricing and promotions strategist (margin-safe discount codes, promo calendar).",
    "clara": "Clara, product page copywriter (title, description, SEO meta, handle).",
    "iris": "Iris, product visual designer (image cleanup, lifestyle scenes, channel exports, alt text).",
    "oskar": "Oskar, catalog, collections and shopping feed specialist.",
    "yuki": "Yuki, localization and transcreation specialist.",
    "leo": "Leo, content and email marketer (FAQ, comparison, blog, emails, social).",
    "sasha": "Sasha, paid ads strategist (break-even Google Ads campaigns).",
    "ruth": "Ruth, claims and compliance reviewer.",
    "quinn": "Quinn, store auditor and performance analyst (listing score, rankings, fix plan).",
}


def _role(slug: str) -> str:
    slug = (slug or "").lower()
    role = next((r for r, c in settings().coworkers.items() if c.get("slug") == slug), None) \
        or next((r for r in ROLES if slug.startswith(r)), None)
    if not role:
        raise HTTPException(404, "unknown coworker")
    return role


@router.post("/conversations")
async def create_conversation(request: Request, x_coworker_slug: str = Header(...),
                              x_sokosumi_user_id: str = Header(...), x_sokosumi_organization_id: str = Header("")):
    conv_id = f"conv_{uuid.uuid4().hex}"
    db.execute("insert into conversations (id, coworker, sokosumi_user_id, sokosumi_org_id) values (%s, %s, %s, %s)",
               conv_id, _role(x_coworker_slug), x_sokosumi_user_id, x_sokosumi_organization_id)
    return {"id": conv_id, "object": "conversation", "created_at": int(time.time())}


def _text(input_value) -> str:
    if isinstance(input_value, str):
        return input_value
    parts = []
    for item in input_value or []:
        content = item.get("content")
        if isinstance(content, str):
            parts.append(content)
        else:
            parts += [c.get("text", "") for c in content or [] if isinstance(c, dict)]
    return "\n".join(p for p in parts if p)


def _reply(role: str, conv: dict | None, user_text: str, user_id: str, org_id: str) -> str:
    history = conv["messages"] if conv else []
    out = llm.structured(
        f"You are {PERSONAS[role]} Chat with a merchant on Sokosumi. Be brief and concrete. When the merchant has "
        "described work you can do, propose a Task: a short name and a complete brief (product, goal, market, "
        "anything they told you). Do not promise results or prices beyond your role.\n\n"
        f"Conversation so far: {json.dumps(history[-12:])}\nMerchant: {user_text}",
        {"type": "object", "properties": {
            "reply": {"type": "string"},
            "task": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}}}},
         "required": ["reply"]}, max_tokens=1500)
    reply = out["reply"]
    task = out.get("task") or {}
    if task.get("name") and task.get("description"):
        client = Sokosumi(role)
        created = client.create_task((user_id, org_id or None), name=task["name"], description=task["description"],
                                     status="DRAFT", assigneeId=client.coworker_id)
        reply += (f"\n\nI've created a draft Task **{created['name']}**. Move it to **Ready** when you're happy with "
                  "the brief and I'll start.")
    if conv:
        db.execute("update conversations set messages = %s where id = %s",
                   json.dumps([*history, {"role": "user", "text": user_text}, {"role": "assistant", "text": reply}]),
                   conv["id"])
    return reply


@router.post("/responses")
async def create_response(request: Request, x_coworker_slug: str = Header(...),
                          x_sokosumi_user_id: str = Header(...), x_sokosumi_organization_id: str = Header("")):
    body = await request.json()
    role = _role(x_coworker_slug)
    conv = db.one("select * from conversations where id = %s", body.get("conversation")) if body.get(
        "conversation") else None
    resp_id = f"resp_{uuid.uuid4().hex}"
    text = _reply(role, conv, _text(body.get("input")), x_sokosumi_user_id, x_sokosumi_organization_id)
    final = {"id": resp_id, "object": "response", "status": "completed", "created_at": int(time.time()),
             "output": [{"type": "message", "id": f"msg_{uuid.uuid4().hex}", "role": "assistant",
                         "content": [{"type": "output_text", "text": text}]}]}
    db.execute("insert into responses (id, body) values (%s, %s)", resp_id, json.dumps(final))
    if not body.get("stream"):
        return final

    def events():
        yield _sse("response.created", {"type": "response.created", "response": {**final, "status": "in_progress",
                                                                                 "output": []}})
        for i in range(0, len(text), 80):
            yield _sse("response.output_text.delta", {"type": "response.output_text.delta", "delta": text[i:i + 80]})
        yield _sse("response.completed", {"type": "response.completed", "response": final})

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/responses/{resp_id}")
async def get_response(resp_id: str):
    row = db.one("select body from responses where id = %s", resp_id)
    if not row:
        raise HTTPException(404, "not found")
    return row["body"]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
