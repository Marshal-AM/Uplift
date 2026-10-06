"""Changeset operations: the only way a deliverable can ask for a store write.

Each op names its owning role. CRE checks ownership before publishing, and the gateway
only executes ops listed here. Prices, inventory, variants, product status and theme
files have no op, so they cannot be changed.
"""

from typing import Any

# product.update fields and the role that owns each one
PRODUCT_FIELD_OWNERS: dict[str, str] = {
    "title": "clara",
    "descriptionHtml": "clara",
    "handle": "clara",
    "seo": "clara",
    "productType": "oskar",
    "vendor": "oskar",
    "category": "oskar",
}

# Ops other than product.update are owned whole by one role
OP_OWNERS: dict[str, str] = {
    "product.tags_add": "clara",  # copy tags; Oskar uses product.taxonomy_tags_add
    "product.taxonomy_tags_add": "oskar",
    "metafields.set": "*",  # owner resolved per metafield key below
    "collection.add_products": "oskar",
    "collection.create": "oskar",
    "media.add": "iris",
    "media.reorder": "iris",
    "media.update_alt": "iris",
    "translations.register": "yuki",
    "discount.create": "marcus",
    "article.create": "leo",
}

METAFIELD_OWNERS: dict[tuple[str, str], str] = {
    ("custom", "faq"): "leo",
    ("custom", "comparison"): "leo",
    ("shopify--discovery--product_recommendation", "related_products"): "oskar",
    ("shopify--discovery--product_recommendation", "complementary_products"): "oskar",
}


def owners_of(op: dict[str, Any]) -> set[str]:
    """Roles that must own an op for it to be publishable."""
    name = op["op"]
    if name == "product.update":
        return {PRODUCT_FIELD_OWNERS[f] for f in op["fields"]}
    if name == "metafields.set":
        owners = set()
        for mf in op["metafields"]:
            key = (mf["namespace"], mf["key"])
            # category metafields (attributes) belong to Oskar
            owners.add(METAFIELD_OWNERS.get(key, "oskar" if mf["namespace"] == "shopify" else "?"))
        return owners
    return {OP_OWNERS.get(name, "?")}


def validate(op: dict[str, Any]) -> None:
    name = op.get("op")
    if name == "product.update":
        unknown = set(op.get("fields", {})) - PRODUCT_FIELD_OWNERS.keys()
        if unknown or not op.get("fields"):
            raise ValueError(f"product.update has unsupported fields: {sorted(unknown)}")
    elif name not in OP_OWNERS:
        raise ValueError(f"unsupported op: {name}")
    if "?" in owners_of(op):
        raise ValueError(f"op {name} touches a field no role owns")
