#!/bin/bash
# Hook edge cases that a one-line JSON fixture cannot express — each needs a project, a transcript or a timing.
# doctor --self-test runs it; every case is a consumer-reported defect, and each one fails on the code before its fix.
#   N1  an unparseable transcript line killed security-check (exit 5) before the destructive and secret gates ran
#   N2  the same line hid every later call from build-gate → tests that ran read as "not run" (false block)
#   N3  a Windows file_path (C:\…) never matched in build-gate → an Edit-only session was never blocked
#   N5  an invalid package.json logged a fake hook error (ERR trap) on every new-file Write
#   N6  handoff used \s, which BSD sed (macOS) does not know → indented tasks were printed raw
#   E4  the advisory knowledge gate ran before the blocking gates (a block for the wrong reason, or none at all on a timeout)
#   B7  the knowledge gate re-judged every card for every write target — cost grew with targets × cards × tool calls
#   -c  `bash -c "git push --force …"` — the negative side (a feature branch through sh -c still passes)
# Usage: bash hook-edge-cases.sh <plugin root>     Exit: 0 = all pass · 1 = a case failed
R=$(cd "${1:?plugin root}" && pwd)
T=$(mktemp -d 2>/dev/null) || { echo "FAIL cannot create a temp dir"; exit 1; }
trap 'rm -rf "$T"' EXIT
pass=0 fail=0
ok()  { pass=$((pass+1)); echo "ok   $1"; }
nok() { fail=$((fail+1)); echo "FAIL $1 :: $2"; }
KEY="AKI""AIOSFODNN7""EXAMPLE"   # AWS's published example key id, assembled at run time so no file carries it

proj() {   # $1 dir → a git repo with one rule card owning migrations/** and src/**
  mkdir -p "$1/.claude/rules" "$1/migrations" "$1/src" "$1/.st"
  (cd "$1" && git init -q && git -c user.email=t@x -c user.name=t commit -q --allow-empty -m init)
  printf -- '---\npaths:\n  - "migrations/**"\n---\n# data card\n' > "$1/.claude/rules/data.md"
}
# Payload JSON is built with Git Bash's argument path conversion off: /tmp/… handed to jq.exe came back as C:/Users/…/Temp/…
# while CLAUDE_PROJECT_DIR stayed /tmp/…, so no path was inside the project and E4's gate cases passed on windows-latest.
# Only the builders — a jq that READS a file by path needs the conversion (jq.exe cannot open /tmp/…)
jqb() { MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' jq "$@"; }
tu() { jqb -nc --arg n "$1" --argjson i "$2" '{type:"assistant",message:{content:[{type:"tool_use",name:$n,input:$i}]}}'; }
SURR='{"type":"user","message":{"content":[{"type":"tool_result","content":"build ok \ud83d"}]}}'   # lone surrogate: jq 1.7 rejects the line
TRUNC='{"type":"assistant","message":{"content":[{"type":"tool_u'                                 # a last line cut mid-write
sc() {   # $1 project  $2 payload JSON → stdout/stderr in $T/o $T/e, exit code in SC
  SC=0
  printf '%s' "$2" | (cd "$1" && CLAUDE_PLUGIN_ROOT="$R" CLAUDE_PROJECT_DIR="$1" ORANGEKIT_STATE_DIR="$1/.st" \
    bash "$R/scripts/security-check.sh" >"$T/o" 2>"$T/e") || SC=$?
}
bg() {   # $1 project  $2 transcript → build-gate stdout in BG
  BG=$(printf '{"hook_event_name":"Stop","stop_hook_active":false,"cwd":"%s","transcript_path":"%s"}' "$1" "$2" \
    | (cd "$1" && CLAUDE_PLUGIN_ROOT="$R" CLAUDE_PROJECT_DIR="$1" ORANGEKIT_STATE_DIR="$1/.st" bash "$R/scripts/build-gate.sh" 2>/dev/null))
}
write_in() { jqb -nc --arg s "$1" --arg t "$2" --arg f "$3" --arg c "$4" '{session_id:$s,transcript_path:$t,cwd:($f|sub("/[^/]*/[^/]*$";"")),tool_name:"Write",tool_input:{file_path:$f,content:$c}}'; }
bash_in() { jqb -nc --arg s "$1" --arg t "$2" --arg d "$3" --arg c "$4" '{session_id:$s,transcript_path:$t,cwd:$d,tool_name:"Bash",tool_input:{command:$c}}'; }

# ── N1 · security-check with an unparseable transcript line ──────────────
P="$T/n1"; proj "$P"
{ tu Read "{\"file_path\":\"$P/.claude/rules/data.md\"}"; printf '%s\n%s' "$SURR" "$TRUNC"; } > "$T/n1-read.jsonl"
{ tu Bash '{"command":"ls"}'; printf '%s\n%s' "$SURR" "$TRUNC"; } > "$T/n1-none.jsonl"
sc "$P" "$(write_in n1a "$T/n1-read.jsonl" "$P/migrations/0002.sql" 'create table a (id int);')"
[ "$SC" = 0 ] && ! grep -q 'ERROR line' "$T/e" && ok "N1 card read before an unparseable line still counts (exit 0)" \
  || nok "N1 card read before an unparseable line" "exit $SC · $(head -1 "$T/e")"
sc "$P" "$(bash_in n1b "$T/n1-none.jsonl" "$P" 'echo x > migrations/a.sql && psql -c "DROP TABLE users"')"
[ "$SC" = 2 ] && grep -q 'DROP of a table' "$T/e" && ok "N1 DROP TABLE is blocked although the transcript has an unparseable line" \
  || nok "N1 DROP TABLE with an unparseable transcript line" "exit $SC (2 = blocked) · $(head -1 "$T/e")"
sc "$P" "$(write_in n1c "$T/n1-none.jsonl" "$P/migrations/0003.sql" "-- $KEY")"
[ "$SC" = 2 ] && grep -q 'AWS Access Key' "$T/e" && ok "N1 a hardcoded key is blocked although the transcript has an unparseable line" \
  || nok "N1 secret with an unparseable transcript line" "exit $SC (2 = blocked) · $(head -1 "$T/e")"

# ── E4 · blocking gates run before the knowledge gate ────────────────────
P="$T/e4"; proj "$P"; tu Bash '{"command":"ls"}' > "$T/e4.jsonl"
sc "$P" "$(write_in e4a "$T/e4.jsonl" "$P/migrations/0002.sql" "-- $KEY")"
[ "$SC" = 2 ] && grep -q 'AWS Access Key' "$T/e" && ok "E4 a secret is blocked as a secret, not sent back by the knowledge gate" \
  || nok "E4 secret in a file whose card is unread" "exit $SC · reason: $(grep -m1 -E 'Blocked|Load these' "$T/e")"
sc "$P" "$(bash_in e4b "$T/e4.jsonl" "$P" 'echo x > migrations/b.sql && psql -c "DROP TABLE users"')"
[ "$SC" = 2 ] && grep -q 'DROP of a table' "$T/e" && ok "E4 a DROP is blocked as a DROP, not sent back by the knowledge gate" \
  || nok "E4 DROP with an unread card" "exit $SC · reason: $(grep -m1 -E 'Blocked|Load these' "$T/e")"
sc "$P" "$(write_in e4c "$T/e4.jsonl" "$P/migrations/0004.sql" 'create table a (id int);')"
[ "$SC" = 2 ] && grep -q 'Load these first' "$T/e" && ok "E4 the knowledge gate still blocks a clean write once" \
  || nok "E4 knowledge gate after the reorder" "exit $SC · $(head -1 "$T/e")"
P="$T/e4t"; proj "$P"; tu Bash '{"command":"ls"}' > "$T/e4t.jsonl"
SC=0; write_in e4t "$T/e4t.jsonl" "$P/migrations/0002.sql" 'create table a (id int);' \
  | (cd "$P" && ORANGEKIT_KG_BUDGET=0 CLAUDE_PLUGIN_ROOT="$R" CLAUDE_PROJECT_DIR="$P" ORANGEKIT_STATE_DIR="$P/.st" \
     bash "$R/scripts/security-check.sh" >"$T/o" 2>"$T/e") || SC=$?
[ "$SC" = 0 ] && grep -q 'cannot be determined' "$T/o" && jq -e . "$T/o" >/dev/null 2>&1 \
  && ok "E4 a spent time budget falls back to the undecidable notice (one JSON, no block)" \
  || nok "E4 time budget" "exit $SC · stdout: $(head -c 120 "$T/o")"

# ── B7 · cost does not grow with write targets (transcript WITH tool calls) ──
P="$T/b7"; proj "$P"
for c in 1 2 3; do printf -- '---\npaths:\n  - "src/**"\n---\n# card %s\n' $c > "$P/.claude/rules/s$c.md"; printf 'card:s%s.md\n' $c >> "$P/.st/knowledge-gate.b7"; done
i=0; while [ $i -lt 300 ]; do
  tu Bash "{\"command\":\"cd apps/api && npx vitest run src/x$i.test.ts | tail -20\"}"; tu Read "{\"file_path\":\"/repo/apps/api/src/x$i.ts\"}"; i=$((i+1))
done > "$T/b7.jsonl"
ms() { python3 -c 'import time; print(int(time.time()*1000))' 2>/dev/null || echo 0; }
targets() { local n=0 s=""; while [ $n -lt "$1" ]; do s="$s${s:+ && }echo x > src/f$n.ts"; n=$((n+1)); done; printf '%s' "$s"; }
a=$(ms); sc "$P" "$(bash_in b7 "$T/b7.jsonl" "$P" "$(targets 1)")"; c1=$SC; b=$(ms)
sc "$P" "$(bash_in b7 "$T/b7.jsonl" "$P" "$(targets 8)")"; c8=$SC; c=$(ms)
t1=$((b-a)); t8=$((c-b))
# Fixed: 8 targets ≈ 1.1–1.4× one target. Broken: ≈ 7×. The bound is 3× + 1 s so a slow, noisy runner cannot flake it; process
# creation on Windows (Git Bash) is slow and uneven enough that a ratio there measures the machine, not the hook
if [ "$a" = 0 ]; then echo "skip B7 timing — python3 unavailable for a millisecond clock"
elif case "${OSTYPE:-}" in msys*|cygwin*|win*) true ;; *) false ;; esac; then echo "skip B7 timing — not measured on a Windows shell (fork cost dominates; the cache logic is proven on macOS/Linux)"
elif [ "$c1" = 0 ] && [ "$c8" = 0 ] && [ "$t8" -lt $((t1*3 + 1000)) ]; then ok "B7 8 targets cost about one (1 target ${t1} ms · 8 targets ${t8} ms · 600 tool calls · 3 cards)"
else nok "B7 cost grows with write targets" "1 target ${t1} ms (exit $c1) · 8 targets ${t8} ms (exit $c8)"; fi

# ── N5 · invalid package.json is not a hook error ────────────────────────
P="$T/n5"; proj "$P"; printf '{"scripts":{"test":"vitest run"},}\n' > "$P/package.json"; : > "$T/n5.jsonl"
mkdir -p "$P/src/server"
sc "$P" "$(write_in n5 "$T/n5.jsonl" "$P/src/server/points.ts" 'export const p = 1')"
if ! grep -q 'ERROR line' "$T/e" && ! awk -F'|' '$4 != "0"' "$P/.st/hookrun.log" 2>/dev/null | grep -q .; then ok "N5 an invalid package.json logs no hook error"
else nok "N5 invalid package.json" "exit $SC · $(grep -m1 'ERROR' "$T/e") · hookrun: $(awk -F'|' '$4 != "0" {print $1 "|" $4 "|" $5}' "$P/.st/hookrun.log" | head -1)"; fi

# ── N2 · build-gate with an unparseable line between the edit and the tests ──
P="$T/n2"; proj "$P"; echo 'export {}' > "$P/src/a.ts"; (cd "$P" && git add -A && git -c user.email=t@x -c user.name=t commit -qm a)
echo 'export const x = 1' > "$P/src/a.ts"; : > "$P/.st/session-baseline.txt"
{ tu Edit "{\"file_path\":\"$P/src/a.ts\",\"old_string\":\"{}\",\"new_string\":\"x\"}"; printf '%s\n' "$SURR"; tu Bash '{"command":"npx vitest run"}'; } > "$T/n2.jsonl"
bg "$P" "$T/n2.jsonl"
case "$BG" in *'"continue": false'*|*'"continue":false'*) nok "N2 tests run after an unparseable line" "blocked: $(printf '%s' "$BG" | head -c 100)" ;;
  *) ok "N2 tests run after an unparseable transcript line still count (no block)" ;; esac

# ── N3 · build-gate with a Windows-form Edit path ────────────────────────
tu Edit '{"file_path":"C:\\Users\\me\\proj\\src\\a.ts","old_string":"{}","new_string":"x"}' > "$T/n3.jsonl"
bg "$P" "$T/n3.jsonl"
case "$BG" in *'"continue": false'*|*'"continue":false'*) ok "N3 an Edit with a C:\\ path is this session's edit (blocked without tests)" ;;
  *) nok "N3 Windows Edit path" "not blocked — C:\\Users\\me\\proj\\src\\a.ts did not match src/a.ts" ;; esac

# ── N6 · handoff lists an indented open task ─────────────────────────────
P="$T/n6"; proj "$P"; mkdir -p "$P/dev/active/w"; printf -- '- [x] done\n  - [ ] nested open task\n' > "$P/dev/active/w/tasks.md"
HO=$(printf '{"hook_event_name":"PreCompact","cwd":"%s"}' "$P" | (cd "$P" && CLAUDE_PLUGIN_ROOT="$R" CLAUDE_PROJECT_DIR="$P" ORANGEKIT_STATE_DIR="$P/.st" \
     ORANGEKIT_HANDOFF_DIR="$P/.st/handoff" bash "$R/scripts/handoff.sh" 2>/dev/null) | jq -r '.additionalContext // empty' 2>/dev/null)
if printf '%s\n' "$HO" | grep -qx '  - nested open task' && printf '%s\n' "$HO" | grep -q 'progress 1/2'; then ok "N6 an indented task is counted and listed without its checkbox"
else nok "N6 indented task" "$(printf '%s\n' "$HO" | grep -E 'progress|nested' | tr '\n' ' ')"; fi

# ── -c payloads · the negative side (the positive side is in doctor's POS_FX) ──
P="$T/c"; proj "$P"; : > "$T/c.jsonl"
for cmd in 'sh -c "git push origin feature-x"' 'bash -c "git push --force origin my-feature"' 'bash -c "npm test"'; do
  sc "$P" "$(bash_in c "$T/c.jsonl" "$P" "$cmd")"
  [ "$SC" = 0 ] && ok "-c $cmd passes" || nok "-c $cmd" "exit $SC · $(grep -m1 Blocked "$T/e")"
done
sc "$P" "$(bash_in c "$T/c.jsonl" "$P" "bash -c \"sh -c 'git push --force origin main'\"")"
[ "$SC" = 2 ] && grep -q 'force push to a shared branch' "$T/e" && ok "-c a nested sh -c inside bash -c is unwrapped (blocked)" \
  || nok "-c nested payload" "exit $SC"

# ── B10 · build-gate counts a Bash WRITE, not a mention (two directions) ──
# Another session changed b/index.tsx. Reads of it, or a write to a/index.tsx, are not this session's edit; a write to it is.
P="$T/b10"; proj "$P"; mkdir -p "$P/a" "$P/b"; echo 'export {}' > "$P/a/index.tsx"; echo 'export {}' > "$P/b/index.tsx"
(cd "$P" && git add -A && git -c user.email=t@x -c user.name=t commit -qm files)
echo 'export const other = 1' > "$P/b/index.tsx"
b10() {   # $1 want (pass|block)  $2 cwd ("" = none recorded)  $3 command
  : > "$P/.st/session-baseline.txt"
  jq -nc --arg c "$3" --arg d "$2" '{type:"assistant"} + (if $d == "" then {} else {cwd:$d} end) + {message:{content:[{type:"tool_use",name:"Bash",input:{command:$c}}]}}' > "$T/b10.jsonl"
  bg "$P" "$T/b10.jsonl"
  case "$BG" in *'"continue": false'*|*'"continue":false'*) got=block ;; *) got=pass ;; esac
  local lbl; case "$2" in "") lbl="(no cwd)" ;; "$P") lbl="(root)" ;; *) lbl="(${2#"$P"/})" ;; esac
  lbl="$lbl $(printf '%s' "$3" | tr '\n' '~')"
  [ "$got" = "$1" ] && ok "B10 $1 $lbl" || nok "B10 $lbl" "expected $1, got $got"
}
b10 pass  "$P"   'cat b/index.tsx | head -5'
b10 pass  "$P"   'git diff b/index.tsx'
b10 pass  "$P"   'grep -rn useState --include=index.tsx .'
b10 pass  "$P"   'cd a && sed -n 1,20p index.tsx'
b10 pass  "$P/a" 'echo x > index.tsx'
b10 block "$P"   'echo "export const x = 2" > b/index.tsx'
b10 block "$P"   "cd b && sed -i '' s/other/mine/ index.tsx"
b10 block "$P/a" 'cp /tmp/template.tsx ../b/index.tsx'
b10 block "$P"   "$(printf 'cat > /tmp/note.txt <<EOF\nnotes\nEOF\nsed -i.bak s/a/b/ b/index.tsx')"
b10 block ""     'echo x > b/index.tsx'
b10 block "$P"   'npx prettier --write b/index.tsx'

# ── S1 · Windows: the knowledge gate resolves a Bash target against a C:\-style cwd ──
# Simulated: OSTYPE=msys and the cwd sent with backslashes — the hook must still see migrations/x.sql under the project root
P="$T/s1"; proj "$P"; tu Bash '{"command":"ls"}' > "$T/s1.jsonl"
SC=0; bash_in s1 "$T/s1.jsonl" "$(printf '%s' "$P" | tr '/' '\\')" 'echo x > migrations/x.sql' \
  | (cd "$P" && OSTYPE=msys CLAUDE_PLUGIN_ROOT="$R" CLAUDE_PROJECT_DIR="$P" ORANGEKIT_STATE_DIR="$P/.st" \
     bash "$R/scripts/security-check.sh" >"$T/o" 2>"$T/e") || SC=$?
[ "$SC" = 2 ] && grep -q 'Load these first' "$T/e" && ok "S1 a Bash write under a backslash cwd reaches the knowledge gate (Windows)" \
  || nok "S1 backslash cwd" "exit $SC · $(head -1 "$T/e") — the target was resolved outside the project root"

# ── Windows paths · /c/… from Git Bash and C:/… from a native program are one path ──
sl() { OSTYPE="$1" bash -c 'source "$1/scripts/lib/common.sh" >/dev/null 2>&1; orangekit_slashes "$2"' _ "$R" "$2" 2>&1; }
[ "$(sl msys /c/Users/me/proj)" = "C:/Users/me/proj" ] && [ "$(sl msys /tmp/x)" = "/tmp/x" ] && [ "$(sl darwin /c/Users/me)" = "/c/Users/me" ] \
  && ok "slashes: /c/Users/… → C:/Users/… on a Windows shell only (/tmp untouched)" \
  || nok "slashes /c/…" "msys /c/Users/me/proj → '$(sl msys /c/Users/me/proj)' · msys /tmp/x → '$(sl msys /tmp/x)' · darwin /c/Users/me → '$(sl darwin /c/Users/me)'"

# ── gawk (the Windows awk) · no `\/` escape warning from the write-target check ──
if command -v gawk >/dev/null 2>&1; then
  mkdir -p "$T/gawkbin"; ln -s "$(command -v gawk)" "$T/gawkbin/awk"
  P="$T/gk"; proj "$P"; : > "$T/gk.jsonl"
  SC=0; bash_in gk "$T/gk.jsonl" "$P" 'for f in $(cat /tmp/list.txt); do echo x > $f; done' \
    | (cd "$P" && PATH="$T/gawkbin:$PATH" CLAUDE_PLUGIN_ROOT="$R" CLAUDE_PROJECT_DIR="$P" ORANGEKIT_STATE_DIR="$P/.st" \
       bash "$R/scripts/security-check.sh" >"$T/o" 2>"$T/e") || SC=$?
  ! grep -q 'escape sequence' "$T/e" && ok "gawk: no escape-sequence warning on stderr (exit $SC)" \
    || nok "gawk escape warning" "$(grep -m1 'escape sequence' "$T/e")"
else echo "skip gawk escape check — gawk not installed (Windows Git Bash and most Linux CI images have it)"; fi

echo "pass $pass fail $fail"
[ "$fail" -eq 0 ]
