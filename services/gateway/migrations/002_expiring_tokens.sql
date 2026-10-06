-- Shopify only accepts expiring offline tokens: the ciphertext holds {access_token, refresh_token}; the access
-- token is refreshed (and the refresh token rotated) before it expires.
alter table store_links add column if not exists expires_at timestamptz;
-- links made with the old non-expiring tokens cannot be refreshed; the merchant reconnects once
update store_links set status = 'invalid' where expires_at is null and status = 'valid';
