---
name: orangekit-update
description: Brings everything an older version of this plugin installed into this project up to the installed plugin version in one pass — T1 rule cards, reference assets, stack rule cards and guide skills — reporting old config shapes, retired cards and guides whose stack premise moved instead of guessing. Use for "update orangekit", "orangekit update", "the plugin was updated, bring the project along", or "update the rule cards". For a v2 harness use /orangekit-migrate; for first-time setup /orangekit-init. Manual invocation only.
disable-model-invocation: true
---

# /orangekit-update — bring the project to the installed plugin version

Updating the plugin replaces only the plugin. What an older version **copied into this project** stays behind:
T1 cards in `.claude/rules/`, `.claude/references/`, stack rule cards (`stack-<axis>-<pack>.md`) and guide skills in
`.claude/skills/*-guide/`. The session briefing reports that drift one item at a time; this skill settles it at once.

**The script decides; this skill relays and asks.** Every file verdict (newer stamp · user edit · premise pinned) is made
by the installers init uses, through `scripts/orangekit-update.sh`. Do not re-decide a file in prose.

| | What happens to it |
| --- | --- |
| T1 cards · references · stack rule cards · guide pack files | updated — an older copy the user edited is kept as `.bak`, a same-version edit is preserved |
| `orangekit.config.json` in an old shape · cards the plugin no longer ships · guides whose stack premise moved · a v2 harness | reported, settled below only with the user's yes |
| project cards (`project-structure` · `code-conventions`) · `CLAUDE.md` · generated seams · `dev/` · `.gitignore` | never touched |

## Step 0: Is the plugin itself current?

This skill updates the project **to the plugin version that is installed now**. If the user wants the newest
release first, give them these commands and stop — the new version loads only after a restart:

```bash
grep -m1 '"name"' "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json"   # this plugin's name
claude plugin marketplace update                                       # refresh every marketplace catalog
claude plugin update <name>@<marketplace>                              # the id `claude plugin list` shows for it
```

Then they restart Claude Code and run `/orangekit-update` again.

## Step 1: Check — changes nothing

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/orangekit-update.sh" --plugin-root "${CLAUDE_PLUGIN_ROOT}"
```

| Exit | Meaning | Next |
| --- | --- | --- |
| 0 | up to date | report it and stop |
| 1 | files behind and/or items that need a person | Step 2 |
| 2 | cannot run — not initialized (`/orangekit-init`) or not a plugin root | relay the message and stop |

If the report starts with **a v2 harness is still installed**, stop here and hand over to `/orangekit-migrate` —
nothing else is updated on a v2 project.

## Step 2: Show the plan and ask once

Summarize the check in the user's language: how many files are behind (and which cards), and each item that needs a person.
If `git status --porcelain` is not empty, say so — a clean tree makes the update's diff easy to review.
Then ask with `AskUserQuestion`:

```
Update <n> plugin-installed files to v<version>?
  1. Update        — run it; edited older copies are kept as .bak
  2. Cancel        — change nothing
```

## Step 3: Apply — verified by a fresh check

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/orangekit-update.sh" --plugin-root "${CLAUDE_PLUGIN_ROOT}" --apply
```

The script checks again from scratch after applying. Trust its summary, not the installers' progress lines:
**"every plugin-installed file matches"** is the only success. Anything else — relay it, do not retry blindly.

## Step 4: Items that need a person

Handle only those the report listed, one at a time, each with its own yes.

- **Old config shape** (single-axis preset · no app axis · an unknown preset name) — read the matching table in
  `${CLAUDE_PLUGIN_ROOT}/skills/orangekit-migrate/SKILL.md` ("Two-axis preset migration" · "App axis migration"),
  show the exact before → after of `orangekit.config.json`, ask, edit, then run Step 1 again: the stack step reads
  the presets, so its result can change after the conversion.
- **Cards the plugin no longer ships** — list them. On yes:
  ```bash
  bash "${CLAUDE_SKILL_DIR}/scripts/orangekit-update.sh" --plugin-root "${CLAUDE_PLUGIN_ROOT}" --apply --retire
  ```
  They move to `.claude/deprecated/` with a 14-day expiry in the file name; moving one back restores it.
- **Guide premise moved** — not updated on purpose: the project still runs the older major. Tell the user to move it
  across with `/stack-guide-generator` when the project raises that dependency.

## Step 5: Report

- What changed — `git diff --stat -- .claude` when the project is a git repository.
- The `.bak` files the update left next to replaced copies: review them (a team edit may be inside), then delete.
- Items still open, each with the command or skill that settles it.
