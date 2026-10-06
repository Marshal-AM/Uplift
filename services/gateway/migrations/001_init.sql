create table if not exists store_links (
  id bigserial primary key,
  sokosumi_user_id text not null,
  sokosumi_org_id text not null default '',   -- '' = personal workspace
  platform text not null,                     -- 'shopify' | 'google'
  account text not null,                      -- shop domain / google account
  token_ciphertext bytea not null,
  data_key_ciphertext bytea not null,
  scopes text not null,
  status text not null default 'valid',       -- 'valid' | 'invalid'
  updated_at timestamptz not null default now(),
  unique (sokosumi_user_id, sokosumi_org_id, platform)
);

create index if not exists store_links_account on store_links (platform, account);

create table if not exists used_nonces (
  nonce text primary key,
  used_at timestamptz not null default now()
);

create table if not exists applied_changesets (
  change_hash text primary key,
  link_id bigint not null references store_links (id) on delete cascade,
  result jsonb not null,
  applied_at timestamptz not null default now()
);
