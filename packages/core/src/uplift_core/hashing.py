"""Canonical JSON (RFC 8785) and the hashes Uplift commits to.

`result_hash` matches Kodosumi's `create_result_hash` for a string result, so the
manifest string a flow returns is exactly what lands on-chain as the Job's resultHash.
"""

import hashlib
from typing import Any

import rfc8785


def canonical(value: Any) -> str:
    return rfc8785.dumps(value).decode("utf-8")


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def result_hash(manifest_string: str) -> str:
    return sha256_hex(manifest_string)


def change_hash(changeset: list[dict[str, Any]]) -> str:
    return sha256_hex(canonical(changeset))
