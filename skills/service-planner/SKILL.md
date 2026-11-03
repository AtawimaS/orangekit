---
name: service-planner
description: Designs the service structure, screens, and user flows, and derives concrete functional requirements. Use when it is not settled which screens are needed, what path users take, or what they see in exceptions such as cancellation, refund, and errors, and for "service planning" or requirements-elicitation requests. When requirements are done and only the document remains use /prd-generator; for visual style such as color and fonts use /ui-ux-design.
---

# Service Planner

Designs the service and derives **concrete functional requirements (FR-xxx)**.
It answers "what are we building and how?", aiming for a level of detail a PRD can take over as-is.

<HARD-GATE>
Do not pass the functional requirements table (Step 5) to the PRD before the user approves it — the PRD takes this table as-is, so an error spreads downstream.
Save it after the user confirms.
</HARD-GATE>

## Workflow

Copy this checklist into your reply and tick it off as you go (the Step 1 table decides which Steps are skipped).

```
- [ ] Step 1 Identify the input
- [ ] Step 2 Integrate the business plan
- [ ] Step 3 Personas and scenarios
- [ ] Step 4 IA design
- [ ] Step 5 Derive FR/NFR, user confirmation
- [ ] Step 6 Save and link to the PRD
```

### Step 1: Identify the input and set the scope

| Input situation | Steps to run |
| --------- | --------- |
| Invoked with a business plan from business | Step 2 → Step 3 → Step 4 → Step 5 → Step 6 |
| Invoked directly by the user | Step 3 → Step 4 → Step 5 → Step 6 |
| Request to revise an existing service plan | Step 3 (load the existing one) → Step 5 (revise) → Step 6 |

### Step 2: Integrate the business plan

Read `dev/docs/business/business-plan-<name>.md` and pull out **only what constrains the service design**:

| Business plan item | Constraint it puts on the service design |
| --- | --- |
| Target customer | The starting point for the Step 3 personas (carried over, not invented anew) |
| Value proposition | The test for a Must feature in Step 5 — if it does not contribute to the value proposition, it is not a Must |
| Revenue model | Whether payment, subscription, and permission screens exist at all (Step 4 IA) |
| Key metrics (KPI) | **Why** the Step 5 acceptance criteria have to be measurable |

If there is no business plan, or the item is empty, **do not fill it in by estimating** — mark that item
"undecided" and raise it as an open question in Step 5.

### Step 3: User analysis (User Journey Mapping)

3-1. Define the core personas
3-2. Derive the main user scenarios
3-3. Write the User Stories

### Step 4: Information architecture (IA) design

4-1. Screen hierarchy (site map)
4-2. List of core screens
4-3. Navigation flow between screens
4-4. Screen data needs — for each screen, write a table of **the fields it reads · the fields it writes · whether it is a list ·
     its empty/loading/error branches** (§6 "Screen data needs"). The wire contract (`dev/docs/api/wire-contract.md`) and
     the draft data model are derived from this table — without it the contract gets built with no relation to the screens
4-5. Draft data model — group the fields from 4-4 into entities (logical level; physical types and migrations
     belong to the implementation stage)

### Step 5: Derive the functional requirements — the core artifact

5-1. Decompose User Story → Epic → Feature → Requirement
5-2. Functional requirements table (FR-xxx) — MoSCoW priority + acceptance criteria
5-3. Non-functional requirements table (NFR-xxx)
5-4. User confirmation

### Step 6: Save the service plan and hand off to the PRD

Save path: `dev/docs/service/service-plan-<name>.md`

## Reference documents

`references/service-frameworks.md` is 319 lines. **Read only the section for the current Step.**

| Step | Section to read |
| --- | --- |
| Step 3 | §1 User Story writing guide |
| Step 4 | §6 Information architecture guide |
| Step 5 | §2 MoSCoW · §3 Acceptance Criteria · §4 FR table · §5 NFR checklist |
| Step 6 | §7 Service plan output template |

- Service plans live in `dev/docs/service/` · business plans live in `dev/docs/business/`

## Pitfalls

- Avoid the trap of mapping FRs 1:1 to UI screens — the screen data needs table from 4-4 is an IA artifact (which data a
  screen touches), not an FR (what a user can do). Do not mix the two
- Do not fill NFR numbers in without a basis — a number with no basis is decoration, not a verification criterion
- Do not copy figures (target metrics) from the business plan straight into FR acceptance criteria — a business goal and a feature's pass criterion are measured in different units
