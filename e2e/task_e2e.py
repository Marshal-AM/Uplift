"""Act as a merchant on Sokosumi preprod: create a Task for an Uplift coworker and follow it to the end.

    uv run python e2e/task_e2e.py create quinn "Audit my product" "Audit https://<store>/products/<handle> for US shoppers"
    uv run python e2e/task_e2e.py watch TASK_ID            # stream the activity until COMPLETED/FAILED or the merchant must act
    uv run python e2e/task_e2e.py reply TASK_ID "approve"  # answer a question / approve a change set

Uses your own `sokosumi --preprod auth login` session, exactly like a merchant using the CLI.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ["npx", "-y", "-p", "node@24", "-p", "@masumi_network/sokosumi", "sokosumi", "--preprod"]
WAITING = {"AUTHENTICATION_REQUIRED", "INPUT_REQUIRED", "APPROVAL_REQUIRED"}
DONE = {"COMPLETED", "FAILED", "CANCELED", "OUT_OF_CREDITS"}


def soko(*args: str) -> dict:
    proc = subprocess.run([*CLI, *args, "--json"], capture_output=True, text=True)
    if proc.returncode:
        sys.exit(f"sokosumi {' '.join(args[:2])} failed: {proc.stdout[-800:]}{proc.stderr[-400:]}")
    return json.loads(proc.stdout)


def coworker_id(role: str) -> str:
    return json.loads((ROOT / "infra" / ".secrets" / "coworkers.json").read_text())[role]["id"]


def create(role: str, name: str, description: str) -> None:
    task = soko("tasks", "create", "--personal", "--coworker-id", coworker_id(role), "--name", name,
                "--description", description, "--status", "READY")
    task = task.get("task", task)
    print(f"task {task['id']} created for {role}; watch with: uv run python e2e/task_e2e.py watch {task['id']}")


def watch(task_id: str, timeout_s: int = 3600) -> None:
    seen: set[str] = set()
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        events = soko("tasks", "events", task_id).get("events", [])
        for e in events:
            if e["id"] in seen:
                continue
            seen.add(e["id"])
            who = (e.get("actor") or {}).get("type", "system")
            line = f"[{e['createdAt'][11:19]}] {who:<9} {e.get('status') or '':<24} {(e.get('comment') or '').strip()}"
            print(line[:2000])
            if e.get("authenticationUrl"):
                print(f"           → open to connect your store: {e['authenticationUrl']}")
        status = next((e["status"] for e in reversed(events) if e.get("status")), None)
        if status in DONE:
            print(f"\nTask finished: {status}")
            return
        if status in WAITING and (events[-1].get("actor") or {}).get("type") == "coworker":
            print(f"\nWaiting for you ({status}). Reply with: uv run python e2e/task_e2e.py reply {task_id} \"...\"")
            return
        time.sleep(10)
    sys.exit("timed out")


def reply(task_id: str, comment: str) -> None:
    soko("tasks", "comment", task_id, "--comment", comment)
    print("sent")


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:]
    {"create": create, "watch": watch, "reply": reply}[cmd](*rest)
