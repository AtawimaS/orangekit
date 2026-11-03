---
name: execution-dashboard
description: Shows the skills, rules, and hooks referenced in this session as a timeline plus a per-category summary. Use for "execution trace", "execution flow", "what did you reference?", or "which skills did you use?". Manual invocation only.
disable-model-invocation: true
---

# Execution Dashboard

Tracks the Skills/Rules/Hooks/Agents/documents used in the current session and produces a timeline plus a per-category summary report.

## Workflow

Copy this checklist into your response to show progress:

```
- [ ] 0 Read the instrumentation logs
- [ ] 1 Analyze the session (mark each item instrumented/inferred)
- [ ] 2 Timeline
- [ ] 3 Per-category summary
- [ ] 4 Output (summary first, timeline second)
```

### Step 0: Pull in the instrumentation logs (deterministic data)

Read the `.claude/.orangekit/` logs the v3 hooks recorded to get exact execution data:

| Log | Written by | Content |
| --- | --- | --- |
| `.claude/.orangekit/skilluse.log` | track-skill (PostToolUse) | Skill invocations |
| `.claude/.orangekit/hookrun.log` | Every hook (common.sh) | Hook runs · exit codes |
| `.claude/.orangekit/graph.log` | Hooks (orangekit_edge) | Graph edge traversal |

```bash
tail -200 .claude/.orangekit/skilluse.log .claude/.orangekit/hookrun.log .claude/.orangekit/graph.log 2>/dev/null
```

### Step 1: Analyze the session (semantic data)

Read the conversation backwards and extract Skill invocations, Rule references, Hook runs, Agent calls, and document lookups.

**Mark the source on every item** — mixing what came from the logs (`instrumented`) with what was inferred from the conversation (`inferred`)
makes this report unusable as evidence. When the two disagree, the instrumentation wins.

### Step 2: Build the timeline

One line per event, in time order. Items with a log entry take their places first; inferred items are slotted in between.

```
| Time | Kind | Name | Result | Source |
| --- | --- | --- | --- | --- |
| 14:02 | Hook | session-brief | exit 0 | instrumented |
| 14:03 | Skill | codebase-survey | done | instrumented |
| 14:11 | Rule | code-change.md | referenced | inferred |
```

If the time is unknown, leave `--` and keep only the order — **do not invent a time.**

### Step 3: Per-category summary

Fold into five groups: Skill · Rule · Hook · Agent · documents.

```
| Category | Calls | Items (in call order) |
| --- | --- | --- |
| Skill | 2 | codebase-survey · completion-review |
| Hook | 5 | session-brief ×1 · build-gate ×3 · track-skill ×1 |
| Rule | 3 | workflow-routing · code-change · reversibility |
| Agent | 0 | — |
| Documents | 4 | CLAUDE.md · docs/harness-anatomy.md … |
```

Do not drop a category with zero calls; leave it as `0 | —` — **the absence is itself an observation.**

### Step 4: Output

Present the two tables in this order: **summary table first, timeline second.** Then one paragraph
on what stands out (for example: "3 of the 5 hook runs were build-gate — source changed often").

If there are no instrumentation logs and everything is inferred, **say so on the report's first line.**

## Cautions

- If the conversation is long, analyze only the most recent 50 messages (reading more adds tokens without making the timeline more accurate)
- Do not infer information that is in neither the conversation nor the logs — omit it
- If the `.claude/.orangekit/` logs are missing, skip Step 0 and analyze the conversation only (apply the first-line notice from Step 4)
