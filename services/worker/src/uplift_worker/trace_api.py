"""Live trace API: agents post their events here; the /live page and e2e/trace.py read and stream them.

POST /trace/ingest                      Bearer TRACE_KEY — {"events": [...]} from the agents (Kodosumi)
GET  /trace/tasks?key=                  recent Tasks with title, coworker, phase, credits
GET  /trace/events?task=&after=&key=    a Task's events after an id
GET  /trace/stream?task=&key=           the same as Server-Sent Events, live (resumes from Last-Event-ID)
"""

import asyncio
import hmac
import json
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from uplift_core import trace

from . import db
from .config import settings
from .db import PHASES

router = APIRouter(prefix="/trace")



def _view(key: str) -> None:
    expected = settings().trace_view_key
    if not expected or not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(401, "bad key")


def _row(r: dict) -> dict:
    return {"id": r["id"], "at": r["at"].timestamp() * 1000, "agent": r["agent"], "service": r["service"],
            "step": r["step"], "detail": r["detail"], "status": r["status"], "ms": r["ms"], "span": r["span"],
            "kind": r["kind"], "meta": r["meta"]}


EVENTS = ("select id, at, agent, service, step, detail, status, ms, span, kind, meta from trace_events "
          "where task_id = %s and id > %s order by id limit %s")


@router.post("/ingest")
async def ingest(request: Request, authorization: str | None = Header(None)):
    key = settings().trace_key
    if not key or not authorization or not hmac.compare_digest(authorization.encode(), f"Bearer {key}".encode()):
        raise HTTPException(401, "bad key")
    events = (await request.json()).get("events", [])[:500]
    await asyncio.to_thread(db.insert_trace, events)
    return {"ok": True, "stored": len(events)}


@router.get("/tasks")
def tasks(key: str = Query(""), limit: int = Query(40, le=200)):
    _view(key)
    rows = db.all_(
        """select t.task_id, min(t.at) as started, max(t.at) as last, count(*) as steps,
                  array_remove(array_agg(distinct t.agent), null) as agents,
                  (array_agg(t.meta order by t.id) filter (where t.kind = 'task.received'))[1] as info,
                  sum(coalesce((t.meta->>'credits')::numeric, 0)) filter (where t.kind = 'payment.charged') as credits,
                  r.phase, r.coworker
           from trace_events t left join runs r on r.task_id = t.task_id
           group by t.task_id, r.phase, r.coworker order by max(t.at) desc limit %s""", limit)
    out = []
    for r in rows:
        info = r["info"] or {}
        out.append({"task": r["task_id"], "title": info.get("title") or "Task", "brief": info.get("brief") or "",
                    "coworker": r["coworker"] or info.get("coworker"), "phase": r["phase"],
                    "phase_label": PHASES.get(r["phase"] or "", r["phase"] or ""),
                    "started": r["started"].timestamp() * 1000, "last": r["last"].timestamp() * 1000,
                    "steps": r["steps"], "agents": r["agents"], "credits": float(r["credits"] or 0) or None})
    return {"tasks": out, "now": time.time() * 1000}


@router.get("/events")
def events(task: str, key: str = Query(""), after: int = Query(0), limit: int = Query(2000, le=5000)):
    _view(key)
    return {"events": [_row(r) for r in db.all_(EVENTS, task, after, limit)]}


@router.get("/stream")
async def stream(request: Request, task: str, key: str = Query(""), after: int = Query(0),
                 last_event_id: str | None = Header(None)):
    _view(key)
    start = int(last_event_id) if last_event_id and last_event_id.isdigit() else after

    async def feed():
        last, quiet, until = start, 0, time.time() + 600  # the browser reconnects after 10 min, from Last-Event-ID
        yield "retry: 1500\n\n"
        while time.time() < until and not await request.is_disconnected():
            rows = await asyncio.to_thread(db.all_, EVENTS, task, last, 500)
            for r in rows:
                last = r["id"]
                yield f"id: {last}\ndata: {json.dumps(_row(r), ensure_ascii=False, default=str)}\n\n"
            quiet = 0 if rows else quiet + 1
            if quiet and quiet % 30 == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(feed(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def trace_md(task_id: str) -> str:
    """The Task's full step log as Markdown (attached to the finished Task as trace.md)."""
    rows = db.all_(EVENTS, task_id, 0, 5000)
    spans: dict[str, dict] = {}
    ordered: list[dict] = []
    for r in rows:  # one line per step: a span's last event replaces its "running" one
        if r["span"] and r["span"] in spans:
            spans[r["span"]].update(r)
            continue
        item = dict(r)
        ordered.append(item)
        if r["span"]:
            spans[r["span"]] = item
    if not ordered:
        return ""
    t0 = ordered[0]["at"]
    lines = [f"# Live trace · Task `{task_id}`", "",
             f"{len(ordered)} steps · started {t0.astimezone(UTC):%Y-%m-%d %H:%M:%S} UTC · every step, the agent "
             "that took it and the service it used.", "",
             "| t+ | agent | service | step | result | time |", "|---|---|---|---|---|---|"]
    for e in ordered:
        off = (e["at"] - t0).total_seconds()
        step = ("**" + e["step"] + "**") if e["status"] == "stage" else e["step"]
        result = {"error": "⚠ ", "fail": "✗ "}.get(e["status"], "") + (e["detail"] or "")
        took = f"{e['ms'] / 1000:.1f} s" if e["ms"] is not None else ""
        cells = [f"{int(off // 60)}:{off % 60:04.1f}", e["agent"] or "", e["service"], step, result, took]
        lines.append("| " + " | ".join(str(c).replace("|", "\\|") for c in cells) + " |")
    return "\n".join(lines) + f"\n\n_Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by the Uplift Worker._\n"


def attach_trace(client, task_id: str, st: dict, save) -> None:
    """Attach the step log to the finished Task once; never holds up the delivery."""
    if st.get("trace_attached"):
        return
    try:
        trace.flush(3)
        text = trace_md(task_id)
        if text:
            client.upload(task_id, "trace.md", text.encode(), "text/markdown")
        st["trace_attached"] = True
        save()
    except Exception:
        pass
