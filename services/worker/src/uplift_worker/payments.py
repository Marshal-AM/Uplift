"""Paid-Task flow on the Uplift Masumi payment node (mirrors masumi-network/demo-agent-token2049).

1. seller terms (POST /payment, Fixed registration) → 2. Task event `masumiPayment` (Core buys with the
Task owner's credits) → 3. wait for confirmed FundsLocked → … work … → 4. POST /payment/submit-result.
"""

import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from uplift_core.hashing import sha256_hex

from .clients import Sokosumi, mps
from .config import settings


def request_terms(role: str, input_text: str, task_id: str) -> dict[str, Any]:
    s = settings()
    now = datetime.now(UTC)
    nonce = secrets.token_hex(10)
    body = {
        "network": s.network, "agentIdentifier": s.agent_identifiers[role], "paymentSourceType": "Web3CardanoV2",
        "supportedPaymentSourceIndex": 0, "inputHash": sha256_hex(input_text), "identifierFromPurchaser": nonce,
        "payByTime": (now + timedelta(minutes=10)).isoformat(),
        "submitResultTime": (now + timedelta(hours=6)).isoformat(),
        "metadata": f'{{"taskId":"{task_id}"}}',
    }
    payment = mps("/payment", body)
    return {"nonce": nonce, "payment": payment}


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
    client.event(task_id, comment=f"Payment requested: {price} credits.", masumiPayment=purchase_payload(terms))


def _confirmed(payment: dict, state: str) -> bool:
    txs = [payment.get("CurrentTransaction") or {}, *(payment.get("TransactionHistory") or [])]
    return payment.get("onChainState") == state and any(
        t.get("status") == "Confirmed" and t.get("newOnChainState") == state for t in txs)


def funds_locked(terms: dict[str, Any]) -> bool:
    payment = mps("/payment/resolve-blockchain-identifier", {
        "network": settings().network, "blockchainIdentifier": terms["payment"]["blockchainIdentifier"],
        "includeHistory": "true"})
    return _confirmed(payment, "FundsLocked")


def wait_funds(terms: dict[str, Any], timeout_s: int = 900) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if funds_locked(terms):
            return
        time.sleep(15)
    raise TimeoutError("escrow was not funded in time")


def submit_result(terms: dict[str, Any], result_hash: str) -> None:
    mps("/payment/submit-result", {"network": settings().network,
                                   "blockchainIdentifier": terms["payment"]["blockchainIdentifier"],
                                   "submitResultHash": result_hash})
