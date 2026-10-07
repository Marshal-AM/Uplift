"""Register (or sync) the 13 Uplift coworkers on Sokosumi preprod and capture their runtime keys.

Prerequisite (once, interactive): `npx -y -p node@24 -p @masumi_network/sokosumi sokosumi --preprod auth login`

    uv run python infra/sokosumi/register.py --worker-url https://<worker>  [--workspace-id ORG_ID]

Idempotent: coworkers are matched by name and never registered twice. Runtime keys are shown by Core once,
so they go straight into infra/.secrets/coworkers.json (mode 0600, git-ignored) and are never printed.
`--push` then copies them to the Railway `worker` service (COWORKERS_JSON, via stdin) and to cre/.env.
"""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LISTINGS = json.loads((Path(__file__).parent / "coworkers.json").read_text())
SECRETS = ROOT / "infra" / ".secrets" / "coworkers.json"
CLI = ["npx", "-y", "-p", "node@24", "-p", "@masumi_network/sokosumi", "sokosumi", "--preprod"]
CHAT = set(LISTINGS)  # every coworker chats (one Responses endpoint routes on X-Coworker-Slug)


def soko(*args: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("SOKOSUMI_API_KEY", "SOKOSUMI_AUTH_TOKEN")}
    proc = subprocess.run([*CLI, *args, "--json"], capture_output=True, text=True, env=env)
    if proc.returncode:
        detail = "\n".join(x for x in (proc.stdout[-1500:], proc.stderr[-1500:]) if "EBADENGINE" not in x)
        raise SystemExit(f"sokosumi {args[0]} {args[1] if len(args) > 1 else ''} failed:\n{detail}")
    return json.loads(proc.stdout)


def load_secrets() -> dict:
    return json.loads(SECRETS.read_text()) if SECRETS.exists() else {}


def save_secrets(data: dict) -> None:
    SECRETS.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(SECRETS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)


def listing_args(role: str, worker_url: str) -> list[str]:
    item = LISTINGS[role]
    caps = "tasks,chat" if role in CHAT else "tasks"
    args = ["--caption", item["caption"], "--description", item["description"], "--capability", caps]
    if item.get("url"):  # website; the avatar is uploaded separately (Core takes it as a file, not a field)
        args += ["--url", item["url"]]
    if role in CHAT:
        args += ["--base-url", f"{worker_url.rstrip('/')}/v1"]
    return args


def register(worker_url: str, workspace_id: str | None) -> None:
    vendors = [v for v in soko("vendors", "me")["vendors"] if (v.get("role") or "").lower() == "admin"]
    if not vendors:
        raise SystemExit("No Vendor you administer. Create one: sokosumi --preprod vendors create --name Uplift "
                         "--slug uplift-<suffix> (needs membership in an organization workspace).")
    vendor_id = (vendors[0].get("vendor") or vendors[0]).get("id")
    secrets = load_secrets()
    owned = {c["id"]: c for c in soko("coworkers", "list", "--scope", "owned")["coworkers"]}
    target = ["--workspace-id", workspace_id] if workspace_id else ["--personal"]

    for role, item in LISTINGS.items():
        existing = owned.get(secrets.get(role, {}).get("id"))  # by id: the display name can change
        if existing:
            coworker = soko("coworkers", "update", existing["id"], "--name", item["name"],
                            *listing_args(role, worker_url))["coworker"]
            action = "synced"
        else:
            coworker = soko("coworkers", "register", "--vendor-id", vendor_id, "--name", item["name"],
                            *listing_args(role, worker_url), *target)["coworker"]
            action = "registered"
        entry = secrets.setdefault(role, {})
        entry |= {"id": coworker["id"], "slug": coworker.get("slug") or re.sub(r"[^a-z0-9]+", "-", item["name"].lower())}
        if not entry.get("key"):
            entry["key"] = soko("coworkers", "api-key", coworker["id"])["apiKey"]["token"]
            action += " + key"
        save_secrets(secrets)  # after every coworker, so a crash never loses a once-only key
        print(f"{role:<7} {action:<18} {coworker['id']}  {item['name']}")


def push() -> None:
    secrets = load_secrets()
    missing = [r for r in LISTINGS if not secrets.get(r, {}).get("key")]
    if missing:
        raise SystemExit(f"no keys yet for: {', '.join(missing)}")
    subprocess.run(["railway", "variable", "set", "COWORKERS_JSON", "--stdin", "--service", "worker",
                    "--skip-deploys", "--json"], input=json.dumps(secrets), text=True, check=True,
                   capture_output=True, cwd=ROOT)
    env_path = ROOT / "cre" / ".env"
    lines = [ln for ln in (env_path.read_text().splitlines() if env_path.exists() else [])
             if not ln.startswith("SOKO_KEY_")]
    lines += [f"SOKO_KEY_{r.upper()}={secrets[r]['key']}" for r in LISTINGS]
    fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("pushed COWORKERS_JSON to Railway `worker` and SOKO_KEY_* to cre/.env")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker-url", required=False)
    ap.add_argument("--workspace-id")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    if a.worker_url:
        register(a.worker_url, a.workspace_id)
    if a.push:
        push()
