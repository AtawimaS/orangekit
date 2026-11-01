#!/usr/bin/env bash
# proc-shim.sh — wraps Linux procps pkill/pgrep so that **their own ancestor processes are left out of the results**.
#
# Why: Claude Code's Bash tool puts the whole command on the shell's command line. `pkill -f "node server.mjs"` finds the same
# text on that shell's command line too and **kills the shell that was running the command** — the build and restart after it
# never run, exit 143/144. The macOS/BSD versions leave ancestors out by default, so this does not happen there. A hook that guesses
# "will this die?" from the command text never closes, because the forms are an open set (benchmark replay: plain pkill 78 died · 2
# survived, guarded loop 1 died · 2 survived). So instead of guessing, remove the cause — whatever the form, ancestors are not in the results.
#
# Called by: `pkill` and `pgrep` in the plugin's bin/, as `exec bash proc-shim.sh <tool> <shim dir> "$@"`.
# Behaviour: ① not procps → run the original as is ② procps with `--ignore-ancestors` (Debian bookworm 4.0.2, 4.0.3+) → run it with that option
#           ③ otherwise (e.g. Ubuntu 22.04 3.3.17) → find with the original pgrep, drop ancestors (this shell up to init), and handle the output
#             options (-c -n -o -d) and pkill's signal/-e here
# Exit codes match procps: 0 one or more · 1 none · 2 syntax error · 3 fatal error.

tool=$1 shimdir=$2; shift 2

real="" IFS_SAVE=$IFS; IFS=:
for d in $PATH; do
  [ "$d" = "$shimdir" ] && continue
  [ -x "$d/$tool" ] && { real="$d/$tool"; break; }
done
IFS=$IFS_SAVE
[ -n "$real" ] || { printf '%s: command not found\n' "$tool" >&2; exit 127; }

for a in "$@"; do case "$a" in -V|--version|-h|--help) exec "$real" "$@" ;; esac; done
"$real" --version 2>&1 | grep -q procps || exec "$real" "$@"
"$real" --help 2>&1 | grep -q -- '--ignore-ancestors' && exec "$real" --ignore-ancestors "$@"

# ── ③ procps without --ignore-ancestors: filter here ───────────────────
pgrep_bin="$(dirname "$real")/pgrep"
[ -x "$pgrep_bin" ] || exec "$real" "$@"   # no matching pgrep: leave it alone

anc=" $$ " p=$PPID   # this wrapper's own command line carries the same text
while [ -n "$p" ] && [ "$p" -gt 1 ] 2>/dev/null; do
  anc="$anc$p "
  p=$(sed 's/.*) //' "/proc/$p/stat" 2>/dev/null | cut -d' ' -f2)
done

keep=() count=0 newest=0 oldest=0 delim=$'\n' sig=TERM echo=0
first=1
while [ $# -gt 0 ]; do
  a=$1; shift
  if [ "$tool" = pkill ] && [ "$first" = 1 ] && [[ "$a" =~ ^-([0-9]+|(SIG)?[A-Z][A-Z0-9+-]+)$ ]]; then
    sig=${a#-}; first=0; continue
  fi
  first=0
  case "$a" in
    --) keep+=("$a" "$@"); break ;;
    --count) count=1 ;;
    --newest) newest=1 ;;
    --oldest) oldest=1 ;;
    --echo) echo=1 ;;
    --delimiter=*) delim=${a#*=} ;;
    --delimiter) delim=$1; shift ;;
    --signal=*) sig=${a#*=} ;;
    --signal) sig=$1; shift ;;
    --*=*) keep+=("$a") ;;
    --group|--pgroup|--parent|--session|--terminal|--euid|--uid|--pidfile|--ns|--nslist|--runstates|--env)
      keep+=("$a" "$1"); shift ;;
    --*) keep+=("$a") ;;
    -?*)
      i=1
      while [ $i -lt ${#a} ]; do
        c=${a:$i:1}; rest=${a:$((i+1))}
        case "$c" in
          c) count=1 ;;
          n) newest=1 ;;
          o) oldest=1 ;;
          e) [ "$tool" = pkill ] && echo=1 || keep+=("-e") ;;
          d) if [ -n "$rest" ]; then delim=$rest; else delim=$1; shift; fi; break ;;
          [gGPstuUFr]) if [ -n "$rest" ]; then keep+=("-$c" "$rest"); else keep+=("-$c" "$1"); shift; fi; break ;;
          *) keep+=("-$c") ;;
        esac
        i=$((i+1))
      done ;;
    *) keep+=("$a") ;;
  esac
done

tmp=$(mktemp 2>/dev/null) || exec "$real" "${keep[@]}"
trap 'rm -f "$tmp" "$tmp.e"' EXIT
# capture into a file, not $(…) — a command-substitution subshell is a child with this wrapper's command line and the real pgrep would match it
"$pgrep_bin" "${keep[@]}" > "$tmp" 2> "$tmp.e"; rc=$?
if [ "$rc" -ge 2 ]; then cat "$tmp.e" >&2; exit "$rc"; fi

lines=() pids=()
while IFS= read -r l; do
  pid=${l%% *}
  case "$anc" in *" $pid "*) continue ;; esac
  lines+=("$l") pids+=("$pid")
done < "$tmp"

if [ $((newest + oldest)) -gt 0 ] && [ ${#pids[@]} -gt 1 ]; then
  best=0 bt=""
  for k in "${!pids[@]}"; do
    st=$(sed 's/.*) //' "/proc/${pids[$k]}/stat" 2>/dev/null | cut -d' ' -f20)
    [ -n "$st" ] || continue
    if [ -z "$bt" ] || { [ "$newest" = 1 ] && [ "$st" -gt "$bt" ]; } || { [ "$oldest" = 1 ] && [ "$st" -lt "$bt" ]; }; then
      bt=$st best=$k
    fi
  done
  lines=("${lines[$best]}") pids=("${pids[$best]}")
fi

if [ "$tool" = pgrep ]; then
  if [ "$count" = 1 ]; then printf '%s\n' "${#lines[@]}"
  elif [ ${#lines[@]} -gt 0 ]; then
    out=""; for l in "${lines[@]}"; do out="${out:+$out$delim}$l"; done; printf '%s\n' "$out"
  fi
  [ ${#lines[@]} -gt 0 ] && exit 0 || exit 1
fi

killed=0
for pid in "${pids[@]}"; do
  name=$(cat "/proc/$pid/comm" 2>/dev/null)
  if [[ "$sig" =~ ^[0-9]+$ ]]; then kill "-$sig" "$pid" 2>/dev/null; else kill -s "${sig#SIG}" "$pid" 2>/dev/null; fi || continue
  killed=$((killed + 1))
  [ "$echo" = 1 ] && printf '%s killed (pid %s)\n' "$name" "$pid"
done
[ "$count" = 1 ] && printf '%s\n' "$killed"
[ "$killed" -gt 0 ] && exit 0 || exit 1
