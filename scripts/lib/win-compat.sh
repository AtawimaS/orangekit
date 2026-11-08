#!/bin/bash
# scripts/lib/win-compat.sh — Windows shims, sourced by hooks (through common.sh), doctor, the installers and skill scripts.
# Safe for checkers: no `set` options, no traps, no output. On macOS and Linux it defines nothing.
# The orangekit-harness plugin ships without scripts/, so its scripts carry a copy that doctor compares with this file.

# ── Windows (Git Bash · MSYS · Cygwin): resolve Python, strip CRLF
# `python3` is often the Microsoft Store alias — on PATH, but it opens the Store (exit 9009) instead of running — while a
# python.org install answers to `python` or `py -3`. Native jq.exe and python.exe also end every line with CRLF, and the
# trailing \r broke comparisons silently. Only on a Windows shell; macOS and Linux are untouched.
case "${OSTYPE:-}" in
  msys*|cygwin*|win*)
    _ok_py=""
    for _ok_c in python3 python "py -3"; do
      $_ok_c -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1 && { _ok_py=$_ok_c; break; }
    done
    [ -n "$_ok_py" ] && eval "python3() { command $_ok_py \"\$@\" | tr -d '\\r'; return \"\${PIPESTATUS[0]}\"; }"
    command -v jq >/dev/null 2>&1 && jq() { command jq "$@" | tr -d '\r'; return "${PIPESTATUS[0]}"; }
    unset _ok_py _ok_c ;;
esac
