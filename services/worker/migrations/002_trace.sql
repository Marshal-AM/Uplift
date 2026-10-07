-- live trace: every step a Task takes and the service it uses (the /live page, e2e/trace.py, trace.md)
create table if not exists trace_events (
  id bigserial primary key,
  at timestamptz not null,
  task_id text not null,
  agent text,
  service text not null,
  step text not null,
  detail text not null default '',
  status text not null default 'ok',
  ms integer,
  span text,
  kind text,
  meta jsonb
);
create index if not exists trace_events_task on trace_events (task_id, id);
create index if not exists trace_events_at on trace_events (at desc);
