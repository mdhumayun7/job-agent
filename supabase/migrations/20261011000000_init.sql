-- Job Agent portal: initial schema.
-- Apply in the Supabase SQL editor (or `supabase db push`). Safe to read top to bottom:
-- every table has row level security; users can only see and change their own rows,
-- government records are public only when published, and only staff can edit them.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- profiles
create table public.profiles (
  id           uuid primary key references auth.users (id) on delete cascade,
  role         text not null default 'user' check (role in ('user', 'editor', 'admin')),
  display_name text check (char_length(display_name) <= 80),
  data         jsonb not null default '{}'::jsonb,   -- education, skills, dob, category, state, pwbd, experience
  preferences  jsonb not null default '{}'::jsonb,   -- dashboard sections, preferred categories/states, alert settings
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint profiles_data_size check (pg_column_size(data) < 65536),
  constraint profiles_prefs_size check (pg_column_size(preferences) < 16384)
);

create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id) values (new.id) on conflict do nothing;
  return new;
end $$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

create or replace function public.is_staff() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role in ('editor', 'admin'));
$$;

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role = 'admin');
$$;

create or replace function public.touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end $$;

create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();

alter table public.profiles enable row level security;
create policy "own profile: read"   on public.profiles for select using (id = auth.uid() or public.is_admin());
create policy "own profile: update" on public.profiles for update using (id = auth.uid()) with check (id = auth.uid());
-- Users may edit their profile fields but never their role.
revoke update on public.profiles from authenticated, anon;
grant update (display_name, data, preferences) on public.profiles to authenticated;
grant select on public.profiles to authenticated;

-- Admins change roles through this function only.
create or replace function public.set_user_role(target uuid, new_role text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'only admins can change roles'; end if;
  if new_role not in ('user', 'editor', 'admin') then raise exception 'invalid role'; end if;
  update public.profiles set role = new_role where id = target;
end $$;

-- ---------------------------------------------------------------- government recruitments
create table public.govt_jobs (
  id          text primary key check (id ~ '^[a-z0-9][a-z0-9-]{2,80}$'),
  data        jsonb not null,
  published   boolean not null default false,
  archived    boolean not null default false,
  source_kind text not null default 'manual' check (source_kind in ('manual', 'automated')),
  title       text generated always as (data ->> 'title') stored,
  category    text generated always as (data ->> 'category') stored,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  updated_by  uuid references auth.users (id) on delete set null,
  constraint govt_jobs_has_title check (coalesce(data ->> 'title', '') <> ''),
  constraint govt_jobs_has_source check ((data -> 'source' ->> 'url') ~ '^https?://')
);
create index govt_jobs_published_idx on public.govt_jobs (published, archived);

create or replace function public.govt_jobs_stamp() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  new.updated_at := now();
  new.updated_by := coalesce(auth.uid(), new.updated_by);
  return new;
end $$;
create trigger govt_jobs_stamp before insert or update on public.govt_jobs
  for each row execute function public.govt_jobs_stamp();

alter table public.govt_jobs enable row level security;
create policy "public reads published"  on public.govt_jobs for select using (published and not archived);
create policy "staff read all"          on public.govt_jobs for select using (public.is_staff());
create policy "staff insert"            on public.govt_jobs for insert with check (public.is_staff());
create policy "staff update"            on public.govt_jobs for update using (public.is_staff()) with check (public.is_staff());
create policy "admin delete"            on public.govt_jobs for delete using (public.is_admin());
grant select on public.govt_jobs to anon, authenticated;
grant insert, update, delete on public.govt_jobs to authenticated;

-- ---------------------------------------------------------------- audit history
create table public.audit_log (
  id         bigint generated always as identity primary key,
  table_name text not null,
  row_id     text not null,
  action     text not null,
  actor      uuid,
  at         timestamptz not null default now(),
  old_data   jsonb,
  new_data   jsonb
);

create or replace function public.audit_govt_jobs() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.audit_log (table_name, row_id, action, actor, old_data, new_data)
  values ('govt_jobs', coalesce(new.id, old.id), tg_op, auth.uid(),
          case when tg_op <> 'INSERT' then to_jsonb(old) end,
          case when tg_op <> 'DELETE' then to_jsonb(new) end);
  return coalesce(new, old);
end $$;
create trigger govt_jobs_audit after insert or update or delete on public.govt_jobs
  for each row execute function public.audit_govt_jobs();

alter table public.audit_log enable row level security;
create policy "staff read audit" on public.audit_log for select using (public.is_staff());
grant select on public.audit_log to authenticated;

-- ---------------------------------------------------------------- user lists
create table public.saved_jobs (
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  job_kind   text not null check (job_kind in ('govt', 'company')),
  job_key    text not null check (char_length(job_key) <= 200),
  snapshot   jsonb not null default '{}'::jsonb check (pg_column_size(snapshot) < 4096),
  created_at timestamptz not null default now(),
  primary key (user_id, job_kind, job_key)
);

create table public.recent_views (
  user_id   uuid not null default auth.uid() references auth.users (id) on delete cascade,
  job_kind  text not null check (job_kind in ('govt', 'company')),
  job_key   text not null check (char_length(job_key) <= 200),
  snapshot  jsonb not null default '{}'::jsonb check (pg_column_size(snapshot) < 4096),
  viewed_at timestamptz not null default now(),
  primary key (user_id, job_kind, job_key)
);

create table public.saved_searches (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name       text not null check (char_length(name) between 1 and 80),
  scope      text not null check (scope in ('govt', 'company')),
  query      jsonb not null default '{}'::jsonb check (pg_column_size(query) < 4096),
  notify     boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.notification_state (
  user_id   uuid not null default auth.uid() references auth.users (id) on delete cascade,
  notif_key text not null check (char_length(notif_key) <= 200),
  read_at   timestamptz,
  dismissed boolean not null default false,
  primary key (user_id, notif_key)
);

do $$
declare t text;
begin
  foreach t in array array['saved_jobs', 'recent_views', 'saved_searches', 'notification_state'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('create policy "own rows" on public.%I for all using (user_id = auth.uid()) with check (user_id = auth.uid())', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
  end loop;
end $$;

-- ---------------------------------------------------------------- reports (broken links, wrong info)
create table public.reports (
  id              uuid primary key default gen_random_uuid(),
  job_kind        text not null check (job_kind in ('govt', 'company')),
  job_key         text not null check (char_length(job_key) <= 200),
  reason          text not null check (reason in ('broken_link', 'wrong_information', 'outdated', 'duplicate', 'other')),
  details         text check (char_length(details) <= 2000),
  reporter        uuid default auth.uid() references auth.users (id) on delete set null,
  status          text not null default 'open' check (status in ('open', 'resolved', 'dismissed')),
  resolution_note text check (char_length(resolution_note) <= 2000),
  resolved_by     uuid references auth.users (id) on delete set null,
  resolved_at     timestamptz,
  created_at      timestamptz not null default now()
);
alter table public.reports enable row level security;
-- Anyone signed in can report; the row is always created as 'open' by the reporter themselves.
create policy "signed-in users report" on public.reports for insert to authenticated
  with check (reporter = auth.uid() and status = 'open' and resolved_by is null and resolution_note is null);
create policy "reporter reads own"     on public.reports for select using (reporter = auth.uid() or public.is_staff());
create policy "staff resolve"          on public.reports for update using (public.is_staff()) with check (public.is_staff());
grant select, insert on public.reports to authenticated;
grant update (status, resolution_note, resolved_by, resolved_at) on public.reports to authenticated;

-- ---------------------------------------------------------------- link checks (written by CI with the service role)
create table public.link_checks (
  url        text primary key,
  job_id     text,
  status     integer,
  ok         boolean not null,
  checked_at timestamptz not null default now()
);
alter table public.link_checks enable row level security;
create policy "staff read link checks" on public.link_checks for select using (public.is_staff());
grant select on public.link_checks to authenticated;

-- ---------------------------------------------------------------- email alert log (service role only)
create table public.email_log (
  user_id   uuid not null references auth.users (id) on delete cascade,
  notif_key text not null,
  sent_at   timestamptz not null default now(),
  primary key (user_id, notif_key)
);
alter table public.email_log enable row level security;  -- no policies: only the service role can use it

-- ---------------------------------------------------------------- account deletion
create or replace function public.delete_my_account() returns void
language plpgsql security definer set search_path = public, auth as $$
begin
  if auth.uid() is null then raise exception 'not signed in'; end if;
  delete from auth.users where id = auth.uid();   -- cascades to every user table above
end $$;
revoke execute on function public.delete_my_account() from anon;
grant execute on function public.delete_my_account() to authenticated;
revoke execute on function public.set_user_role(uuid, text) from anon;
grant execute on function public.set_user_role(uuid, text) to authenticated;
