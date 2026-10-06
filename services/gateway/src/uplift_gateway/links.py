"""Store links: one encrypted credential per (Sokosumi user, organization, platform).

The credential is {access_token, refresh_token}; `expires_at` is when the access token expires.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from . import crypto, db, shopify

REFRESH_MARGIN = timedelta(minutes=5)


@dataclass
class Link:
    id: int
    user_id: str
    org_id: str
    platform: str
    account: str
    status: str
    token: str


def _seal(grant: dict, user_id: str, org_id: str, platform: str) -> tuple[bytes, bytes, datetime]:
    secret = json.dumps({"access_token": grant["access_token"], "refresh_token": grant["refresh_token"]})
    ciphertext, data_key = crypto.encrypt(secret, user_id, org_id, platform)
    return ciphertext, data_key, datetime.now(UTC) + timedelta(seconds=int(grant["expires_in"]))


def save(user_id: str, org_id: str, platform: str, account: str, grant: dict) -> None:
    """Connect or reconnect: the new credential replaces the old one."""
    ciphertext, data_key, expires_at = _seal(grant, user_id, org_id, platform)
    db.execute(
        """
        insert into store_links (sokosumi_user_id, sokosumi_org_id, platform, account,
                                 token_ciphertext, data_key_ciphertext, scopes, status, expires_at)
        values (%s, %s, %s, %s, %s, %s, %s, 'valid', %s)
        on conflict (sokosumi_user_id, sokosumi_org_id, platform) do update set
          account = excluded.account, token_ciphertext = excluded.token_ciphertext,
          data_key_ciphertext = excluded.data_key_ciphertext, scopes = excluded.scopes,
          expires_at = excluded.expires_at, status = 'valid', updated_at = now()
        """,
        user_id, org_id, platform, account, ciphertext, data_key, grant.get("scope", ""), expires_at,
    )


def _open(row: dict, user_id: str, org_id: str, platform: str) -> dict:
    return json.loads(crypto.decrypt(bytes(row["token_ciphertext"]), bytes(row["data_key_ciphertext"]),
                                     user_id, org_id, platform))


def get(user_id: str, org_id: str, platform: str) -> Link | None:
    """The link with a usable access token, refreshed first if it is about to expire."""
    query = "select * from store_links where sokosumi_user_id = %s and sokosumi_org_id = %s and platform = %s"
    row = db.fetch_one(query, user_id, org_id, platform)
    if not row:
        return None
    if row["status"] == "valid" and (row["expires_at"] is None or row["expires_at"] - REFRESH_MARGIN < datetime.now(UTC)):
        # refresh tokens rotate, so only one caller may refresh: lock the row and re-check
        with db.connection() as conn, conn.transaction():
            row = conn.execute(query + " for update", (user_id, org_id, platform)).fetchone()
            if row["expires_at"] is None or row["expires_at"] - REFRESH_MARGIN < datetime.now(UTC):
                secret = _open(row, user_id, org_id, platform)
                try:
                    grant = shopify.refresh(row["account"], secret.get("refresh_token", ""))
                except shopify.ReauthRequired:
                    conn.execute("update store_links set status = 'invalid', updated_at = now() where id = %s",
                                 (row["id"],))
                    return Link(row["id"], user_id, org_id, platform, row["account"], "invalid", "")
                ciphertext, data_key, expires_at = _seal(grant, user_id, org_id, platform)
                row = conn.execute(
                    "update store_links set token_ciphertext = %s, data_key_ciphertext = %s, expires_at = %s, "
                    "updated_at = now() where id = %s returning *", (ciphertext, data_key, expires_at, row["id"]),
                ).fetchone()
    token = _open(row, user_id, org_id, platform)["access_token"]
    return Link(row["id"], user_id, org_id, platform, row["account"], row["status"], token)


def status(user_id: str, org_id: str, platform: str) -> dict:
    row = db.fetch_one(
        "select account, status from store_links where sokosumi_user_id = %s and sokosumi_org_id = %s "
        "and platform = %s",
        user_id, org_id, platform,
    )
    return {"connected": bool(row) and row["status"] == "valid", "account": row["account"] if row else None}


def invalidate(link_id: int) -> None:
    db.execute("update store_links set status = 'invalid', updated_at = now() where id = %s", link_id)


def delete_account(platform: str, account: str) -> None:
    db.execute("delete from store_links where platform = %s and account = %s", platform, account)
