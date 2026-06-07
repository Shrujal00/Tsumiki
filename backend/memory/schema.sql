-- Tsumiki relational schema (Supabase / Postgres)
-- ---------------------------------------------------------------------------
-- Paste this into the Supabase SQL editor. The application does NOT auto-migrate.
-- Conventions: UUID primary keys, foreign keys cascade from users(id),
-- created_at timestamptz default now().
-- ---------------------------------------------------------------------------

create extension if not exists "pgcrypto";  -- provides gen_random_uuid()

-- Users ---------------------------------------------------------------------
create table if not exists users (
    id                uuid        primary key default gen_random_uuid(),
    display_name      text,
    streak            integer     not null default 0,
    escalation_level  integer     not null default 0,  -- 0 none, 1 notification, 2 voice call
    last_checkin_at   timestamptz,
    created_at        timestamptz not null default now()
);

-- Goals ---------------------------------------------------------------------
create table if not exists goals (
    id           uuid        primary key default gen_random_uuid(),
    user_id      uuid        not null references users(id) on delete cascade,
    title        text        not null,
    domain       text,
    target_date  date,
    is_active    boolean     not null default true,
    created_at   timestamptz not null default now()
);

-- Milestones ----------------------------------------------------------------
create table if not exists milestones (
    id           uuid        primary key default gen_random_uuid(),
    goal_id      uuid        not null references goals(id) on delete cascade,
    description  text        not null,
    target_date  date,
    completed    boolean     not null default false,
    created_at   timestamptz not null default now()
);

-- Check-ins -----------------------------------------------------------------
create table if not exists checkins (
    id          uuid        primary key default gen_random_uuid(),
    user_id     uuid        not null references users(id) on delete cascade,
    action_id   text,                                   -- references a PlannedAction (plans not persisted in Task 1)
    completed   boolean     not null default false,
    note        text,
    "timestamp" timestamptz not null default now(),
    created_at  timestamptz not null default now()
);

-- World states --------------------------------------------------------------
create table if not exists world_states (
    id             uuid        primary key default gen_random_uuid(),
    user_id        uuid        not null references users(id) on delete cascade,
    balance_level  integer     not null default 0,
    stones         jsonb       not null default '[]'::jsonb,  -- [{variant, created_at, from_user_id}]
    created_at     timestamptz not null default now()
);

-- Reflection notes ----------------------------------------------------------
create table if not exists reflection_notes (
    id          uuid        primary key default gen_random_uuid(),
    user_id     uuid        not null references users(id) on delete cascade,
    note        text        not null,
    domain      text,                                   -- goal-domain tag for retrieval
    created_at  timestamptz not null default now()
);

-- Indexes -------------------------------------------------------------------
create index if not exists idx_goals_user        on goals(user_id);
create index if not exists idx_milestones_goal    on milestones(goal_id);
create index if not exists idx_checkins_user_time on checkins(user_id, "timestamp" desc);
create index if not exists idx_world_states_user  on world_states(user_id);
create index if not exists idx_reflection_user    on reflection_notes(user_id);
