-- one event cursor per coworker (Core returns events oldest first)
create table if not exists cursors (
  coworker text primary key,
  event_id text
);

-- one journal row per Sokosumi Task the Worker runs; state is written before each side effect
create table if not exists runs (
  task_id text primary key,
  coworker text not null,
  phase text not null,
  state jsonb not null default '{}',
  updated_at timestamptz not null default now()
);

-- CRE results delivered by callback
create table if not exists cre_results (
  request_id text primary key,
  result jsonb not null,
  received_at timestamptz not null default now()
);

-- chat conversations created by Sokosumi Core (Responses API)
create table if not exists conversations (
  id text primary key,
  coworker text not null,
  sokosumi_user_id text not null,
  sokosumi_org_id text not null default '',
  messages jsonb not null default '[]',
  created_at timestamptz not null default now()
);

create table if not exists responses (
  id text primary key,
  body jsonb not null,
  created_at timestamptz not null default now()
);
