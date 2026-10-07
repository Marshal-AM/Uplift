"""Trigger the `uplift-clearing` CRE workflow and wait for its result callback.

Deployed: JSON-RPC `workflows.execute` to the CRE gateway with an ETH-signed JWT (authorizedKeys).
Local:    `cre workflow simulate` with the same payload (hackathon / no deploy access).
Either way the workflow posts its result to /hooks/cre, which lands in `cre_results`.
"""

import base64
import contextlib
import hashlib
import json
import logging
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from uplift_core import trace

from . import db
from .clients import _name
from .config import settings

log = logging.getLogger("uplift.worker")
_compile = threading.Lock()
CALLBACK_S = 120  # a simulation has already posted its callback when it exits  # a source build writes one shared temp file; the shipped WASM needs no lock


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _jwt(body: dict[str, Any]) -> str:
    account = Account.from_key(settings().cre_trigger_private_key)
    digest = "0x" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "ETH", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(json.dumps({"digest": digest, "iss": account.address, "iat": now, "exp": now + 240,
                                  "jti": str(uuid.uuid4())}, separators=(",", ":")).encode())
    signature = account.sign_message(encode_defunct(text=f"{header}.{payload}")).signature
    return f"{header}.{payload}.{_b64url(bytes(signature))}"


def trigger(action: str, payload: dict[str, Any], timeout_s: int = 240, agent: str | None = None) -> dict[str, Any]:
    """`timeout_s` bounds the workflow run (checks take 5–25 s); the result callback then has CALLBACK_S. A timeout
    raises, and the caller's journal retries the step on its next pass."""
    """`agent`: who the live trace attributes a verify to (Nora's plan node); default the payload's role."""
    role = agent or payload.get("role") or payload.get("coworker")
    step = f"Verifying {_name(role)}'s work" if action == "verify" else "Publishing the approved changes to Shopify"
    where = "deployed workflow" if settings().cre_trigger_url else "workflow simulation"
    with trace.span("Chainlink CRE", step, f"uplift-clearing · {where} · hash-checks, scores and signs off",
                    task=payload.get("task_id"), agent=role if action == "verify" else None,
                    kind=f"cre.{action}") as sp:
        result = _trigger(action, payload, timeout_s)
        if action == "verify":
            sp.status = "ok" if result.get("outcome") == "PASS" else "fail"
            sp.detail = f"{result.get('outcome')} · {result.get('score')}/100 (pass mark {result.get('pass_mark', '—')})"
            sp.meta |= {"checks": result.get("checks", []), "reasons": result.get("reasons", []),
                        "judge": result.get("judge_note"), "outcome": result.get("outcome"),
                        "score": result.get("score")}
        elif result.get("published"):
            after = result.get("after_score")
            sp.detail = f"{result.get('applied')} changes applied through the gateway's write API" + (
                f" · core listing score now {after}/95" if after is not None else "")
            sp.meta |= {"applied": result.get("applied"), "after_score": after}
        else:
            sp.status = "fail"
            sp.detail = f"refused: {result.get('reason')}"
        return result


def _trigger(action: str, payload: dict[str, Any], timeout_s: int) -> dict[str, Any]:
    s = settings()
    request_id = str(uuid.uuid4())
    started = time.time()
    workflow_input = {"action": action, "request_id": request_id,
                      "callback_url": f"{s.public_url}/hooks/cre", **payload}
    if s.cre_trigger_url:
        body = {"id": request_id, "jsonrpc": "2.0", "method": "workflows.execute",
                "params": {"input": workflow_input, "workflow": {"workflowID": s.cre_workflow_id}}}
        resp = httpx.post(s.cre_trigger_url, json=body, timeout=30,
                          headers={"Authorization": f"Bearer {_jwt(body)}"})
        resp.raise_for_status()
        if "error" in resp.json():
            raise RuntimeError(f"CRE trigger rejected: {resp.json()['error']}")
    else:
        project = (Path(__file__).resolve().parents[2] / s.cre_project_dir).resolve()
        prebuilt = ["--wasm", "./uplift-clearing.wasm"] if (project / "uplift-clearing" / "uplift-clearing.wasm").exists() \
            else []  # the Worker image ships the compiled workflow; a dev checkout compiles from source
        with contextlib.nullcontext() if prebuilt else _compile:
            proc = subprocess.run(["cre", "workflow", "simulate", "uplift-clearing", *prebuilt, "--non-interactive",
                                   "--trigger-index", "0", "--http-payload", json.dumps(workflow_input), "--target",
                                   "local-simulation"], cwd=project, timeout=timeout_s, capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(f"CRE simulation failed: {(proc.stderr or proc.stdout)[-800:]}")
    triggered = time.time()
    deadline = triggered + (CALLBACK_S if not s.cre_trigger_url else timeout_s)
    while time.time() < deadline:
        row = db.one("select result from cre_results where request_id = %s", request_id)
        if row:
            log.info("timing CRE %s role=%s task=%s: %.0fs to run, %.0fs more for the callback", action,
                     payload.get("role") or payload.get("coworker"), payload.get("task_id"), triggered - started,
                     time.time() - triggered)
            return row["result"]
        time.sleep(1)
    raise TimeoutError(f"CRE {action} produced no result")
