"""Store links: one encrypted token per (Sokosumi user, organization, platform)."""

from dataclasses import dataclass

from . import crypto, db


@dataclass
class Link:
    id: int
    user_id: str
    org_id: str
    platform: str
    account: str
    status: str
    token: str


def save(user_id: str, org_id: str, platform: str, account: str, token: str, scopes: str) -> None:
    """Connect or reconnect: the new token replaces the old one."""
    ciphertext, data_key = crypto.encrypt(token, user_id, org_id, platform)
    db.execute(
        """
        insert into store_links (sokosumi_user_id, sokosumi_org_id, platform, account,
                                 token_ciphertext, data_key_ciphertext, scopes, status)
        values (%s, %s, %s, %s, %s, %s, %s, 'valid')
        on conflict (sokosumi_user_id, sokosumi_org_id, platform) do update set
          account = excluded.account, token_ciphertext = excluded.token_ciphertext,
          data_key_ciphertext = excluded.data_key_ciphertext, scopes = excluded.scopes,
          status = 'valid', updated_at = now()
        """,
        user_id, org_id, platform, account, ciphertext, data_key, scopes,
    )


def get(user_id: str, org_id: str, platform: str) -> Link | None:
    row = db.fetch_one(
        "select * from store_links where sokosumi_user_id = %s and sokosumi_org_id = %s and platform = %s",
        user_id, org_id, platform,
    )
    if not row:
        return None
    token = crypto.decrypt(
        bytes(row["token_ciphertext"]), bytes(row["data_key_ciphertext"]), user_id, org_id, platform
    )
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
