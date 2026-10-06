"""Shopify adapter: OAuth helpers, Admin GraphQL calls, product snapshot, changeset execution."""

import base64
import hashlib
import hmac
import re
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import settings

SHOP_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$")


class ReauthRequired(Exception):
    """Shopify rejected the stored token; the merchant must reconnect."""


class ShopifyError(Exception):
    pass


def normalize_shop(shop: str) -> str:
    shop = shop.strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0]
    if "." not in shop:
        shop = f"{shop}.myshopify.com"
    if not SHOP_RE.match(shop):
        raise ValueError("Enter your store's myshopify.com domain")
    return shop


def authorize_url(shop: str, state: str) -> str:
    s = settings()
    query = urlencode({
        "client_id": s.shopify_client_id,
        "scope": s.shopify_scopes,
        "redirect_uri": f"{s.public_base_url}/connect/shopify/callback",
        "state": state,
    })
    return f"https://{shop}/admin/oauth/authorize?{query}"


def valid_oauth_hmac(params: dict[str, str]) -> bool:
    received = params.get("hmac", "")
    message = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "hmac")
    digest = hmac.new(settings().shopify_client_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, received)


def valid_webhook_hmac(body: bytes, header: str) -> bool:
    digest = hmac.new(settings().shopify_client_secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), header or "")


def _token_request(shop: str, grant: dict[str, Any]) -> dict[str, Any]:
    s = settings()
    resp = httpx.post(f"https://{shop}/admin/oauth/access_token", timeout=20,
                      json={"client_id": s.shopify_client_id, "client_secret": s.shopify_client_secret, **grant})
    if resp.status_code in (400, 401):
        raise ReauthRequired()
    resp.raise_for_status()
    return resp.json()  # {access_token, expires_in, refresh_token, refresh_token_expires_in, scope}


def exchange_code(shop: str, code: str) -> dict[str, Any]:
    """Expiring offline token (Shopify no longer accepts non-expiring ones on the Admin API)."""
    return _token_request(shop, {"code": code, "expiring": 1})


def refresh(shop: str, refresh_token: str) -> dict[str, Any]:
    """Returns a new access token and a new refresh token (the old refresh token stops working)."""
    return _token_request(shop, {"grant_type": "refresh_token", "refresh_token": refresh_token})


def graphql(shop: str, token: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    resp = httpx.post(
        f"https://{shop}/admin/api/{settings().shopify_api_version}/graphql.json",
        headers={"X-Shopify-Access-Token": token},
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    if resp.status_code == 401:
        raise ReauthRequired()
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise ShopifyError(body["errors"])
    return body["data"]


SNAPSHOT_QUERY = """
query Snapshot($id: ID!) {
  shop { id name primaryDomain { url } currencyCode }
  product(id: $id) {
    id title handle descriptionHtml productType vendor tags status onlineStoreUrl
    seo { title description }
    category { id fullName }
    media(first: 50) { nodes { id alt mediaContentType ... on MediaImage { image { url width height } } } }
    variants(first: 100) { nodes { id title sku barcode price compareAtPrice
      inventoryItem { unitCost { amount currencyCode } } } }
    collections(first: 25) { nodes { id title handle } }
    metafields(first: 50) { nodes { namespace key type value } }
  }
}
"""


def snapshot(shop: str, token: str, product_id: str) -> dict[str, Any]:
    data = graphql(shop, token, SNAPSHOT_QUERY, {"id": product_id})
    if not data["product"]:
        raise ShopifyError(f"product not found: {product_id}")
    return data


# --- changeset execution -------------------------------------------------------------------

_MUTATIONS: dict[str, str] = {
    "product.update": """mutation($product: ProductUpdateInput!) {
        productUpdate(product: $product) { product { id } userErrors { field message } } }""",
    "tags_add": """mutation($id: ID!, $tags: [String!]!) {
        tagsAdd(id: $id, tags: $tags) { node { id } userErrors { field message } } }""",
    "metafields.set": """mutation($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) { metafields { id } userErrors { field message } } }""",
    "collection.add_products": """mutation($id: ID!, $productIds: [ID!]!) {
        collectionAddProducts(id: $id, productIds: $productIds) { collection { id } userErrors { field message } } }""",
    "collection.create": """mutation($input: CollectionInput!) {
        collectionCreate(input: $input) { collection { id } userErrors { field message } } }""",
    "media.add": """mutation($product: ProductUpdateInput!, $media: [CreateMediaInput!]) {
        productUpdate(product: $product, media: $media) { product { id } userErrors { field message } } }""",
    "media.reorder": """mutation($id: ID!, $moves: [MoveInput!]!) {
        productReorderMedia(id: $id, moves: $moves) { job { id } mediaUserErrors { field message } } }""",
    "media.update_alt": """mutation($files: [FileUpdateInput!]!) {
        fileUpdate(files: $files) { files { id } userErrors { field message } } }""",
    "translations.register": """mutation($resourceId: ID!, $translations: [TranslationInput!]!) {
        translationsRegister(resourceId: $resourceId, translations: $translations) {
          translations { key locale } userErrors { field message } } }""",
    "discount.create": """mutation($basicCodeDiscount: DiscountCodeBasicInput!) {
        discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
          codeDiscountNode { id } userErrors { field message } } }""",
    "article.create": """mutation($article: ArticleCreateInput!) {
        articleCreate(article: $article) { article { id } userErrors { field message } } }""",
}


def _variables(op: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    name = op["op"]
    if name == "product.update":
        product = {"id": op["product_id"], **op["fields"]}
        if "handle" in op["fields"]:
            product["redirectNewHandle"] = True
        return name, {"product": product}
    if name in ("product.tags_add", "product.taxonomy_tags_add"):
        return "tags_add", {"id": op["product_id"], "tags": op["tags"]}
    if name == "metafields.set":
        return name, {"metafields": [{"ownerId": op["owner_id"], **m} for m in op["metafields"]]}
    if name == "collection.add_products":
        return name, {"id": op["collection_id"], "productIds": op["product_ids"]}
    if name == "media.add":
        media = [{"originalSource": m["url"], "alt": m.get("alt", ""), "mediaContentType": "IMAGE"}
                 for m in op["media"]]
        return name, {"product": {"id": op["product_id"]}, "media": media}
    if name == "media.reorder":
        return name, {"id": op["product_id"], "moves": op["moves"]}
    if name == "media.update_alt":
        return name, {"files": op["files"]}
    if name == "translations.register":
        return name, {"resourceId": op["resource_id"], "translations": op["translations"]}
    if name in ("collection.create", "discount.create", "article.create"):
        key = {"collection.create": "input", "discount.create": "basicCodeDiscount",
               "article.create": "article"}[name]
        return name, {key: op["input"]}
    raise ValueError(f"unsupported op: {name}")


def apply_op(shop: str, token: str, op: dict[str, Any]) -> dict[str, Any]:
    mutation_key, variables = _variables(op)
    data = graphql(shop, token, _MUTATIONS[mutation_key], variables)
    payload = next(iter(data.values()))
    errors = payload.get("userErrors") or payload.get("mediaUserErrors") or []
    if errors:
        raise ShopifyError({"op": op["op"], "errors": errors})
    return {"op": op["op"], "result": {k: v for k, v in payload.items() if not k.endswith("rrors")}}
