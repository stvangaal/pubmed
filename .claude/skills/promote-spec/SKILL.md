---
name: promote-spec
description: Advance a specification through the status state machine (draft → ready → in-progress → implemented). Runs validation gates at each transition.
disable-model-invocation: true
allowed-tools: Read, Edit, Grep, Glob, Bash(bash scripts/*)
argument-hint: <spec-name>
layer: 0
---

# Promote Spec

Move a specification to its next status, validating gate conditions at each transition.

## Status state machine

```
draft ──→ ready ──→ in-progress ──→ implemented
  ↑                      │                │
  │                      ↓                ↓
  └──────────── revision-needed ←─────────┘
```

## Procedure

### 1. Find the spec

Look up `$ARGUMENTS` in `docs/specs/`. Try these in order:
- Exact path if provided (e.g., `docs/specs/traverser.spec.md`)
- Name match with `.spec.md` suffix (e.g., `traverser` → `docs/specs/traverser.spec.md`)
- Partial match across spec filenames

If the spec can't be found, list available specs and ask the user to pick one.

### 2. Read current status

Read the spec file. Extract the current `## Status` value. Show the user:
- Current status
- Available transitions from this status
- Ask which transition they want (if multiple are possible)

### 3. Validate gate conditions

Run the appropriate gate check based on the transition:

**draft → ready:**
- [ ] `## Behaviour` section exists and is non-empty
- [ ] All definitions in `## Requires` table exist in `docs/definitions/` (at least as draft/v0)
- [ ] No `TODO`, `TBD`, or `FIXME` markers in the Behaviour section (warn if found, don't block)
- [ ] `## Purpose` section is non-empty
- Report: "Gate check: N/N conditions passed"

**ready → in-progress:**
- [ ] Confirm with user: "Are you starting implementation work on this spec?"
- [ ] If `docs/ARCHITECTURE.md` exists, confirm the spec is listed there
- This is a lightweight gate — it's mainly a deliberate status change

**in-progress → implemented:**
- [ ] All files listed in the register's "Owns" column for this spec exist on disk
- [ ] Run `bash scripts/health-check.sh` — no drift for this spec's files and definitions
- [ ] Ask user: "Do all tests pass for this spec?"
- [ ] Ask user: "Has the register been updated with final file ownership?"
- Report: "Gate check: N/N conditions passed"

**any → revision-needed:**
- [ ] Ask user for the revision reason
- [ ] Record the reason as a new entry in the spec's `## Decisions` table with status "revision-needed" and today's date

**revision-needed → draft:**
- [ ] Ask user: "Have the issues been addressed? What changed?"
- [ ] Lightweight gate — resets to draft for re-review

### 4. Apply the transition

If all gate conditions pass (or the user acknowledges warnings):

1. Edit the spec file: update the `## Status` line to the new status
2. If `docs/REGISTER.md` exists, update the status column for this spec in the spec index table
3. Show the user what was changed (file, old status → new status)

### 5. Suggest next steps

Based on the new status:
- **ready:** "This spec is ready for implementation. Run `/promote-spec <name>` again when you start work."
- **in-progress:** "Implementation can begin. The spec-first gate is now satisfied for files owned by this spec."
- **implemented:** "Mark complete. Consider running `/health-check` to verify project consistency."
- **revision-needed:** "This spec needs rework. Update the Behaviour or Decisions section, then promote back to draft."

$ARGUMENTS
