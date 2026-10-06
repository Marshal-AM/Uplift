"""Register the Uplift agents on the Masumi registry (Cardano Preprod, Web3CardanoV2, Fixed tUSDM pricing).

- The 12 specialists register through the Kodosumi panel (their MIP-003 API is the Kodosumi Sumi endpoint).
- Nora has no Kodosumi flow; she registers directly on the MPS as an OpenApi agent (the Worker's OpenAPI spec)
  so her paid-Task fee has an agent identifier.

    uv run python infra/masumi/register.py            # register what is missing, then wait for confirmation
    uv run python infra/masumi/register.py --publish  # also push AGENT_IDENTIFIERS_JSON / AGENT_IDS_JSON to the Worker

Secrets are read from the Railway services' variables and never printed. Prerequisite: the MPS selling wallet holds
test ADA (registration mints an NFT).
"""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
LISTINGS = json.loads((ROOT / "infra" / "sokosumi" / "coworkers.json").read_text())
MPS = "https://mps-production-d96b.up.railway.app/api/v1"
KODO = "https://kodosumi-production-c7de.up.railway.app"
WORKER = "https://worker-production-47e0.up.railway.app"
TUSDM = "16a55b2a349361ff88c03788f93e1e966e5d689605d044fef722ddde0014df10745553444d"


def railway_vars(service: str) -> dict:
    out = subprocess.run(["railway", "variable", "list", "--service", service, "--json"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def mps_client() -> httpx.Client:
    return httpx.Client(base_url=MPS, headers={"token": railway_vars("mps")["ADMIN_KEY"]}, timeout=60)


def selling_wallet(mps: httpx.Client) -> dict:
    wallets = mps.get("/wallet/list", params={"take": 50, "walletType": "Selling"}).json()["data"]["Wallets"]
    return next(w for w in wallets if w["type"] == "Selling")


def registry(mps: httpx.Client) -> list[dict]:
    resp = mps.get("/registry", params={"network": "Preprod", "filterPaymentSourceType": "Web3CardanoV2", "limit": 100})
    resp.raise_for_status()
    return resp.json()["data"]["Assets"]


def register_specialists(vkey: str) -> None:
    with httpx.Client(base_url=KODO, timeout=120) as kodo:
        kodo.post("/api/login", json={"name": "admin", "password": railway_vars("kodosumi")["KODO_ADMIN_PASSWORD"]}
                  ).raise_for_status()
        expose = kodo.get("/expose/uplift").json()
        meta = expose.get("meta") or []
        urls = {m["url"].rstrip("/").rsplit("/", 1)[-1]: m["url"] for m in meta}
        data = {m["url"]: m.get("data") or "" for m in meta}
        for role, item in LISTINGS.items():
            if role == "nora":
                continue
            url = urls.get(role)
            if not url:
                raise SystemExit(f"flow for {role} not found in the uplift expose: {sorted(urls)}")
            status = kodo.get("/expose/uplift/registry", params={"flow_url": url}).json()
            if status.get("agentIdentifier") or status.get("state") not in (None, "", "not_registered", "NotRegistered"):
                print(f"{role:<7} {status.get('state')}")
                continue
            body = {"flow_url": url, "wallet_vkey": vkey, "pricing_type": "Fixed", "amount": item["price"],
                    "currency": "USDM"}
            if not _parses(data[url]):  # e.g. an unquoted ": " in a stored description
                body |= {"meta_yaml": re.sub(r"^(description|display): (.*)$",
                                             lambda m: f"{m.group(1)}: {json.dumps(m.group(2))}", data[url], flags=re.M),
                         "meta_etag": expose["etag"]}
            resp = kodo.post("/expose/uplift/registry", json=body)
            print(f"{role:<7} register → {resp.status_code} {resp.text[:160] if resp.status_code >= 300 else ''}")


def _parses(text: str) -> bool:
    try:
        return isinstance(yaml.safe_load(text), dict) and bool(yaml.safe_load(text).get("tags"))
    except yaml.YAMLError:
        return False


def register_nora(mps: httpx.Client, vkey: str) -> None:
    nora = LISTINGS["nora"]
    if any(a["name"] == nora["name"] for a in registry(mps)):
        print("nora    already registered")
        return
    source = mps.get("/payment-source", params={"take": 10}).json()["data"]["PaymentSources"]
    address = next(s["smartContractAddress"] for s in source if s["paymentSourceType"] == "Web3CardanoV2"
                   and s["network"] == "Preprod")
    resp = mps.post("/registry", json={
        "network": "Preprod", "type": "OpenApi", "sellingWalletVkey": vkey, "name": nora["name"],
        "description": nora["caption"], "openApiSpecUrl": f"{WORKER}/openapi.json",
        "Tags": nora["tags"][:15], "ExampleOutputs": [], "Capability": {"name": "claude-sonnet-5-5", "version": "1"},
        "Author": {"name": "Uplift", "organization": "Uplift"},
        "supportedPaymentSources": [{
            "chain": "Cardano", "network": "Preprod", "paymentSourceType": "Web3CardanoV2", "address": address,
            "pricing": {"pricingType": "Fixed", "fixed": [{"asset": TUSDM, "amount": str(round(nora["price"] * 1e6))}]}}],
    })
    print(f"nora    register → {resp.status_code} {resp.text[:200] if resp.status_code >= 300 else ''}")


def wait_confirmed(mps: httpx.Client, timeout_s: int = 1800) -> dict[str, str]:
    names = {item["name"]: role for role, item in LISTINGS.items()}
    deadline = time.time() + timeout_s
    while True:
        assets = [a for a in registry(mps) if a["name"] in names or any(a["name"].startswith(r.title()) for r in LISTINGS)]
        states = {a["name"]: a["state"] for a in assets}
        done = {a["name"]: a["agentIdentifier"] for a in assets if a["state"] in ("RegistrationConfirmed", "UpdateConfirmed")}
        failed = [n for n, s in states.items() if s in ("RegistrationFailed", "UpdateFailed")]
        print(f"confirmed {len(done)}/{len(LISTINGS)} · " + ", ".join(f"{n.split(' ·')[0]}={s}" for n, s in states.items()))
        if failed:
            raise SystemExit(f"registration failed for: {failed}")
        if len(done) >= len(LISTINGS) or time.time() > deadline:
            return {_role(n): ident for n, ident in done.items()}
        time.sleep(30)


def _role(name: str) -> str:
    return next(r for r in LISTINGS if name.lower().startswith(r))


def publish(identifiers: dict[str, str]) -> None:
    subprocess.run(["railway", "variable", "set", "AGENT_IDENTIFIERS_JSON", "--stdin", "--service", "worker",
                    "--skip-deploys", "--json"], input=json.dumps(identifiers), text=True, check=True,
                   capture_output=True, cwd=ROOT)
    print(f"AGENT_IDENTIFIERS_JSON set for {sorted(identifiers)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    with mps_client() as mps:
        vkey = selling_wallet(mps)["walletVkey"]
        register_specialists(vkey)
        register_nora(mps, vkey)
        identifiers = wait_confirmed(mps)
    if a.publish:
        publish(identifiers)
