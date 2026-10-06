"""Trigger the `uplift-clearing` CRE workflow and wait for its result callback.

Deployed: JSON-RPC `workflows.execute` to the CRE gateway with an ETH-signed JWT (authorizedKeys).
Local:    `cre workflow simulate` with the same payload (hackathon / no deploy access).
Either way the workflow posts its result to /hooks/cre, which lands in `cre_results`.
"""

import base64
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct

from . import db
from .config import settings


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


def trigger(action: str, payload: dict[str, Any], timeout_s: int = 600) -> dict[str, Any]:
    s = settings()
    request_id = str(uuid.uuid4())
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
        proc = subprocess.run(["cre", "workflow", "simulate", "uplift-clearing", *prebuilt, "--non-interactive",
                               "--trigger-index", "0", "--http-payload", json.dumps(workflow_input), "--target",
                               "local-simulation"], cwd=project, timeout=timeout_s, capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(f"CRE simulation failed: {(proc.stderr or proc.stdout)[-800:]}")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        row = db.one("select result from cre_results where request_id = %s", request_id)
        if row:
            return row["result"]
        time.sleep(3)
    raise TimeoutError(f"CRE {action} produced no result")
