"""Record finished Sokosumi Tasks into runs/: brief, every event, payment receipt, cost, Chainlink verdicts and the
full deliverables (manifest + artifact files) — the evidence of an end-to-end run.

    uv run python e2e/record_run.py runs/<folder> TASK_ID ROLE   # one Task (Nora: also every specialist run)

Reads the merchant's Sokosumi CLI session (tasks), the coworker key from infra/.secrets (receipt) and the artifact
bucket with the local .env AWS keys. Signed S3 links are stripped before anything is written.
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import boto3
import httpx

ROOT = Path(__file__).resolve().parents[1]
CLI = ["npx", "-y", "-p", "node@24", "-p", "@masumi_network/sokosumi", "sokosumi", "--preprod"]
API = "https://api.preprod.sokosumi.com"
ENV = {k: v.strip().strip("'") for k, v in (line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines()
                                             if "=" in line and not line.startswith("#"))}
KEYS = json.loads((ROOT / "infra" / ".secrets" / "coworkers.json").read_text())
S3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id=ENV["AWS_ACCESS_KEY_ID"],
                  aws_secret_access_key=ENV["AWS_SECRET_ACCESS_KEY"])
BUCKET = ENV["ARTIFACT_BUCKET"]


def soko(*args: str) -> dict:
    for attempt in range(3):  # the CLI occasionally returns an empty or partial body; ask again
        out = subprocess.run([*CLI, *args, "--json"], capture_output=True, text=True).stdout
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            if attempt == 2:
                raise
    raise RuntimeError("unreachable")


def unsign(value):
    """Drop the query string (signature, key id, expiry) from every presigned S3 link."""
    if isinstance(value, dict):
        return {k: unsign(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unsign(v) for v in value]
    if isinstance(value, str) and ".amazonaws.com/" in value and "?" in value:
        return value.split("?")[0]
    return value


def manifests_for(task_id: str, since: datetime) -> list[dict]:
    """Every deliverable produced for this Task (standalone: job_or_task_id = task; Nora: task:node)."""
    found = []
    for page in S3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix="artifacts/"):
        for o in page.get("Contents", []):
            if o["Key"].endswith("/manifest.json") and o["LastModified"] >= since:
                m = json.loads(S3.get_object(Bucket=BUCKET, Key=o["Key"])["Body"].read())
                if str(m.get("job_or_task_id", "")).split(":")[0] == task_id:
                    found.append({"result_hash": o["Key"].split("/")[1], "at": o["LastModified"].isoformat(), **m})
    return sorted(found, key=lambda m: m["at"])


def save_deliverable(m: dict, folder: Path) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "manifest.json").write_text(json.dumps(unsign(m), indent=2, ensure_ascii=False))
    names = []
    for a in m.get("artifacts", []):
        key = a["url"].split(".com/")[1].split("?")[0]
        path = folder / a["name"].replace("/", "-")
        path.write_bytes(S3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
        names.append(path.name)
    bundle = m.get("verification_bundle", {}).get("url")
    if bundle:
        key = bundle.split(".com/")[1].split("?")[0]
        (folder / "verification_bundle.json").write_bytes(S3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    return names


def record(out: Path, task_id: str, role: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    task = soko("tasks", "get", task_id)
    task = task.get("task", task)
    events = soko("tasks", "events", task_id)["events"]
    receipt = None
    for _ in range(3):  # the receipt endpoint occasionally answers with an empty body
        try:
            receipt = httpx.get(f"{API}/v1/tasks/{task_id}/receipt", timeout=30,
                                headers={"Authorization": f"Bearer {KEYS[role]['key']}"}).json().get("data")
            break
        except ValueError:
            continue
    (out / "events.json").write_text(json.dumps(events, indent=2, ensure_ascii=False))
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2))
    t0 = datetime.fromisoformat(task["createdAt"].replace("Z", "+00:00"))
    delivered = manifests_for(task_id, t0)
    files = {}
    for i, m in enumerate(delivered, 1):
        node = str(m.get("job_or_task_id", "")).split(":")[1] if ":" in str(m.get("job_or_task_id", "")) else m["role"]
        files[f"{i:02d}-{node}"] = (m["role"], save_deliverable(m, out / "deliverables" / f"{i:02d}-{node}"))
    end = datetime.fromisoformat(events[-1]["createdAt"].replace("Z", "+00:00"))
    credits = sum(e.get("credits") or 0 for e in events) / 100
    verdicts = [re.sub(r"\s+", " ", e["comment"]) for e in events
                if re.search(r"Chainlink(:| verification:) \*\*(PASS|FAIL)", e.get("comment") or "")]
    lines = [f"# {task['name']}", "",
             f"- **Coworker:** {task.get('coworkerName')} (`{role}`)", f"- **Task:** `{task_id}`",
             f"- **Final status:** {task['status']}", f"- **Credits charged:** {credits}",
             f"- **Payment claim:** {receipt.get('claimStatus') if receipt else '—'} · on-chain "
             f"{receipt.get('onChainState') if receipt else '—'}",
             f"- **Elapsed (created → last event):** {(end - t0).total_seconds():.0f} s", "",
             "## Brief (exactly as given)", "", "```", task.get("description") or "", "```", "",
             "## Chainlink verdicts", "", *[f"- {v}" for v in verdicts], "",
             "## Timeline", "", "| t+ | actor | status | event |", "|---|---|---|---|"]
    for e in events:
        dt = (datetime.fromisoformat(e["createdAt"].replace("Z", "+00:00")) - t0).total_seconds()
        text = re.sub(r"\s+", " ", (e.get("comment") or "")).replace("|", "\\|")[:240]
        lines.append(f"| {dt:.0f}s | {(e.get('actor') or {}).get('type', '')} | {e.get('status') or ''} | {text} |")
    final = next((e.get("comment") for e in reversed(events) if e.get("status") in ("COMPLETED", "FAILED")), "")
    lines += ["", "## Final message", "", final or "—", "", "## Deliverables", ""]
    for name, (r, names) in files.items():
        lines.append(f"- `deliverables/{name}/` ({r}): " + ", ".join(f"`{n}`" for n in names))
    (out / "README.md").write_text("\n".join(lines) + "\n")
    return {"task": task_id, "role": role, "status": task["status"], "credits": credits,
            "claim": receipt.get("claimStatus") if receipt else None, "elapsed_s": round((end - t0).total_seconds()),
            "verdicts": verdicts, "folder": str(out.relative_to(ROOT))}


if __name__ == "__main__":
    print(json.dumps(record(ROOT / sys.argv[1], sys.argv[2], sys.argv[3]), indent=1))
