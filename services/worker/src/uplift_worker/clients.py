"""Clients for Sokosumi Core (coworker runtime), Kodosumi (panel API), the Gateway and the Masumi payment node."""

import time
from typing import Any

import httpx
from uplift_core import trace

from .config import settings

TIMEOUT = httpx.Timeout(60, connect=10)


class Sokosumi:
    """Calls Core as one coworker (Bearer coworker key), optionally on behalf of a Task owner."""

    def __init__(self, role: str):
        self.role = role
        self.coworker_id = settings().coworkers[role]["id"]
        self._key = settings().coworkers[role]["key"]

    def _headers(self, user_id: str | None = None, org_id: str | None = None) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self._key}", "Accept": "application/json"}
        if user_id:
            h["X-Context-User-Id"] = user_id
        if org_id:
            h["X-Context-Organization-Id"] = org_id
        return h

    def request(self, method: str, path: str, body: Any = None, *, as_user: tuple | None = None) -> Any:
        resp = httpx.request(method, f"{settings().sokosumi_api_url}{path}", json=body, timeout=TIMEOUT,
                             headers=self._headers(*(as_user or ())), follow_redirects=False)
        if resp.status_code >= 400:
            raise SokosumiError(resp.status_code, resp.text[:500])
        return resp.json() if resp.content else None

    def _agent(self) -> str:
        """Who posts, for the live trace: the bound agent, or this coworker (Nora's parallel verifications)."""
        return (trace.current() or {}).get("agent") or self.role

    # tasks
    def events(self, cursor: str | None) -> tuple[list[dict], str | None]:
        q = f"?limit=100&cursor={cursor}" if cursor else "?limit=100"
        body = self.request("GET", f"/v1/coworkers/me/events{q}")
        return body["data"], (body.get("meta", {}).get("pagination") or {}).get("nextCursor")

    def task(self, task_id: str) -> dict:
        return self.request("GET", f"/v1/tasks/{task_id}")["data"]

    def task_events(self, task_id: str) -> list[dict]:
        return self.request("GET", f"/v1/tasks/{task_id}/events")["data"]

    def event(self, task_id: str, **body: Any) -> dict:
        if "masumiPayment" in body:  # traced by payments.charge, with the amount
            return self.request("POST", f"/v1/tasks/{task_id}/events", body)["data"]
        status = body.get("status")
        step = f"Task status → {STATUS_LABEL.get(status, status)}" if status else "Posted an update to the Task"
        with trace.span("Sokosumi", step, _first_line(body.get("comment")), task=task_id, agent=self._agent(),
                        kind="sokosumi.event",
                        meta={"status": status, "message": body.get("comment")} if body.get("comment") else None):
            return self.request("POST", f"/v1/tasks/{task_id}/events", body)["data"]

    def upload(self, task_id: str, filename: str, data: bytes, content_type: str) -> None:
        with trace.span("Sokosumi", f"Attached {filename} to the Task", f"{len(data) / 1024:,.1f} KB · {content_type}",
                        task=task_id, agent=self._agent(), kind="sokosumi.file"):
            session = self.request("POST", f"/v1/tasks/{task_id}/files",
                                   {"filename": filename, "contentType": content_type, "size": len(data)})["data"]
            httpx.put(session["uploadUrl"], content=data,
                      headers=session.get("headers") or {"Content-Type": content_type},
                      timeout=httpx.Timeout(120)).raise_for_status()

    def create_task(self, as_user: tuple, **body: Any) -> dict:
        return self.request("POST", "/v1/tasks", body, as_user=as_user)["data"]

    # jobs (Nora hiring specialists, billed to the Task owner)
    def hire(self, task_id: str, agent_id: str, input_data: dict, max_credits: float, name: str) -> dict:
        return self.request("POST", f"/v1/tasks/{task_id}/jobs", {"agentId": agent_id, "inputData": input_data,
                                                                  "maxCredits": max_credits, "name": name})["data"]

    def job(self, job_id: str) -> dict:
        return self.request("GET", f"/v1/jobs/{job_id}")["data"]

    def rate(self, agent_id: str, rating: int, as_user: tuple) -> None:
        self.request("POST", f"/v1/agents/{agent_id}/ratings", {"rating": rating}, as_user=as_user)

    def receipt(self, task_id: str) -> dict:
        return self.request("GET", f"/v1/tasks/{task_id}/receipt")["data"]


STATUS_LABEL = {"RUNNING": "Running", "INPUT_REQUIRED": "Needs the merchant's input",
                "APPROVAL_REQUIRED": "Waiting for the merchant's approval", "COMPLETED": "Completed",
                "FAILED": "Failed", "AUTHENTICATION_REQUIRED": "Needs the store connection"}


def _first_line(text: str | None) -> str:
    line = next((x.strip() for x in (text or "").splitlines() if x.strip()), "")
    return line.replace("**", "")


class SokosumiError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"Sokosumi {status}: {body}")
        self.status = status


class Kodosumi:
    """Runs a specialist flow through the panel API (no Sumi payment; the Worker handles paid Tasks)."""

    def __init__(self):
        self.http = httpx.Client(base_url=settings().kodo_url, timeout=httpx.Timeout(120))
        self.http.post("/api/login", json={"name": settings().kodo_admin_user,
                                           "password": settings().kodo_admin_password}).raise_for_status()

    def launch(self, role: str, inputs: dict[str, Any], label: str | None = None) -> str:
        """`label`: the plan node the trace shows this run as (Nora: `quinn_after`, `yuki:de`); default the role."""
        resp = self.http.post(f"/-/uplift/uplift/{role}", json=inputs)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("result"):
            raise FlowError(f"launch rejected: {body.get('errors') or body}")
        fid = body["result"]
        _runs[fid] = (label or role, time.time())
        trace.emit("Kodosumi", f"Started {_name(label or role)}'s agent", f"run {fid}", status="running",
                   span=f"run-{fid}", agent=label or role, kind="kodosumi.run", meta={"run": fid, "flow": f"/uplift/{role}"})
        return fid

    def wait(self, fid: str, launched_at: float, timeout_s: int = 1800) -> str:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            state, text = self.status(fid, launched_at)
            if state == "finished":
                return text
            if state == "error":
                raise FlowError(text)
            time.sleep(2)
        raise FlowError(f"flow {fid} timed out")

    def status(self, fid: str, launched_at: float) -> tuple[str, str | None]:
        """Without blocking: ("running", None), ("finished", manifest text) or ("error", message). Kodosumi holds a
        status request for a run it does not know, so the request is short and an unknown run is FlowLost."""
        try:
            resp = self.http.get(f"/outputs/status/{fid}?extended=true", timeout=15)
            unknown = resp.status_code >= 500  # the edge proxy answers 502 for a held request
        except httpx.ReadTimeout:
            unknown = True
        if unknown:
            if time.time() - launched_at > LOST_AFTER_S:
                role = _runs.pop(fid, (None, 0))[0]
                trace.emit("Kodosumi", "Agent run never started — relaunching", f"run {fid}", status="error",
                           span=f"run-{fid}", agent=role, kind="kodosumi.run")
                raise FlowLost(f"run {fid} never started")
            return "running", None
        status = resp.json()
        if status["status"] in ("finished", "error"):
            text = _final_text(status["final"])
            _close_run(fid, status["status"], text, launched_at)
            return status["status"], text
        return "running", None

    def input_schema(self, role: str) -> list[dict]:
        return self.http.get(f"/sumi/uplift/{role}/input_schema").json()["input_data"]


def _final_text(final: Any) -> str:
    """Kodosumi serialises str results as {"Text": {"body": ...}} or plain JSON string."""
    import json

    if isinstance(final, str):
        try:
            final = json.loads(final)
        except ValueError:
            return final
    if isinstance(final, dict) and "Text" in final:
        return final["Text"]["body"]
    if isinstance(final, dict) and "str" in final:
        return final["str"]
    return final if isinstance(final, str) else json.dumps(final)


class FlowError(Exception):
    pass


class FlowLost(FlowError):
    """Kodosumi accepted the launch but the run never started (its status stays unknown); relaunch it."""


_runs: dict[str, tuple[str, float]] = {}  # fid → (role, launched) for the trace


def _close_run(fid: str, state: str, text: str | None, launched_at: float) -> None:
    if fid not in _runs and not trace.current():
        return
    role, started = _runs.pop(fid, (None, launched_at))
    if state == "finished":
        try:
            import json

            manifest = json.loads(text or "{}")
            detail = (f"{len(manifest.get('artifacts', []))} deliverables · {len(manifest.get('changeset', []))} "
                      "proposed store changes")
        except ValueError:
            detail = "result ready"
        trace.emit("Kodosumi", f"{_name(role)}'s agent finished" if role else "The agent finished", detail, ms=(time.time() - started) * 1000,
                   span=f"run-{fid}", agent=role, kind="kodosumi.run", meta={"run": fid})
    else:
        trace.emit("Kodosumi", f"{_name(role)}'s agent stopped" if role else "The agent stopped", (text or "error")[:300],
                   status="error",
                   ms=(time.time() - started) * 1000, span=f"run-{fid}", agent=role, kind="kodosumi.run")


def _name(agent: str) -> str:
    """A plan node as people read it: quinn_after → Quinn (after-report), yuki:de → Yuki (de)."""
    base, _, rest = agent.replace("_after", ":after-report").partition(":")
    return base.title() + (f" ({rest})" if rest else "")


LOST_AFTER_S = 90  # a run Kodosumi still does not know this long after launch never started


GATEWAY_STEPS = {"/v1/read/snapshot": "Reading the product from the store", "/v1/read/graphql": "Store query"}


def gateway(path: str, body: dict) -> Any:
    step = GATEWAY_STEPS.get(path)  # the connection check repeats while waiting and is not traced

    def call() -> Any:
        resp = httpx.post(f"{settings().gateway_url}{path}", json=body, timeout=TIMEOUT,
                          headers={"Authorization": f"Bearer {settings().gateway_read_key}"})
        if resp.status_code == 409:
            raise ReauthRequired()
        resp.raise_for_status()
        return resp.json()

    if not step:
        return call()
    with trace.span("Shopify", step, "read-only, through the Uplift gateway", kind="shopify.read"):
        return call()


class ReauthRequired(Exception):
    pass


def mps(path: str, body: dict | None = None) -> Any:
    s = settings()
    resp = httpx.request("POST" if body is not None else "GET", f"{s.mps_url}{path}", json=body, timeout=TIMEOUT,
                         headers={"token": s.mps_token, "Content-Type": "application/json"})
    data = resp.json()
    if resp.status_code >= 400 or data.get("status") != "success":
        raise RuntimeError(f"MPS {path} failed ({resp.status_code}): {str(data)[:300]}")
    return data["data"]
