---
name: brainstorming
description: Narrows an idea whose shape is still undecided into an approved design through questions and approach comparison. Use when the user wants to add a feature but cannot pick how, wants options laid out and compared, says "let's think this through", "I'm not sure how to build this", or asks to brainstorm. If what to build is settled and a short request only lacks project context, use /prompt-enhancer; for screen and user-flow design use /service-planner. Not for bug fixes or config changes.
---

# Brainstorming Ideas Into Designs

Turn an idea into an approved design through dialogue. Understand the project context first, and ask one question at a time.

<HARD-GATE>
Do not write code or take any implementation action until you have presented a design and the user has approved it — implementing before approval means choosing an irreversible direction on the user's behalf.
</HARD-GATE>

Copy this checklist into your response to show progress.

```
- [ ] 1. Explore project context (files, docs, recent commits) + record the original request
- [ ] 2. Diagnose ambiguity -> ask one question at a time
- [ ] 3. Propose 2-3 approaches (trade-offs + recommendation)
- [ ] 4. Present the design section by section, approval after each
- [ ] 5. Before/After comparison table -> hand off to the next Phase
```

## The Process

**Understanding the idea** — Look at the current project state first. Record the user's first request verbatim (for the Before/After comparison). Ask one question per message; if a topic is big, break it into several questions. The goal is to understand purpose, constraints, and success criteria.

**Diagnosing ambiguity** — Before asking anything, sort the ambiguity in the request into the six categories below and ask about the ones that apply first.

| Category | Example ambiguity | Example hypothesis options |
|---------|-----------|-------------|
| Scope | Unclear who "users" are | All users / admins only / a specific role |
| Behavior | Failure behavior undefined | Fail silently / show an error / retry automatically |
| Interface | Transport undefined | REST API / GraphQL / WebSocket |
| Data | Data format undefined | JSON / CSV / both |
| Constraints | Performance requirement undefined | <100ms / <1s / no particular requirement |
| Priority | Importance unclear | Must-have (MVP) / nice-to-have (v1.1) / future (v2) |

**Hypotheses as options** — Open questions force the user to invent the choices, which is a heavy cognitive load. Offer concrete options with a one-line trade-off each.
- Bad: "What authentication method do you want?"
- Good: "Pick an authentication method: (A) OAuth social login — fastest to implement / (B) Email+Password — full control / (C) Magic Link — no passwords"

**Exploring approaches** — Propose 2-3 approaches with trade-offs. Lead with your recommended option and explain why.

**Presenting the design** — Once you believe you understand it, present the design. Scale each section to its complexity (a few sentences if straightforward, 200-300 words if nuanced) and ask after each section whether it looks right. Cover architecture, components, data flow, error handling, and testing. Cut unnecessary features from the design (YAGNI). If an earlier section turns out not to be understood, go back and clarify.

## Before/After Summary

Once the design is done and before handoff, produce a **before/after clarification table** and show it to the user. Put the original request (the one you recorded) next to the confirmed design, item by item.

| Item | Before (original request) | After (confirmed) |
|---|---|---|
| Audience | "users" | Logged-in paying customers only |

## After the Design

After the design is approved, move to the next Phase depending on the invocation context.

| Invocation context | Hand off to |
|----------|----------|
| Inside the planning pipeline (via orangekit-planner) | Return a **structured summary** to orangekit-planner -> proceed to research |
| Standalone call — two or more entry conditions unmet | Prompt enhancement -> PRD generation -> dev docs generation |
| Standalone call — at most one entry condition unmet | Prompt enhancement -> implementation |
| Standalone call — extending an existing feature | Hand off to dev docs generation |

On a standalone call (`/brainstorming`), ask the user whether to save the output once the design is approved.
