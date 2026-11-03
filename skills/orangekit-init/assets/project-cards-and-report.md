<!-- An asset used only by orangekit-init. Called from Steps 7.5 and 10 of SKILL.md. Needed only after the interview is over. -->

# Step 7.5 · Step 10: project-specific cards · completion report

## Step 7.5: Create project-specific rule cards (project-owned)

Where Step 7's cards are **plugin-owned** (auto-refreshed by a version stamp), this step's two cards
are **project-owned** — they hold this project's real structure and conventions, and the project manages them from then on.

1. Read `${CLAUDE_PLUGIN_ROOT}/templates/rules/project-structure.template.md`
2. **If there is existing code, measure the real tree** (`ls` + the main directories 2–3 levels deep) —
   do not fill it in by guessing. For a new project, fill in the target structure from the preset + the Step 4.7 topology
2.5. **Fill the "dependency direction" section** — if there is existing code, measure the direction
   imports actually flow; if new, write the direction of the preset topology. If there are no layers,
   write "single layer — not applicable". **Do not force one into existence** — write a layer into
   the card that does not exist and `orangekit-reviewer` will report violations that do not exist
3. Substitute or remove every placeholder and guidance comment and save it under `.claude/rules/`
   as `project-structure.md`
4. `${CLAUDE_PLUGIN_ROOT}/templates/rules/code-conventions.template.md` the same way —
   keep **only the one stack block** matching the preset and keep the shared blocks (naming · code
   style · commit conventions). If existing lint settings or CLAUDE.md carry project-specific
   conventions, confirm with the user and fold them in, then save as `code-conventions.md`
5. Check that both cards' `paths:` frontmatter points at the **real source directory** (the Step 4
   input) — if paths are wrong the card is never loaded.
   **Also check the paths the topology requires** — for `monorepo` the shared package path, for
   `msa` the service roots, must actually exist in `paths:`. **If they do not, do not save the card**;
   go back to Step 4.7 and Step 4, settle the paths, and generate again.
   A card that covers only the source directory never once appears over shared code —
   such a card is worse than no card (it makes you believe there is one)

> Do not put an `orangekit-rule-version` stamp in these two cards — that marks them project-owned.
>
> **The protection mechanism is not the stamp but name non-collision.** `install-rules.sh` iterates
> only the plugin's `rules/*.md` (`for f in "$SRC"/*.md`), so as long as `rules/` has no file of the
> same name, they never become candidates. Therefore **do not create `project-structure.md` or
> `code-conventions.md` in the plugin's `rules/`** — the moment you do, the unstamped target is read
> as `0.0.0` and the project's copy is overwritten (a `.bak` remains, but it is a silent loss).

## Step 10: Completion report

```
ORANGEKIT Devkit initial setup complete!

Files created:
  ✅ orangekit.config.json
  ✅ CLAUDE.md
  ✅ .claude/rules/ (N plugin rule cards + project-specific project-structure · code-conventions)
  ✅ dev/ directory structure

Stack rule files (copy the `status:` line from Step 9.5 verbatim):
  ✅ .claude/rules/stack-<axis>-<pack>.md — installed (rules)
  ✅ .claude/rules/stack-<axis>-<stack>.md — generated from the official docs (project-owned)   ← when "rule file only" was chosen in the three-way question
  ·  <axis>                               — no pack (generate) — universal rules only      ← when "create nothing" was chosen, or no item had evidence
  ·  <axis>                               — not chosen (undecided)

Detailed guide skills (opt-in):
  ·  not installed — ask for "generate guides" if needed          ← when "No" was chosen
  ✅/⏳ .claude/skills/<axis>-guide — the `status:` line of the detailed guide path verbatim  ← when "Yes" was chosen (do not report a half as finished)

Verification:
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh"

Next steps:
  1. Review CLAUDE.md and fill in project-specific information
  2. Restart Claude Code and the harness activates
```
