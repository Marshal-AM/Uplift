"""Paid-Task flow on the Uplift Masumi payment node (mirrors masumi-network/demo-agent-token2049).

1. seller terms (POST /payment, Fixed registration) → 2. Task event `masumiPayment` (Core buys with the
Task owner's credits) → 3. wait for confirmed FundsLocked → … work … → 4. POST /payment/submit-result.
"""

import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from uplift_core import trace
from uplift_core.hashing import sha256_hex

from .clients import Sokosumi, SokosumiError, mps
from .config import settings


def _iso(t: datetime) -> str:
    """MPS date inputs: UTC, millisecond precision, `Z` suffix."""
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def request_terms(role: str, input_text: str, task_id: str, credits: float | None = None) -> dict[str, Any]:
    """Signed seller terms. `credits` sets the amount for a Dynamic-priced registration (Nora: the specialists
    used); Fixed registrations carry their own price."""
    s = settings()
    now = datetime.now(UTC)
    nonce = secrets.token_hex(10)
    body = {
        "network": s.network, "agentIdentifier": s.agent_identifiers[role], "paymentSourceType": "Web3CardanoV2",
        "supportedPaymentSourceIndex": 0, "inputHash": sha256_hex(input_text), "identifierFromPurchaser": nonce,
        "payByTime": _iso(now + timedelta(minutes=10)),
        "submitResultTime": _iso(now + timedelta(hours=6)),
        "metadata": f'{{"taskId":"{task_id}"}}',
    }
    if credits is not None:  # 1 credit = 1 tUSDM (6 decimals)
        body["RequestedFunds"] = [{"amount": str(round(credits * 1_000_000)), "unit": s.tusdm_unit}]
    with trace.span("Masumi", "Creating the payment request (seller terms)",
                    "on the Uplift payment node · Cardano preprod", task=task_id, kind="masumi.terms") as sp:
        payment = mps("/payment", body)
        bid = payment["blockchainIdentifier"]
        amount = sum(int(f["amount"]) for f in payment.get("RequestedFunds") or []) / 1_000_000
        sp.detail = (f"{amount:g} credits · {'dynamic price (the specialists used)' if credits is not None else 'fixed price'}"
                     + f" · pay by {_hhmm(payment['payByTime'])} · result due by {_hhmm(payment['submitResultTime'])}")
        sp.meta |= {"blockchain id": f"{bid[:10]}…{bid[-10:]}", "agent": f"{s.agent_identifiers[role][:14]}…",
                    "input hash": body["inputHash"][:16] + "…", "network": s.network}
    return {"nonce": nonce, "payment": payment}


def _hhmm(ms: Any) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, UTC).strftime("%H:%M UTC")


_escrow: dict[str, float] = {}  # blockchain id → when the lock was submitted (for the trace)


def purchase_payload(terms: dict[str, Any]) -> dict[str, Any]:
    p = terms["payment"]
    return {
        "blockchainIdentifier": p["blockchainIdentifier"], "agentIdentifier": p["agentIdentifier"],
        "sellerVkey": p["SmartContractWallet"]["walletVkey"], "submitResultTime": str(p["submitResultTime"]),
        "payByTime": str(p["payByTime"]), "unlockTime": str(p["unlockTime"]),
        "externalDisputeUnlockTime": str(p["externalDisputeUnlockTime"]), "inputHash": p["inputHash"],
        "identifierFromPurchaser": terms["nonce"], "paymentSourceType": "Web3CardanoV2",
        "supportedPaymentSourceIndex": 0,
        "Amounts": [{"amount": a["amount"], "unit": a["unit"]} for a in p["RequestedFunds"]],
        "PaymentSource": {"network": settings().network,
                          "smartContractAddress": p["PaymentSource"]["smartContractAddress"],
                          "policyId": p["PaymentSource"]["policyId"]},
    }


def charge(client: Sokosumi, task_id: str, terms: dict[str, Any], price: float) -> None:
    with trace.span("Sokosumi", f"Charging {price} credits to the merchant's workspace",
                    "Sokosumi buys the agent's Masumi payment with workspace credits", task=task_id,
                    kind="payment.charged", meta={"credits": price}):
        client.event(task_id, comment=f"Payment requested: {price} credits.", masumiPayment=purchase_payload(terms))
    bid = terms["payment"]["blockchainIdentifier"]
    _escrow.setdefault(bid, time.time())
    trace.emit("Cardano", "Locking the payment in escrow", "the smart contract holds it until the work is accepted; "
               "the agent starts meanwhile", status="running", span=f"escrow-{bid[-16:]}", task=task_id,
               kind="cardano.escrow")


def pay(client: Sokosumi, task_id: str, st: dict, role: str, input_text: str, price: float, save,
        dynamic: bool = False) -> bool:
    """Request terms once and post the payment. The terms are journaled before the charge, so a retry reuses them
    (until their pay-by deadline) instead of creating another payment request. False: the workspace has no
    credits (Sokosumi then marks the Task OUT_OF_CREDITS), which no retry can fix."""
    if not st.get("terms") or int(st["terms"]["payment"]["payByTime"]) / 1000 < time.time() + 60:
        st["terms"] = request_terms(role, input_text, task_id, price if dynamic else None)
        save()
    try:
        charge(client, task_id, st["terms"], price)
    except SokosumiError as exc:
        if exc.status == 422 and "insufficient_balance" in str(exc):
            return False
        raise
    return True


def _confirmed(payment: dict, state: str) -> bool:
    txs = [payment.get("CurrentTransaction") or {}, *(payment.get("TransactionHistory") or [])]
    return payment.get("onChainState") == state and any(
        t.get("status") == "Confirmed" and t.get("newOnChainState") == state for t in txs)


def lock_expired(terms: dict[str, Any]) -> bool:
    """The buyer never locked the escrow: past the pay-by deadline plus the payment node's 5-minute grace."""
    return int(terms["payment"]["payByTime"]) / 1000 + 300 < time.time()


def funds_locked(terms: dict[str, Any]) -> bool:
    bid = terms["payment"]["blockchainIdentifier"]
    payment = mps("/payment/resolve-blockchain-identifier", {
        "network": settings().network, "blockchainIdentifier": bid, "includeHistory": "true"})
    locked = _confirmed(payment, "FundsLocked")
    if locked and _escrow.get(bid) != 0:  # trace the confirmation once
        started = _escrow.get(bid)
        tx = (payment.get("CurrentTransaction") or {}).get("txHash") or ""
        trace.emit("Cardano", "Funds locked in escrow", "confirmed on Cardano preprod" + (f" · tx {tx[:12]}…" if tx else ""),
                   ms=(time.time() - started) * 1000 if started else None, span=f"escrow-{bid[-16:]}",
                   kind="cardano.escrow", meta={"tx": tx} if tx else None)
        _escrow[bid] = 0
    return locked


def wait_funds(terms: dict[str, Any], timeout_s: int = 900) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if funds_locked(terms):
            return
        time.sleep(15)
    raise TimeoutError("escrow was not funded in time")


def submit_result(terms: dict[str, Any], result_hash: str) -> None:
    with trace.span("Masumi", "Submitting the result hash on-chain",
                    f"result {result_hash[:12]}… · the seller can collect after the unlock time",
                    kind="masumi.result", meta={"result hash": result_hash}):
        mps("/payment/submit-result", {"network": settings().network,
                                       "blockchainIdentifier": terms["payment"]["blockchainIdentifier"],
                                       "submitResultHash": result_hash})
