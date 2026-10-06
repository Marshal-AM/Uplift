"""Clients for Sokosumi Core (coworker runtime), Kodosumi (panel API), the Gateway and the Masumi payment node."""

import time
from typing import Any

import httpx

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
        return self.request("POST", f"/v1/tasks/{task_id}/events", body)["data"]

    def upload(self, task_id: str, filename: str, data: bytes, content_type: str) -> None:
        session = self.request("POST", f"/v1/tasks/{task_id}/files",
                               {"filename": filename, "contentType": content_type, "size": len(data)})["data"]
        httpx.put(session["uploadUrl"], content=data, headers=session.get("headers") or {"Content-Type": content_type},
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

    def launch(self, role: str, inputs: dict[str, Any]) -> str:
        resp = self.http.post(f"/-/uplift/uplift/{role}", json=inputs)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("result"):
            raise FlowError(f"launch rejected: {body.get('errors') or body}")
        return body["result"]

    def wait(self, fid: str, timeout_s: int = 1800) -> str:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            status = self.http.get(f"/outputs/status/{fid}?extended=true").json()
            if status["status"] == "finished":
                return _final_text(status["final"])
            if status["status"] == "error":
                raise FlowError(_final_text(status["final"]))
            time.sleep(5)
        raise FlowError(f"flow {fid} timed out")

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


def gateway(path: str, body: dict) -> Any:
    resp = httpx.post(f"{settings().gateway_url}{path}", json=body, timeout=TIMEOUT,
                      headers={"Authorization": f"Bearer {settings().gateway_read_key}"})
    if resp.status_code == 409:
        raise ReauthRequired()
    resp.raise_for_status()
    return resp.json()


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
