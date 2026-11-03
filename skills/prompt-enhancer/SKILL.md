---
name: prompt-enhancer
description: Turns a briefly stated development request into an implementable instruction by enriching it with the project's code structure, dependencies, conventions, and existing patterns. Use when what to build is already settled but the project context is missing — one- or two-line feature requests like "just add this" — and when handing a design approved by /brainstorming over to implementation. If what to build is still undecided, use /brainstorming first.
---

# Prompt Enhancer

Turns a user's brief development request into an **enhanced prompt** that carries the project context. The depth of enhancement depends on how many of the four entry conditions (intent · context · impact radius · verification path) are unmet.

## Core Workflow

### Step 1: Analyze the project context

**Measure, do not guess** — concluding the framework, package manager, or test runner from convention
makes the enhanced prompt carry a false premise into the next Phase.

```bash
cat orangekit.config.json 2>/dev/null                     # if the stack is already declared, stop here
ls package.json pyproject.toml go.mod Cargo.toml 2>/dev/null
git log --oneline -10 ; git diff --stat HEAD~5 2>/dev/null   # where the recent work was
```

Collection ceiling: **5 files · 5 commands.** Do not sweep directories unrelated to the request —
this skill's artifact is one prompt, not a survey report.

What to look at for each request type is set by `references/enhancement-patterns.md`
(UI component · API endpoint · state management · bug fix, and so on). Read only that section.

### Step 2: Work out the intent and which conditions are unmet

**Choosing the enhancement type:**

| Situation | Enhancement type | Step 3 behavior |
|------|----------|------------|
| Via the planning pipeline (a service-plan exists) | tech-spec | Step 3: technical spec mapping |
| Ordinary request — at most one condition unmet | Light | Step 3: light enhancement |
| Ordinary request — two or more conditions unmet | Deep | Step 3: deep enhancement |

### Step 3: Enhance at the chosen depth

#### Technical spec mapping (tech-spec)

Maps service-planner's functional requirements (FR-xxx) onto the project's code context.

#### Light enhancement (at most one condition unmet)

Enhances it into a clear request statement that carries the project context.

#### Deep enhancement (two or more conditions unmet)

Enhances it with project context + implementation scope + detailed requirements and success criteria.

### Step 4: Confirm with the user

Do not implement until the user confirms — this skill's goal is a clear request to hand to the next Phase, not an implementation, and implementing before confirmation locks in a wrong premise.

## Reference documents

| File | When to read it |
| --- | --- |
| `references/enhancement-patterns.md` | **In Step 1 only.** Once the request type is settled, read only that type's section |
| `references/framework-guides.md` | In Step 1, only when the stack is Next.js/React. **If the project has `frontend-guide` or `backend-guide` skills, those win** (they are generated for the actual stack, so they are more accurate) |

## Tips

- If a similar screen or component already exists, reference it as "with an approach similar to the existing X"
- If it is unclear how many conditions are unmet, enhance at the deep level
