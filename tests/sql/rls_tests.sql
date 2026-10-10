-- Each block raises an exception if a rule is broken.
\set ON_ERROR_STOP 1

insert into auth.users values
  ('00000000-0000-0000-0000-00000000000a', 'admin@example.org'),
  ('00000000-0000-0000-0000-00000000000b', 'alice@example.org'),
  ('00000000-0000-0000-0000-00000000000c', 'bob@example.org');
update public.profiles set role = 'admin' where id = '00000000-0000-0000-0000-00000000000a';

create function pg_temp.as_user(uid text) returns void language plpgsql as $$
begin
  perform set_config('request.jwt.claim.sub', coalesce(uid, ''), false);
end $$;

-- profiles created by trigger
do $$ begin
  if (select count(*) from public.profiles) <> 3 then raise exception 'profile trigger failed'; end if;
end $$;

-- admin creates a draft and a published record
set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-00000000000a');
insert into public.govt_jobs (id, data, published) values
  ('draft-one', '{"title":"Draft","source":{"url":"https://example.gov.in/a"}}', false),
  ('live-one',  '{"title":"Live","source":{"url":"https://example.gov.in/b"}}', true);
reset role;

-- anonymous visitors see only the published record
set role anon;
select pg_temp.as_user(null);
do $$ begin
  if (select count(*) from public.govt_jobs) <> 1 then raise exception 'anon must see only published rows'; end if;
end $$;
reset role;

-- a normal user cannot edit government records or escalate their role
set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-00000000000b');
do $$ begin
  update public.govt_jobs set published = true where id = 'draft-one';
  if (select count(*) from public.govt_jobs where id = 'draft-one') <> 0 then raise exception 'user can see drafts'; end if;
  begin
    insert into public.govt_jobs (id, data) values ('evil-one', '{"title":"x","source":{"url":"https://x.in"}}');
    raise exception 'user inserted a govt job';
  exception when insufficient_privilege then null; end;
  begin
    update public.profiles set role = 'admin' where id = auth.uid();
    raise exception 'user changed own role';
  exception when insufficient_privilege then null; end;
  begin
    perform public.set_user_role(auth.uid(), 'admin');
    raise exception 'user called set_user_role';
  exception when raise_exception then
    if sqlerrm not like 'only admins%' then raise; end if;
  end;
end $$;

-- users own their saved jobs; others cannot read them
insert into public.saved_jobs (job_kind, job_key, snapshot) values ('govt', 'live-one', '{"title":"Live"}');
update public.profiles set data = '{"dob":"2002-01-01"}' where id = auth.uid();
insert into public.reports (job_kind, job_key, reason, details) values ('govt', 'live-one', 'broken_link', 'apply link 404');
do $$ begin
  begin
    insert into public.reports (job_kind, job_key, reason, status) values ('govt', 'live-one', 'other', 'resolved');
    raise exception 'user created a pre-resolved report';
  exception when insufficient_privilege then null; end;
end $$;
reset role;

set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-00000000000c');
do $$ begin
  if (select count(*) from public.saved_jobs) <> 0 then raise exception 'bob can see alice saved jobs'; end if;
  if (select count(*) from public.profiles) <> 1 then raise exception 'bob can see other profiles'; end if;
  if (select count(*) from public.reports) <> 0 then raise exception 'bob can see alice report'; end if;
  if (select count(*) from public.audit_log) <> 0 then raise exception 'bob can read audit log'; end if;
  begin
    insert into public.saved_jobs (user_id, job_kind, job_key) values ('00000000-0000-0000-0000-00000000000b', 'govt', 'x');
    raise exception 'bob wrote into alice list';
  exception when insufficient_privilege then null; end;
end $$;
reset role;

-- admin sees the report, resolves it, sees the audit trail
set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-00000000000a');
do $$ begin
  if (select count(*) from public.reports) <> 1 then raise exception 'admin cannot see reports'; end if;
  update public.reports set status = 'resolved', resolution_note = 'fixed', resolved_by = auth.uid(), resolved_at = now();
  update public.govt_jobs set published = true where id = 'draft-one';
  if (select count(*) from public.audit_log where row_id = 'draft-one') <> 2 then raise exception 'audit log missing entries'; end if;
  if (select updated_by from public.govt_jobs where id = 'draft-one') <> auth.uid() then raise exception 'updated_by not stamped'; end if;
end $$;
reset role;

-- account deletion removes every user row
set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-00000000000b');
select public.delete_my_account();
reset role;
do $$ begin
  if exists (select 1 from public.profiles where id = '00000000-0000-0000-0000-00000000000b') then raise exception 'profile not deleted'; end if;
  if exists (select 1 from public.saved_jobs where user_id = '00000000-0000-0000-0000-00000000000b') then raise exception 'saved jobs not deleted'; end if;
  if (select reporter from public.reports limit 1) is not null then raise exception 'report not anonymised'; end if;
end $$;
