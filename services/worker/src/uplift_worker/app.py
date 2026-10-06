"""Uplift Worker: one executor loop per coworker, plus chat (Responses API) and hook endpoints."""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request

from . import db, nora, specialist
from .chat import router as chat_router
from .clients import Sokosumi
from .config import settings

log = logging.getLogger("uplift.worker")
_inflight: set[str] = set()


def _advance(role: str, task_id: str) -> None:
    try:
        nora.advance(task_id) if role == "nora" else specialist.advance(role, task_id)
    except Exception:
        log.exception("task %s (%s) failed to advance; will retry", task_id, role)


async def _kick(role: str, task_id: str) -> None:
    if task_id in _inflight:
        return
    _inflight.add(task_id)
    try:
        await asyncio.to_thread(_advance, role, task_id)
    finally:
        _inflight.discard(task_id)


async def executor(role: str) -> None:
    """Poll this coworker's task events; start READY Tasks and resume Tasks waiting on the merchant."""
    client = Sokosumi(role)
    while True:
        try:
            cursor = db.cursor(role)
            events, _ = await asyncio.to_thread(client.events, cursor)
            touched = {e["taskId"] for e in events}
            if events:
                db.set_cursor(role, events[-1]["id"])
            for task_id in touched:
                run = db.get_run(task_id)
                if run is None:
                    task = await asyncio.to_thread(client.task, task_id)
                    if task["status"] != "READY":
                        continue
                if run is None or run["phase"] not in ("done", "closed"):
                    asyncio.create_task(_kick(role, task_id))
            # every run not waiting on the merchant (or finished) keeps advancing without new events: store
            # connect, escrow funding, running Jobs, and resuming after a failed step or a restart
            for run in db.all_("select task_id from runs where coworker = %s and phase not in ('input_wait', "
                               "'quote_wait', 'approval_wait', 'done', 'closed')", role):
                asyncio.create_task(_kick(role, run["task_id"]))
        except Exception:
            log.exception("executor %s poll failed", role)
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.open_pool()
    loops = [asyncio.create_task(executor(role)) for role in settings().coworkers]
    yield
    for loop in loops:
        loop.cancel()
    db.close_pool()


app = FastAPI(title="Uplift Worker", lifespan=lifespan)
app.include_router(chat_router)


@app.get("/health")
def health():
    return {"ok": True, "coworkers": sorted(settings().coworkers)}


def _verify(body: bytes, signature: str | None) -> None:
    expected = hmac.new(settings().worker_hook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "bad signature")


@app.post("/hooks/store-connected")
async def store_connected(request: Request, x_uplift_signature: str | None = Header(None)):
    body = await request.body()
    _verify(body, x_uplift_signature)
    event = json.loads(body)
    run = db.get_run(event["task_id"])
    if run and run["phase"] == "auth_wait":
        asyncio.create_task(_kick(run["coworker"], event["task_id"]))
    return {"ok": True}


@app.post("/hooks/cre")
async def cre_result(request: Request, authorization: str | None = Header(None)):
    """CRE `uplift-clearing` posts its result here (Confidential HTTP with the callback key)."""
    if authorization != f"Bearer {settings().worker_hook_secret}":
        raise HTTPException(401, "bad callback key")
    result = await request.json()
    db.execute("insert into cre_results (request_id, result) values (%s, %s) on conflict do nothing",
               result["request_id"], json.dumps(result))
    return {"ok": True}


def _install_cre_session() -> None:
    """`cre workflow simulate` requires a CRE login. Seed the CLI's session (its refresh token is not rotated, so
    this copy refreshes independently) from CRE_SESSION_B64 / CRE_CONTEXT_B64."""
    home = Path.home() / ".cre"
    for var, name in (("CRE_SESSION_B64", "cre.yaml"), ("CRE_CONTEXT_B64", "context.yaml")):
        if os.environ.get(var):
            home.mkdir(mode=0o700, exist_ok=True)
            (home / name).write_bytes(base64.b64decode(os.environ[var]))
            (home / name).chmod(0o600)


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    _install_cre_session()
    uvicorn.run("uplift_worker.app:app", host="0.0.0.0", port=settings().port)
