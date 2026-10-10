#!/usr/bin/env bash
# Applies the Supabase migration to a throwaway local PostgreSQL 16 with a
# minimal stand-in for Supabase's auth schema, then checks every RLS rule.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PGBIN=/usr/lib/postgresql/16/bin
DATA=$(mktemp -d)
PORT=55432
chown postgres "$DATA" 2>/dev/null || true
su postgres -c "$PGBIN/initdb -D $DATA -A trust -U postgres >/dev/null"
su postgres -c "$PGBIN/pg_ctl -D $DATA -o '-p $PORT -k /tmp' -l $DATA/log -w start >/dev/null"
trap 'su postgres -c "$PGBIN/pg_ctl -D $DATA -m immediate stop >/dev/null"; rm -rf "$DATA"' EXIT
PSQL="psql -h /tmp -p $PORT -U postgres -d postgres -v ON_ERROR_STOP=1 -q"

$PSQL <<'SQL'
create role anon nologin; create role authenticated nologin; create role service_role nologin bypassrls;
create schema auth;
create table auth.users (id uuid primary key, email text);
create function auth.uid() returns uuid language sql stable as
  $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
grant usage on schema auth to anon, authenticated;
grant usage on schema public to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
SQL
$PSQL -f "$ROOT/supabase/migrations/20261011000000_init.sql"
$PSQL -f "$ROOT/tests/sql/rls_tests.sql"
$PSQL -f "$ROOT/supabase/seed.sql"
$PSQL -c "select count(*) as seeded from public.govt_jobs where published" 
echo "RLS tests passed"
