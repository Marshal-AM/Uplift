-- store-search rank of a Task's product at the start and after the end of the run (the /live rank card)
create table if not exists rank_checks (
  task_id text not null,
  stage text not null,  -- start | end
  checked_at timestamptz not null default now(),
  data jsonb not null,
  primary key (task_id, stage)
);
