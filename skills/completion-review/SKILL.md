---
name: completion-review
description: Wraps up the documentation for finished work — updates and checks off context and tasks in dev/active, refreshes the related architecture and API docs, and archives the completed work. Use right after a feature is implemented, or when the user says "I'm done, tidy up the docs". For a PR body to hand to reviewers use /pr-prep; review of shared-contract, API, or migration changes belongs to orangekit-reviewer.
---

# Completion Review

A skill that brings documentation up to date and archives the work once development is done.

Copy this checklist into your response to show progress:

```
- [ ] Step 1 Decide work type and scope
- [ ] Step 2 Dev docs, Step 3 Project docs
- [ ] Step 4.5 Self-check (do not archive if it fails)
- [ ] Step 4 Archive
- [ ] Step 5 Completion report
```

## Workflow

### Step 1: Identify the work type and decide the update scope

| Work type                                | Step 2 (dev docs)              | Step 3 (project docs)                  | Step 4 (archive) |
| ---------------------------------------- | ------------------------------ | -------------------------------------- | ---------------- |
| New feature                              | Update context + tasks in full | Check PRD, CLAUDE.md, all of dev/docs/ | Yes              |
| Extend/modify/delete an existing feature | Update context + tasks         | The dev/docs/ related to what changed  | Yes              |
| Bug fix                                  | tasks only (if dev docs exist) | Minimal update (only if needed)        | May be skipped   |
| Refactoring                              | Update context + tasks         | Focus on the architecture docs         | Yes              |

### Step 2: Update the dev docs

Update the documents in `dev/active/<feature-name>/`.

### Step 3: Update the project docs

Analyze the changes that came up during implementation and update the documents they affect.

### Step 4: Archive

```bash
git mv dev/active/<feature-name> dev/archive/<feature-name>
```

### Step 4.5: Verify the artifact itself

Archiving is awkward to undo (paths change after `git mv`). Check **before** moving anything —
if even one check fails, do not archive and report that item instead:

- [ ] Are there zero unchecked items in `tasks.md`, or does every remaining item carry a reason for exclusion?
- [ ] Was SESSION PROGRESS in `context.md` **appended** to (are the earlier session records still there)?
- [ ] Were the project documents named by the Step 1 table actually updated (or, if no update was needed, is that judgement written down)?
- [ ] If the implementation diverged from the PRD anywhere, was it reported to the user (no automatic fixes)?

```bash
grep -n '^- \[ \]' dev/active/<feature-name>/tasks.md   # unchecked remainder
git diff --stat HEAD -- dev/docs/                        # project docs really were updated
```

### Step 5: Report completion to the user

Four lines. This skill closes out Reversible changes, so a long report is itself a cost.

```
Updated: <N files> (dev docs N · project docs N)
Archived: dev/active/<name> → dev/archive/<name>   (or: skipped — reason)
Remaining: <unchecked items and their exclusion reasons, or "none">
Needs confirmation: <where the implementation diverged from the PRD, or "none">
```

If "Needs confirmation" is not empty, **stop there and let the user choose** —
this skill does not decide whether the implementation or the PRD is right.

## Pitfalls

The Step 4.5 checks are the pitfall list. Add just one: an implementation that differs from the PRD is not fixed automatically, because only the user can decide which side is right.
