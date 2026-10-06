"""End-to-end check of the deployed Connection Gateway against a real Shopify dev store.

Run with the gateway's Railway variables so no secret is printed:
    railway run --service gateway -- uv run python e2e/gateway_e2e.py connect   # prints the Authenticate link
    railway run --service gateway -- uv run python e2e/gateway_e2e.py verify    # after approving in Shopify
"""

import os
import secrets
import sys
import time

import httpx
import jwt
from uplift_core.hashing import change_hash

BASE = os.environ["PUBLIC_BASE_URL"]
USER = os.environ.get("E2E_SOKOSUMI_USER", "e2e-user")
ORG = os.environ.get("E2E_SOKOSUMI_ORG", "")
READ = {"Authorization": f"Bearer {os.environ['GATEWAY_READ_KEY']}"}
WRITE = {"Authorization": f"Bearer {os.environ['GATEWAY_WRITE_KEY']}"}
LINK = {"user_id": USER, "org_id": ORG}


def connect() -> None:
    state = jwt.encode(
        {"task_id": "e2e", "user_id": USER, "org_id": ORG, "coworker": "nora",
         "nonce": secrets.token_hex(16), "exp": int(time.time()) + 3600},
        os.environ["CONNECT_STATE_SECRET"], algorithm="HS256",
    )
    print(f"{BASE}/connect/shopify/start?state={state}")


def post(path: str, body: dict, headers: dict) -> httpx.Response:
    return httpx.post(f"{BASE}{path}", json=body, headers=headers, timeout=60)


def verify() -> None:
    status = post("/v1/read/status", LINK, READ).json()
    print("status:", status)
    assert status["connected"], "store is not connected"

    products = post("/v1/read/graphql", {**LINK, "query": "{ products(first: 1) { nodes { id title } } }"},
                    READ).json()
    product_id = products["products"]["nodes"][0]["id"]
    snap = post("/v1/read/snapshot", {**LINK, "product_id": product_id}, READ).json()
    original_seo = snap["product"]["seo"]
    print("product:", product_id, "| seo before:", original_seo)

    refused = post("/v1/read/graphql", {**LINK, "query": "mutation { tagsAdd(id: \"x\", tags: []) { node { id } } }"},
                   READ)
    assert refused.status_code == 403, refused.text

    new_title = f"Uplift e2e {secrets.token_hex(3)}"
    changeset = [{"op": "product.update", "product_id": product_id, "fields": {"seo": {"title": new_title}}}]
    body = {**LINK, "change_hash": change_hash(changeset), "changeset": changeset}
    assert post("/v1/write/apply", body, READ).status_code == 401, "read key must not write"
    first = post("/v1/write/apply", body, WRITE)
    assert first.status_code == 200, first.text
    replay = post("/v1/write/apply", body, WRITE).json()
    assert replay == first.json(), "replayed changeset must return the stored result"

    after = post("/v1/read/snapshot", {**LINK, "product_id": product_id}, READ).json()["product"]["seo"]
    print("seo after:", after)
    assert after["title"] == new_title

    revert = [{"op": "product.update", "product_id": product_id,
               "fields": {"seo": {"title": original_seo["title"] or "", "description": original_seo["description"] or ""}}}]
    r = post("/v1/write/apply", {**LINK, "change_hash": change_hash(revert), "changeset": revert}, WRITE)
    assert r.status_code == 200, r.text
    print("reverted; gateway e2e passed")


if __name__ == "__main__":
    {"connect": connect, "verify": verify}[sys.argv[1]]()
