# Skill authoring baseline — official best practices

Source: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices (checked 2026-11-03).
This is **the floor every skill must meet.** P1–P6 in `superiority-patterns.md` sit on top of it, so
injecting P patterns into a skill that has not cleared the baseline only adds bloat. What a machine can rule on
belongs to `scripts/skill-lint.sh`; this document covers **only what needs model judgement.**

## Contents

- B1. description — invocation accuracy is decided here
- B2. name
- B3. Body — do not write what Claude already knows
- B4. Degrees of freedom — match the fragility of the task
- B5. Progressive disclosure
- B6. Workflow — checklists and feedback loops
- B7. Content discipline
- B8. When bundling scripts
- B9. Evaluation — build it before the instructions
- Who rules on what

## B1. description — invocation accuracy is decided here

Only `name` and `description` are resident. The model picks from over a hundred candidates on this one line.
However good the body is, if the description is wrong the skill is never called, or called at the wrong time.

**Format** — third person · what it does + when to use it · 1024 characters or fewer · no XML tags · one line.

```
<What it does: verb + deliverable>. Use when <what the user actually types / the situation>. [<Boundary: for X use Y>]
```

Five criteria:

1. **Trigger vocabulary is the user's words.** Users do not type internal terms like `T0`, `Phase 3`,
   "harness-grade" or "P1 boundary". Internal terms contribute nothing to matching and only pay resident cost.
   Contracts that other skills or cards invoke ("Phase 3", "triggered by the doc-dependency card") belong in the body or the routing card.
2. **Cover indirect phrasing.** Users do not say the skill's name — "I'm not sure this will make money before I add
   payments" is more common than "do business planning". Write a few direct keywords together with the **situation**
   (what is undecided, what has just finished).
3. **Write in one language and keep the user's own terms verbatim.** Words the user is likely to type (PR, TDD, PRD,
   SEO, brainstorm) stay in their original form. Do not mix languages within one skill bundle.
4. **Write a boundary only when there is a real competitor.** Add "for X use Y" only when a built-in
   (`/code-review`, `/security-review`, `/simplify`, `/init`, `skill-creator`) or a neighboring skill contends for the same utterance. Put the boundary
   in **both descriptions** — if only one side has it, the side without it keeps intercepting.
5. **Length is not accuracy.** Do not say the same thing twice. A keyword list does not replace a description of the situation.

```yaml
# Good — what + when (direct words, situation) + boundary
description: Prepares a change to be raised as a PR/MR — collects the diff, runs verification, writes the body. Use when the user says "prepare a PR", "open a PR", "write the MR description", or is about to hand a branch to review. For finding bugs in code use /code-review.
# Bad — only what, no when, internal terms
description: Generates harness-grade PR artifacts conforming to the T0 norms.
```

## B2. name

Lowercase letters, digits and hyphens, 64 characters or fewer, no `anthropic` or `claude`, matching the directory name (machine-ruled).
The official recommendation is the gerund form (`processing-pdfs`), but **an already-shipped skill is not renamed** — consumers'
slash commands, routing cards and graph are tied to the name, so a rename is Costly. Only new skills follow the
existing pattern in the bundle (noun phrases: `pr-prep`, `prd-generator`). Do not use vague names like `helper`, `utils` or `tools`.

## B3. Body — do not write what Claude already knows

Once the body is loaded, every token competes with the conversation history. Ask of each paragraph: **would Claude get it wrong without this explanation?**

- Cut: explanations of general concepts (what a PR is, what OWASP is), motivational preambles, the same rule stated twice
- Keep: what is true only in this project or harness, what the model got wrong when measured, exact commands, paths and formats
- Limits: body 500 lines (official) · 300 lines as this repository's target. Over that, subtract first, then split into reference files

## B4. Degrees of freedom — match the fragility of the task

| Task | Freedom | How to write it |
| --- | --- | --- |
| Several approaches are valid and context decides (review, planning, analysis) | High | Judgement criteria and heuristics in prose |
| A preferred pattern exists and variation is allowed (document generation) | Medium | Template or pseudocode + "adjust if needed" |
| Fragile and order matters (install, migration, verification) | Low | Exact commands + "do not change the command or add flags" |

Even within one skill it varies by step. Prose at a step that needs low freedom makes results differ from run to run,
and a fixed procedure at a step that suits high freedom ignores context.

## B5. Progressive disclosure

- SKILL.md acts as a table of contents. Push detail down into reference files and link them **one level deep from SKILL.md**
  (if a reference file calls another reference file, Claude reads only part of it — machine-ruled)
- A reference file over 100 lines gets a `## Contents` at the top (machine-ruled)
- File names say what is in them: `perspective-prompts.md` yes · `doc2.md` no
- With two or more reference files, give **when to read each** as a table (the P6 timing table)
- For scripts, say **whether to run or read them**: "run `x.sh`" / "see `x.py` for the algorithm"

## B6. Workflow — checklists and feedback loops

- For a procedure of three or more steps where skipping breaks the result, give a **copyable checklist**
  ("copy the checklist below into your reply and tick it off as you go")
- For a deliverable where quality matters, put in a **verify → fix → re-verify** loop and write the pass condition and the ceiling (P3) together
- If there are branches, put a decision point at the top: "creating new → section A / fixing → section B"
- Split batch or destructive work into **plan file → validate → execute** (validate the intermediate artifact by machine)

## B7. Content discipline

- **No time-sensitive statements** — "before August 2025, use the old API". If the old way is needed, isolate it in a collapsed `<details>` section.
  Measured history ("broke on 2026-08-23") may stay as the **basis** for a rule, but do not condition an instruction on a date
- **Fix one term** — do not mix "deliverable / output / result" for the same thing
- **Make examples concrete** — if the form matters, give 2–3 input → output pairs
- **State the template's strictness** — "this structure exactly" or "a reasonable default, adjust as needed"
- **Options are one default plus one exception** — not "you can use A, B, or C" but "use A; for a scanned document, B"

## B8. When bundling scripts

- The script handles errors instead of deferring them to Claude — print what, why, and how to fix at the moment of failure
- Justify constants (not `TIMEOUT=47` but a comment on why that value)
- Name the required packages and CLIs in the body and decide behavior when they are absent (three states: if it cannot be judged, do not block)
- Use only `/` in paths. Plugin scripts are called with `${CLAUDE_SKILL_DIR}`
- Write MCP tools by their fully qualified name with the server prefix (`ServerName:tool_name`)

## B9. Evaluation — build it before the instructions

- Run a representative task without the skill and find **where it actually goes wrong** first. Fill only that spot with instructions
- At least three scenarios. For triggers, include should-trigger cases together with **near-misses that should go to a neighboring skill**
- Check with every model you use — instructions that are enough for Opus may fall short for Haiku
- Have a fresh instance do a real task and observe **which files it reads and what it skips**. A bundled file that is never read is cut, or its pointer is fixed
- Measurement tools: single-skill trigger and deliverable A/B is `skill-creator`. Misrouting between neighbors across the whole skill bundle is
  the authoring repository's routing eval (`routing-eval.sh` in `harness-evaluation`)

## Who rules on what

| Item | Machine (`skill-lint.sh`) | Model (this document) |
| --- | --- | --- |
| name format, reserved words, directory match | yes | — |
| description length, XML, one line | yes | — |
| description has a "when" clause, first/second person | warning | whether the trigger vocabulary is the user's words · indirect phrasing · boundary |
| body 500/300 lines | yes | what to cut |
| reference TOC, two-level references, backslash paths | yes | file names · timing table |
| degrees of freedom, checklists, feedback loops, terminology, time-sensitivity | — | yes |
