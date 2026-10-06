"""Uplift Connection Gateway.

- /connect/shopify/*   merchant connects (or reconnects) a store from the Sokosumi Authenticate button
- /v1/read/*           Worker, agents (job-scoped capability) and CRE read store data
- /v1/write/apply      CRE-only: executes an approved changeset
- /webhooks/shopify    uninstall and compliance webhooks
"""

import hashlib
import hmac
import html
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

import graphql
import httpx
import jwt
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from uplift_core import changeset as cs
from uplift_core.hashing import change_hash

from . import db, links, shopify
from .config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.open_pool()
    yield
    db.close_pool()


log = logging.getLogger("uplift.gateway")
app = FastAPI(title="Uplift Connection Gateway", lifespan=lifespan)


@app.exception_handler(shopify.ShopifyError)
async def _shopify_error(_: Request, exc: shopify.ShopifyError):
    return JSONResponse({"error": "shopify_error", "detail": exc.args[0]}, status_code=502)


@app.get("/health")
def health():
    return {"ok": True}


# --- connect / reconnect ---------------------------------------------------------------------

def _decode_state(state: str) -> dict[str, Any]:
    try:
        return jwt.decode(state, settings().connect_state_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(400, "This connect link is invalid or expired. Request a new one in Sokosumi.") from exc


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        f"<title>{title}</title><body style='font-family:system-ui;max-width:28rem;margin:4rem auto;padding:0 1rem'>"
        f"<h2>{title}</h2>{body}</body>"
    )


@app.get("/connect/shopify/start")
def connect_start(state: str, shop: str | None = None):
    _decode_state(state)
    if not shop:
        return _page(
            "Connect your store",
            "<form><input type=hidden name=state value='" + html.escape(state) + "'>"
            "<label>Store domain<br><input name=shop placeholder='your-store.myshopify.com' required "
            "style='width:100%;padding:.5rem;margin:.5rem 0'></label>"
            "<button style='padding:.5rem 1rem'>Continue to Shopify</button></form>",
        )
    try:
        shop_domain = shopify.normalize_shop(shop)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(shopify.authorize_url(shop_domain, state), status_code=302)


@app.get("/connect/shopify/callback")
def connect_callback(request: Request):
    params = dict(request.query_params)
    if not shopify.valid_oauth_hmac(params):
        raise HTTPException(400, "Invalid Shopify signature")
    claims = _decode_state(params.get("state", ""))
    shop_domain = shopify.normalize_shop(params.get("shop", ""))
    try:
        db.execute("insert into used_nonces (nonce) values (%s)", claims["nonce"])
    except Exception as exc:
        raise HTTPException(400, "This connect link was already used. Request a new one in Sokosumi.") from exc

    grant = shopify.exchange_code(shop_domain, params["code"])
    links.save(claims["user_id"], claims.get("org_id", ""), "shopify", shop_domain, grant)
    _notify_worker({"event": "store_connected", "platform": "shopify", "shop": shop_domain, **claims})
    return _page("Store connected", f"<p><b>{html.escape(shop_domain)}</b> is connected to Uplift. "
                                    "You can close this tab and return to Sokosumi.</p>")


def _notify_worker(payload: dict[str, Any]) -> None:
    s = settings()
    if not s.worker_hook_url:
        return
    body = json.dumps(payload).encode()
    signature = hmac.new(s.worker_hook_secret.encode(), body, hashlib.sha256).hexdigest()
    try:  # the Worker also re-checks connection status on its own poll, so a missed nudge only adds latency
        httpx.post(s.worker_hook_url, content=body, timeout=10,
                   headers={"Content-Type": "application/json", "X-Uplift-Signature": signature})
    except httpx.HTTPError as exc:
        log.warning("worker notify failed: %s", exc)


# --- auth -------------------------------------------------------------------------------------

class LinkRef(BaseModel):
    user_id: str | None = None
    org_id: str = ""


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    return authorization.removeprefix("Bearer ")


def read_identity(ref: LinkRef, authorization: str | None = Header(None)) -> tuple[str, str]:
    """Read key: caller names the link. Job-scoped capability: the link comes from the token."""
    token = _bearer(authorization)
    if hmac.compare_digest(token, settings().gateway_read_key):
        if not ref.user_id:
            raise HTTPException(400, "user_id is required")
        return ref.user_id, ref.org_id
    try:
        claims = jwt.decode(token, settings().read_capability_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "invalid read credential") from exc
    return claims["user_id"], claims.get("org_id", "")


def require_write_key(authorization: str | None = Header(None)) -> None:
    if not hmac.compare_digest(_bearer(authorization), settings().gateway_write_key):
        raise HTTPException(401, "invalid write credential")


def _shopify_link(user_id: str, org_id: str) -> links.Link:
    link = links.get(user_id, org_id, "shopify")
    if not link or link.status != "valid":
        raise HTTPException(409, {"error": "reauth_required", "platform": "shopify"})
    return link


def _call(link: links.Link, fn, *args):
    try:
        return fn(link.account, link.token, *args)
    except shopify.ReauthRequired as exc:
        links.invalidate(link.id)
        raise HTTPException(409, {"error": "reauth_required", "platform": "shopify"}) from exc


# --- read API ---------------------------------------------------------------------------------

class StatusRequest(LinkRef):
    platform: str = "shopify"


@app.post("/v1/read/status")
def read_status(body: StatusRequest, authorization: str | None = Header(None)):
    user_id, org_id = read_identity(body, authorization)
    result = links.status(user_id, org_id, body.platform)
    if result["connected"] and body.platform == "shopify":
        # cheap liveness probe so dead tokens are caught before work starts
        link = _shopify_link(user_id, org_id)
        _call(link, shopify.graphql, "{ shop { id } }")
    return result


class SnapshotRequest(LinkRef):
    product_id: str


@app.post("/v1/read/snapshot")
def read_snapshot(body: SnapshotRequest, authorization: str | None = Header(None)):
    user_id, org_id = read_identity(body, authorization)
    return _call(_shopify_link(user_id, org_id), shopify.snapshot, body.product_id)


class GraphQLRequest(LinkRef):
    query: str
    variables: dict[str, Any] = {}


@app.post("/v1/read/graphql")
def read_graphql(body: GraphQLRequest, authorization: str | None = Header(None)):
    user_id, org_id = read_identity(body, authorization)
    try:
        document = graphql.parse(body.query)
    except graphql.GraphQLSyntaxError as exc:
        raise HTTPException(400, f"invalid query: {exc.message}") from exc
    if any(getattr(d, "operation", None) != graphql.OperationType.QUERY for d in document.definitions):
        raise HTTPException(403, "read API accepts queries only")
    return _call(_shopify_link(user_id, org_id), shopify.graphql, body.query, body.variables)


# --- write API (CRE only) ---------------------------------------------------------------------

class ApplyRequest(LinkRef):
    change_hash: str
    changeset: list[dict[str, Any]]


@app.post("/v1/write/apply", dependencies=[Depends(require_write_key)])
def write_apply(body: ApplyRequest):
    if change_hash(body.changeset) != body.change_hash:
        raise HTTPException(400, "change_hash does not match changeset")
    for op in body.changeset:
        try:
            cs.validate(op)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    done = db.fetch_one("select result from applied_changesets where change_hash = %s", body.change_hash)
    if done:
        return done["result"]  # CRE retries are safe

    link = _shopify_link(body.user_id, body.org_id)
    applied = []
    for op in body.changeset:
        try:
            applied.append(_call(link, shopify.apply_op, op))
        except shopify.ShopifyError as exc:
            return JSONResponse({"error": "op_failed", "applied": applied, "detail": exc.args[0]}, 502)
    result = {"change_hash": body.change_hash, "applied": applied}
    db.execute("insert into applied_changesets (change_hash, link_id, result) values (%s, %s, %s)",
               body.change_hash, link.id, json.dumps(result))
    return result


# --- webhooks ---------------------------------------------------------------------------------

@app.post("/webhooks/shopify")
async def shopify_webhook(request: Request):
    body = await request.body()
    if not shopify.valid_webhook_hmac(body, request.headers.get("X-Shopify-Hmac-Sha256", "")):
        raise HTTPException(401, "invalid webhook signature")
    topic = request.headers.get("X-Shopify-Topic", "")
    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
    if topic in ("app/uninstalled", "shop/redact"):
        links.delete_account("shopify", shop_domain)
    # customers/data_request and customers/redact: Uplift stores no customer data
    return {"ok": True}


def run() -> None:
    uvicorn.run("uplift_gateway.app:app", host="0.0.0.0", port=settings().port)
