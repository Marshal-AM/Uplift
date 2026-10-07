"""Uplift's escrow payments on Cardano preprod, with their on-chain transactions and explorer links.

    uv run python e2e/payments.py              # the 10 newest payments
    uv run python e2e/payments.py --limit 30
    uv run python e2e/payments.py --json

Reads the Uplift Masumi payment node (MPS_URL, MPS_TOKEN from services/worker/.env). Each payment is one paid Task:
Sokosumi locks the credits as tUSDM in the Masumi escrow contract (FundsLocked), Uplift submits the result hash
(ResultSubmitted), and after the unlock time the seller wallet collects (Withdrawn) unless the buyer disputes.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
EXPLORER = "https://preprod.cexplorer.io"


def env() -> dict[str, str]:
    lines = (ROOT / "services" / "worker" / ".env").read_text().splitlines()
    return {k: v.strip().strip("'") for k, v in (x.split("=", 1) for x in lines if "=" in x and not x.startswith("#"))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    e = env()
    resp = httpx.get(f"{e['MPS_URL'].rstrip('/')}/payment", headers={"token": e["MPS_TOKEN"]}, timeout=60, params={
        "network": "Preprod", "filterPaymentSourceType": "Web3CardanoV2", "limit": a.limit, "includeHistory": "true"})
    resp.raise_for_status()
    payments = resp.json()["data"].get("Payments", [])
    rows = []
    for p in payments:
        txs = [t for t in [p.get("CurrentTransaction") or {}, *(p.get("TransactionHistory") or [])] if t.get("txHash")]
        seen, steps = set(), []
        for t in reversed(txs):  # oldest first
            if t["txHash"] not in seen:
                seen.add(t["txHash"])
                steps.append({"state": t.get("newOnChainState") or t.get("status"), "tx": t["txHash"],
                              "url": f"{EXPLORER}/tx/{t['txHash']}"})
        rows.append({"created": p.get("createdAt"), "credits": sum(int(f["amount"]) for f in p.get("RequestedFunds") or []) / 1e6,
                     "state": p.get("onChainState"), "task": _task(p.get("metadata")),
                     "blockchain_id": p.get("blockchainIdentifier"), "transactions": steps,
                     "contract": (p.get("PaymentSource") or {}).get("smartContractAddress")})
    if a.json:
        print(json.dumps(rows, indent=1))
        return
    if rows:
        print(f"Escrow contract: {EXPLORER}/address/{rows[0]['contract']}\n")
    for r in rows:
        when = datetime.fromisoformat(r["created"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
        print(f"{when}  {r['credits']:>5g} credits  {r['state'] or '-':<16} Task {r['task'] or '-'}")
        for s in r["transactions"]:
            print(f"    {s['state']:<16} {s['url']}")


def _task(metadata: str | None) -> str | None:
    try:
        return json.loads(metadata or "{}").get("taskId")
    except ValueError:
        return None


if __name__ == "__main__":
    main()
