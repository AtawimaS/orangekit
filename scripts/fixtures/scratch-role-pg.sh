#!/bin/bash
# The scratch role on a real PostgreSQL — what no stub can show: SQL from the scratch connection (`\gexec`, a direct
# connection with the scratch URL) fails on the server outside the scratch DBs, the role can still drop what a --template
# copy brought along, and a project user without CREATEROLE (or a role that gained an attribute) falls back with a warning.
# The project user is a non-superuser with CREATEDB CREATEROLE, like a managed database's main user.
# doctor --self-test runs it when initdb/pg_ctl are found and it is not root (initdb refuses root).
# Usage: bash scratch-role-pg.sh <plugin root> <directory holding initdb, pg_ctl and psql>     Exit: 0 = all pass · 1 = a case failed
R=$(cd "${1:?plugin root}" && pwd); PB=${2:?postgres bin dir}; PATH="$PB:$PATH"; T=$(mktemp -d); PORT=$((20000 + RANDOM % 20000)); pass=0; fail=0
ok(){ pass=$((pass+1)); echo "ok   $1"; }; nok(){ fail=$((fail+1)); echo "FAIL $1 :: $2"; }
trap '"$PB/pg_ctl" -D "$T/d" -m immediate stop >/dev/null 2>&1; rm -rf "$T"' EXIT
printf 'su\n' > "$T/pw"; "$PB/initdb" -D "$T/d" -U postgres -A scram-sha-256 --pwfile="$T/pw" >/dev/null 2>&1 || { echo "FAIL initdb"; exit 1; }
"$PB/pg_ctl" -D "$T/d" -o "-p $PORT -k $T -c listen_addresses=127.0.0.1" -l "$T/log" -w start >/dev/null || { echo "FAIL start"; exit 1; }
SU="postgres://postgres:su@127.0.0.1:$PORT/postgres"
psql "$SU" -Xq -v ON_ERROR_STOP=1 >/dev/null <<'SQL'
CREATE ROLE proj LOGIN PASSWORD 'pp' CREATEDB CREATEROLE;
CREATE ROLE weak LOGIN PASSWORD 'ww' CREATEDB;
CREATE DATABASE app OWNER proj;
CREATE DATABASE other OWNER proj;
SQL
P="postgres://proj:pp@127.0.0.1:$PORT/app"
psql "$P" -Xq -v ON_ERROR_STOP=1 >/dev/null <<'SQL'
CREATE TYPE mood AS ENUM ('a','b');
CREATE TABLE users (id serial PRIMARY KEY, n text, m mood);
CREATE TABLE logs (id int GENERATED ALWAYS AS IDENTITY, u int REFERENCES users);
CREATE VIEW v AS SELECT * FROM users;
CREATE FUNCTION f() RETURNS int LANGUAGE sql AS 'select 1';
CREATE TABLE part (id int, k int) PARTITION BY RANGE (k);
CREATE TABLE part1 PARTITION OF part FOR VALUES FROM (0) TO (10);
CREATE COLLATION mycoll (locale = 'C');
INSERT INTO users (n) VALUES ('x');
SQL
mkdir -p "$T/proj"; (cd "$T/proj" && git init -q)
sc(){ CLAUDE_PROJECT_DIR="$T/proj" ORANGEKIT_STATE_DIR="$T/proj/.st" DATABASE_URL="$1" bash "$R/scripts/security-check.sh" --scratch-db "${@:2}"; }
U=$(sc "$P" new rb --template app 2>"$T/e") && ok "new with a template as a non-superuser project user" || nok "new" "$(cat "$T/e")"
case "$U" in *orangekit_sr_*:*@*) ok "the printed URL connects as the scratch role" ;; *) nok "url" "$U" ;; esac
[ "$(stat -c %a "$T/proj/.st/scratch-role" 2>/dev/null || stat -f %Lp "$T/proj/.st/scratch-role")" = 600 ] && ok "role password file is mode 600" || nok "mode" "not 600"
psql "postgres://postgres:su@127.0.0.1:$PORT/orangekit_scratch_rb" -XAtc "select string_agg(distinct pg_get_userbyid(relowner),',') from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public'" > "$T/own"
case "$(cat "$T/own")" in orangekit_sr_*) ok "every copied relation belongs to the role ($(cat "$T/own"))" ;; *) nok "handover" "$(cat "$T/own")" ;; esac
sc "$P" psql rb -q -v ON_ERROR_STOP=1 -c "INSERT INTO part VALUES (1, 1); CREATE INDEX ON part (k); ALTER COLLATION mycoll RENAME TO mycoll2;" 2>"$T/e" \
  && ok "partitioned table, its partition and a collation belong to the role" || nok "partitions" "$(cat "$T/e")"
sc "$P" psql rb -q -v ON_ERROR_STOP=1 -c "BEGIN; DROP VIEW v; DROP TABLE logs; DROP TABLE users; DROP FUNCTION f(); DROP TYPE mood; COMMIT;" 2>"$T/e" && ok "the role drops its copied objects (rollback test works)" || nok "drop in scratch" "$(cat "$T/e")"
printf "select 'drop database other' \\\\gexec\n" | sc "$P" psql rb -q 2>"$T/e"
psql "$SU" -XAtc "select count(*) from pg_database where datname='other'" | grep -qx 1 && ok "\\gexec 'drop database other' fails on the server (other survives)" || nok "gexec drop" "other was dropped"
printf "select 'drop table if exists users' \\\\gexec\nselect 'alter role proj nologin' \\\\gexec\n" | sc "$P" psql rb -q 2>/dev/null
RU=$(sc "$P" url rb 2>/dev/null); RA=$(printf '%s' "$RU" | sed 's#/orangekit_scratch_rb#/app#')
psql "$RA" -XAtc "drop table users" >/dev/null 2>&1
psql "postgres://proj:pp@127.0.0.1:$PORT/app" -XAtc "select count(*) from users" 2>/dev/null | grep -qx 1 && ok "the role connected to app directly cannot drop app's table" || nok "direct" "users gone"
psql "$SU" -XAtc "select rolcanlogin from pg_roles where rolname='proj'" | grep -qx t && ok "the role cannot alter the project user" || nok "alter role" "proj changed"
psql "$RA" -XAtc "drop database app" >/dev/null 2>&1; psql "$SU" -XAtc "select count(*) from pg_database where datname='app'" | grep -qx 1 && ok "the role cannot drop the project DB" || nok "drop app" "gone"
mkdir -p "$T/shim"; printf '#!/bin/sh\necho renamed-host\n' > "$T/shim/uname"; chmod +x "$T/shim/uname"
PATH="$T/shim:$PATH" sc "$P" psql rb -q -c "select 1" >/dev/null 2>"$T/e" && ok "a renamed host still reaches its scratch DB (the role name is read back)" || nok "rename" "$(cat "$T/e")"
sc "$P" new rb2 >/dev/null 2>&1 && sc "$P" psql rb2 -q -c "create table t(i int); drop table t;" 2>/dev/null && ok "a second scratch DB (no template) reuses the role" || nok "rb2" "failed"
sc "$P" drop --all >/dev/null 2>"$T/e" && [ "$(psql "$SU" -XAtc "select count(*) from pg_database where datname like 'orangekit_scratch_%'")" = 0 ] && ok "drop --all as the project user (a member of the role)" || nok "drop" "$(cat "$T/e")"
[ "$(psql "$SU" -XAtc "select count(*) from pg_roles where rolname like 'orangekit_sr_%'")" = 0 ] && [ ! -e "$T/proj/.st/scratch-role" ] && ok "drop --all also drops the role and its password file" || nok "role cleanup" "role or file left"
grep -qx '\*' "$T/proj/.st/.gitignore" 2>/dev/null && ok "the state dir ignores itself (the password is never committed)" || nok "gitignore" "no * in the state dir"
# A DATABASE_URL that cannot be pointed at the scratch DB must stop before anything is created or handed over
sc "host=127.0.0.1 port=$PORT dbname=app user=proj password=pp" new rx --template app >/dev/null 2>"$T/e"; c1=$?
sc "postgres://proj:pp@127.0.0.1:$PORT/postgres?dbname=app" new ry --template app >/dev/null 2>>"$T/e"; c2=$?
sc "postgres://proj:pp@127.0.0.1:$PORT/postgres?%64bname=app" new rz --template app >/dev/null 2>>"$T/e"; c3=$?; [ "$c3" = 2 ] || c2="$c2/encoded:$c3"
[ "$c1:$c2" = "2:2" ] && [ "$(psql "postgres://postgres:su@127.0.0.1:$PORT/app" -XAtc "select pg_get_userbyid(relowner) from pg_class where relname='users'" 2>/dev/null)" = proj ] \
  && ok "a key=value DATABASE_URL or a dbname= in its query is refused; the project table keeps its owner" || nok "conninfo" "exit $c1/$c2 · $(cat "$T/e" | head -2)"
W="postgres://weak:ww@127.0.0.1:$PORT/postgres"; psql "$SU" -Xqc "create database wapp owner weak" >/dev/null
U2=$(sc "postgres://weak:ww@127.0.0.1:$PORT/wapp" new rw 2>"$T/e"); case "$U2:$(cat "$T/e")" in *weak:ww@*Warning:\ no\ scratch\ role*) ok "no CREATEROLE → falls back with a warning" ;; *) nok "fallback" "$U2 $(cat "$T/e")" ;; esac
sc "postgres://weak:ww@127.0.0.1:$PORT/wapp" psql rw -q -c "create table t(i int)" 2>/dev/null && ok "the fallback DB still works" || nok "fallback psql" "failed"
sc "$P" new rb3 >/dev/null 2>&1; psql "$SU" -Xqc "alter role $(awk '{print $1}' "$T/proj/.st/scratch-role") createdb" >/dev/null
sc "$P" new rb4 >/dev/null 2>"$T/e"; grep -q 'Warning: no scratch role' "$T/e" && ok "a role that gained CREATEDB is not used" || nok "elevated" "$(cat "$T/e")"
echo "pass $pass fail $fail"; [ "$fail" = 0 ]
