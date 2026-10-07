"""Live trace: every step a Task takes, labelled with the service it uses — for the /live page and `e2e/trace.py`.

    trace.bind(task_id, "kai")                                  # once per Task (worker) or agent run (Kodosumi)
    trace.emit("Sokosumi", "Task received", "“Audit my lunch box”")
    with trace.span("Serper", "Google search: “bento lunch box”") as s:
        ...
        s.detail = "10 results"

Events are queued and shipped by a background thread, so tracing never slows or breaks the work. The Worker writes
them to Postgres (`set_sink`); agents in Kodosumi post them to the Worker (TRACE_URL + TRACE_KEY). Signed links,
keys and tokens are stripped before anything leaves the process.
"""

import contextvars
import json
import os
import queue
import re
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx

_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar("uplift_trace", default=None)
_process: dict | None = None  # agents: one run per Kodosumi runner, so its worker threads inherit the run
_queue: queue.Queue = queue.Queue(maxsize=20_000)
_sink: Callable[[list[dict]], None] | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()
_busy = threading.Event()

SECRETS = [
    (re.compile(r"(https?://[^\s?\"'<>)]+)\?[^\s\"'<>)]*"), r"\1"),  # presigned / keyed query strings
    (re.compile(r"Bearer\s+[\w.~+/=-]+"), "Bearer •••"),
    (re.compile(r"\b(shpat|shpss|shpca|coworker|sk|bedrock-api-key)[_-][\w-]{8,}"), r"\1_•••"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)(\"?\s*[:=]\s*\"?)[^\s\",}]+"), r"\1\2•••"),
]


def clean(text: Any, limit: int = 600) -> str:
    out = str(text or "")
    for pattern, repl in SECRETS:
        out = pattern.sub(repl, out)
    out = re.sub(r"\s+", " ", out).strip()
    return out if len(out) <= limit else out[: limit - 1] + "…"


def _clean_meta(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return None
    if isinstance(value, dict):
        return {str(k)[:60]: _clean_meta(v, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, (list, tuple)):
        return [_clean_meta(v, depth + 1) for v in list(value)[:40]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return clean(value, 1500)


def bind(task_id: str | None, agent: str | None, process_wide: bool = False) -> None:
    """Attribute later events (this thread and the tasks it spawns) to a Task and agent. A Nora node id
    (`<task>:<node>`) is attributed to the Task."""
    global _process
    value = {"task": str(task_id).split(":")[0], "agent": agent} if task_id else None
    _ctx.set(value)
    if process_wide:
        _process = value


def current() -> dict | None:
    return _ctx.get() or _process


def set_sink(sink: Callable[[list[dict]], None]) -> None:
    global _sink
    _sink = sink


def emit(service: str, step: str, detail: Any = "", *, status: str = "ok", ms: float | None = None,
         span: str | None = None, task: str | None = None, agent: str | None = None, kind: str | None = None,
         meta: dict | None = None) -> None:
    """One step. `status`: running, ok, fail (a check said no), error (it broke), wait, stage (an agent's own step
    heading). Events sharing a `span` id are one step: the page shows the latest of them."""
    bound = current() or {}
    task = str(task).split(":")[0] if task else bound.get("task")
    if not task:
        return
    event = {"at": time.time(), "task": task, "agent": agent or bound.get("agent"), "service": service,
             "step": clean(step, 300), "detail": clean(detail), "status": status,
             "ms": round(ms) if ms is not None else None, "span": span, "kind": kind,
             "meta": _clean_meta(meta) if meta else None}
    try:
        _queue.put_nowait(event)
    except queue.Full:
        return
    _start()


class Span:
    def __init__(self, service: str, step: str, detail: str, kw: dict):
        self.service, self.step, self.detail, self.kw = service, step, detail, kw
        self.id = uuid.uuid4().hex[:12]
        self.status = "ok"
        self.meta: dict = dict(kw.pop("meta", None) or {})
        self.started = time.monotonic()

    @property
    def elapsed_ms(self) -> float:
        return (time.monotonic() - self.started) * 1000


@contextmanager
def span(service: str, step: str, detail: str = "", **kw: Any) -> Iterator[Span]:
    """A timed step: shown as running until the block ends, then with its outcome and duration. Set `.detail`,
    `.status`, `.step` or `.meta` inside the block to describe the outcome."""
    s = Span(service, step, detail, kw)
    emit(service, step, detail, status="running", span=s.id, meta=s.meta or None, **kw)
    try:
        yield s
    except Exception as exc:
        emit(service, s.step, f"{type(exc).__name__}: {exc}", status="error", ms=s.elapsed_ms, span=s.id,
             meta=s.meta or None, **kw)
        raise
    emit(service, s.step, s.detail, status=s.status, ms=s.elapsed_ms, span=s.id, meta=s.meta or None, **kw)


# --- shipping -------------------------------------------------------------------------------------

def _http_sink(events: list[dict]) -> None:
    url, key = os.environ.get("TRACE_URL"), os.environ.get("TRACE_KEY")
    if url and key:
        httpx.post(url, json={"events": events}, headers={"Authorization": f"Bearer {key}"}, timeout=10)


def _drain() -> None:
    while True:
        batch = [_queue.get()]
        _busy.set()
        time.sleep(0.25)  # gather what arrives together into one write
        while len(batch) < 500:
            try:
                batch.append(_queue.get_nowait())
            except queue.Empty:
                break
        try:
            (_sink or _http_sink)(batch)
        except Exception:  # tracing must never break the work
            pass
        finally:
            _busy.clear()


def _start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    with _lock:
        if not (_thread and _thread.is_alive()):
            _thread = threading.Thread(target=_drain, name="uplift-trace", daemon=True)
            _thread.start()


def flush(timeout: float = 5) -> None:
    """Wait (bounded) until queued events are shipped — before an agent run's process may end."""
    deadline = time.time() + timeout
    while (not _queue.empty() or _busy.is_set()) and time.time() < deadline:
        time.sleep(0.05)


def dumps(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False, default=str)
