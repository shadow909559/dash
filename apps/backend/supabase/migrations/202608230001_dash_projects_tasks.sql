-- DASH Phase 2: one-way project/task cloud mirror.
-- Apply through the Supabase SQL editor or Supabase CLI with an administrator
-- credential. This migration intentionally creates no auth users and does not
-- grant anonymous access.

create table if not exists public.dash_projects (
  id uuid primary key,
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 255),
  description text,
  status text not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  deleted_at timestamptz,
  unique (id, owner_id)
);

create table if not exists public.dash_tasks (
  id uuid primary key,
  project_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 255),
  description text,
  status text not null,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  deleted_at timestamptz,
  foreign key (project_id, owner_id)
    references public.dash_projects (id, owner_id) on delete cascade
);

create index if not exists dash_projects_owner_updated_idx
  on public.dash_projects (owner_id, updated_at desc);
create index if not exists dash_projects_owner_active_idx
  on public.dash_projects (owner_id, deleted_at) where deleted_at is null;
create index if not exists dash_tasks_owner_project_updated_idx
  on public.dash_tasks (owner_id, project_id, updated_at desc);
create index if not exists dash_tasks_owner_active_idx
  on public.dash_tasks (owner_id, deleted_at) where deleted_at is null;

create or replace function public.dash_set_updated_at()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

drop trigger if exists dash_projects_set_updated_at on public.dash_projects;
create trigger dash_projects_set_updated_at
before update on public.dash_projects
for each row execute function public.dash_set_updated_at();

drop trigger if exists dash_tasks_set_updated_at on public.dash_tasks;
create trigger dash_tasks_set_updated_at
before update on public.dash_tasks
for each row execute function public.dash_set_updated_at();

alter table public.dash_projects enable row level security;
alter table public.dash_tasks enable row level security;

-- Future direct Supabase clients need an authenticated Supabase JWT. Current
-- DASH clients cannot reach these tables because they only possess DASH's
-- device token, not a Supabase Auth session.
create policy "dash_projects_select_owner" on public.dash_projects
for select to authenticated using (owner_id = auth.uid());
create policy "dash_projects_insert_owner" on public.dash_projects
for insert to authenticated with check (owner_id = auth.uid());
create policy "dash_projects_update_owner" on public.dash_projects
for update to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy "dash_projects_delete_owner" on public.dash_projects
for delete to authenticated using (owner_id = auth.uid());

create policy "dash_tasks_select_owner" on public.dash_tasks
for select to authenticated using (owner_id = auth.uid());
create policy "dash_tasks_insert_owner" on public.dash_tasks
for insert to authenticated with check (owner_id = auth.uid());
create policy "dash_tasks_update_owner" on public.dash_tasks
for update to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy "dash_tasks_delete_owner" on public.dash_tasks
for delete to authenticated using (owner_id = auth.uid());
