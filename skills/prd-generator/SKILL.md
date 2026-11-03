---
name: prd-generator
description: Creates a PRD (product requirements document) for a feature that has none yet in dev/docs/prd/, as a single or modular PRD depending on scale. Use when the feature and screens are settled and a spec document is needed to hand to the dev team, or when the user says "write a PRD". To check an existing PRD use /prd-reviewer; for the implementation plan that follows a PRD use /dev-docs-generator.
---

# PRD Generator

## Handling the input

| Invocation context | Behavior |
|----------|------|
| Called from orangekit-planner with enhanced requirements | Build the PRD on those (skip the Step 2 collection) |
| Called directly by the user via `/prd-generator` | Collect from the user directly in Step 2 |
| Anything else | Collect only what is missing |

## Core workflow

Copy this checklist into your reply and tick it off as you go.

```
- [ ] 1 Search existing PRDs
- [ ] 2 Collect requirements
- [ ] 3 Decide the mode
- [ ] 4 Generate the PRD (S or M)
- [ ] 5 Save
- [ ] 6 User confirmation
```

### Step 1: Search for an existing PRD and decide

Search `dev/docs/prd/` by feature name and keyword. If a related PRD exists, **do not create a new one** —
propose an update and hand off to prd-reviewer.

### Step 2: Collect the requirements

Ask only for what is missing (the same principle as the four entry-condition states — do not re-ask what you already know):

| Item | Example question |
| --- | --- |
| Problem definition | Who is inconvenienced, and by what |
| Goals / non-goals | What is being done this time and what is explicitly not |
| Core features | Can it be compressed to three or fewer Musts |
| Constraints | Technical, schedule, and cost constraints |

### Step 3: Decide the PRD mode

| Condition | Mode | Output |
|------|------|--------|
| Two or more Phases / more than 20 FRs / cross-domain | **Modular** | prd-overload + Phase Sub PRDs + Shared |
| None of the above | **Single** | One PRD file |

### Step 4-S: Generate a single PRD

Follow the form of `assets/prd-template.md` **exactly** (a strict template). **Every run must produce the same structure** —
add a section the template does not have only when the user asks for it.

### Step 4-M: Generate a modular PRD

- `prd-overload.md`: overall summary + the Phase list + dependencies between Phases
- `phases/phase-N-<name>.md`: template §3-§5 repeated per Phase
- `shared/`: shared data model and vocabulary. **One place is the original, the rest reference it** (no duplicated description)

### Step 5: Save the files

- Single: `dev/docs/prd/prd-<feature-name>.md`
- Modular: overload + phases/ + shared/ under `dev/docs/prd/<feature-name>/`

### Step 6: Confirm with the user

Present a generation summary (mode · FR count · Must count · open-question count) and get it confirmed.
If the PRD is edited after confirmation, point the user to prd-reviewer's "verification after edits".

## Using the project context

When generating the PRD, consult `CLAUDE.md`, `dev/docs/`, and `.claude/rules/`. Read the template `assets/prd-template.md` in Step 4.
