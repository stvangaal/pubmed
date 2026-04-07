---
name: start
description: Orchestrator for spec-driven development — guides from idea through issue, spec, plan, tests, and code. Detects scale to skip ceremony for trivial changes. Saves progress to .claude/progress/ for cross-session resumption.
disable-model-invocation: false
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
layer: 0
---

# Start

The single entry point for all change requests. Orchestrates the full spec-driven development lifecycle:

```
Idea → Issue → Spec → Plan → Tests → Code → Finish
```

Detects change scale to skip ceremony for small fixes. Saves progress so work can resume across sessions.

## When to invoke

Claude should invoke this skill whenever the user:
- Asks to add a feature, fix a bug, refactor code, or make any change
- References a GitHub issue they want to work on
- Starts a session with an intent to modify the project
- Says "pick up where I left off" or resumes previous work

## Progress files

Progress is persisted to `.claude/progress/<issue-number>.yaml` (or `no-issue.yaml` if no issue exists). This file tracks which phase the work is in and any state needed to resume.

```yaml
# .claude/progress/40.yaml
issue: 40
title: "Test article publishing workflow end-to-end"
branch: feat/e2e-wp-test
scale: standard        # trivial | small | standard
phase: code            # intake | spec | plan | test | code | finish
spec: wp-publish       # governing spec name (null for trivial)
created: "2026-04-05"
updated: "2026-04-05"
notes: |
  3 draft posts created successfully. Need to verify in WP admin.
```

**Read progress on entry.** At the start of every invocation, check for an existing progress file. If found, report the current phase and offer to resume or start fresh.

**Write progress after each phase transition.** Update the file when moving between phases. This is the only file this skill writes automatically — all other writes go through sub-skills or require user approval.

## Procedure

### Phase 0: Intake

#### 0a. Check for existing progress

```bash
ls .claude/progress/*.yaml 2>/dev/null
```

If progress files exist, present them:
> "Found in-progress work:
> - #40: Test article publishing workflow (phase: code, branch: feat/e2e-wp-test)
>
> Resume this, or start something new?"

If resuming, read the progress file and jump to the recorded phase.

#### 0b. Identify the change request

From the user's message, extract:
- **What** they want to change
- **Why** (if stated)
- **Any referenced issue number**

#### 0c. Check for a GitHub issue

If the user referenced an issue number:
```bash
gh issue view <number> --json title,state,body
```

If no issue was referenced, check for a matching open issue:
```bash
gh issue list --state open --limit 20
```

Present what you found:
- If a matching issue exists: "Found issue #N: <title>. Working from this?"
- If no issue exists: "No GitHub issue found. Want me to create one?"

Do not block on issue creation — suggest it but proceed if the user declines.

#### 0d. Orient (if project-graph.yaml exists)

If `project-graph.yaml` exists, run `/orient` with the change description to understand where this fits in the existing project structure.

#### 0e. Check branch state

```bash
git rev-parse --abbrev-ref HEAD
git status --short
```

Report current branch and any uncommitted work. Suggest creating a feature branch if on main.

#### 0f. Detect scale

Assess the likely scope of the change:

| Scale | Criteria | Workflow |
|-------|----------|----------|
| **Trivial** | ≤2 files in a single existing spec, obvious fix (typo, config tweak, one-liner) | Plan → Code (skip spec, skip tests) |
| **Small** | ≤2 files in a single existing spec, requires thought but spec already covers the behaviour | Plan → Test → Code (update existing spec if behaviour changes) |
| **Standard** | New behaviour, new files, crosses spec boundaries, or no spec exists yet | Spec → Plan → Test → Code |

Present your assessment:
> "This looks like a **small** change — it touches `wp_publish.py` which is owned by the `wp-publish` spec. The spec already covers this behaviour.
>
> I'd skip spec creation and go straight to planning. Sound right?"

The user can override. Write the agreed scale to the progress file.

**Create the progress file now** with phase set to the first applicable phase.

### Phase 1: Spec (standard scale only)

For standard-scale changes, a governed spec must exist before implementation.

#### If an existing spec covers this work:
1. Read the spec
2. Determine if the behaviour section needs updating
3. If yes, propose edits and apply on approval
4. If the spec is `implemented`, note it may need `revision-needed` status

#### If no spec exists:
1. Run `/generate-spec` to create a new governed spec interactively
2. The spec starts at `draft` status
3. After creation, offer to promote to `in-progress` (run `/promote-spec`)
4. Update the register

#### If the user wants to explore first (exploratory path):
1. Help create a feature branch
2. Let them explore freely
3. When they signal readiness, run `/consolidate` to formalize
4. Then return to this workflow at the Plan phase

Update progress: `phase: plan`

### Phase 2: Plan

Use Claude's built-in plan mode (EnterPlanMode) to design the implementation approach.

1. Enter plan mode
2. Explore the codebase, understand existing patterns
3. Design the implementation — identify files to modify, functions to reuse, edge cases
4. For **small** and **standard** scale: the plan must include a test strategy (what to test, where test files go)
5. Present the plan for user approval
6. Exit plan mode

The ephemeral plan file lives at `.claude/plans/` per the existing convention.

Update progress: `phase: test`

### Phase 3: Test (small and standard scale)

**Tests are written before code.** This is the test-first discipline.

1. Based on the plan's test strategy, write test files:
   - Unit tests for new behaviour
   - Update existing tests if behaviour changes
   - Contract tests if shared definitions are affected
2. Run the tests — they should **fail** (the code doesn't exist yet or hasn't been changed)
3. Confirm with the user: "Tests written and failing as expected. Ready to implement?"

For trivial changes, skip this phase entirely.

Update progress: `phase: code`

### Phase 4: Code

Write the implementation.

1. Implement the changes described in the plan
2. Follow ownership headers — every new file gets `# owner: <spec-name>` as first comment
3. Run the tests from Phase 3 — they should now **pass**
4. If tests fail, iterate until they pass
5. Run the full test suite for affected areas to catch regressions

After tests pass:
> "Implementation complete. Tests passing. Ready to wrap up?"

Update progress: `phase: finish`

### Phase 5: Finish

Orchestrate the pre-PR steps. This invokes `/finish` which handles:

1. Verify no uncommitted changes
2. Map changed files to specs
3. Run health check
4. Promote specs to `implemented`
5. Run security review (if applicable)
6. Create PR via `/pr`
7. Present the PR URL

After the PR is created:
> "PR created: <url>
>
> After it's merged, run `/cleanup` to switch to main and delete the branch."

**Delete the progress file** — this work item is complete.

```bash
rm .claude/progress/<issue-number>.yaml
```

## Scale override rules

The user can always override the detected scale:
- "This needs a spec" → escalate to standard
- "Just fix it" → de-escalate to trivial
- "Skip tests for this one" → acknowledged but noted in PR description

## Cross-session resumption

When a user starts a new session:

1. Check `.claude/progress/` for active work
2. If found, read the progress file and present the state
3. Offer to resume at the recorded phase
4. Re-read the relevant spec, plan file, and branch state to rebuild context

The progress file is the **minimal bookmark** — it points to the spec, plan, and branch where the real context lives. It doesn't duplicate that content.

## Relationship to other skills

This skill **replaces** the previous `/start` and acts as the conductor. It calls these skills internally:

| Phase | Calls |
|-------|-------|
| Intake | `/orient` (if project-graph.yaml exists) |
| Spec | `/generate-spec`, `/consolidate`, `/promote-spec` |
| Plan | `EnterPlanMode` / `ExitPlanMode` |
| Finish | `/finish` → `/pr` |

Skills that remain standalone (invoked by user directly):
- `/cleanup` — post-merge
- `/reflect` — learning capture
- `/health-check` — on-demand audit
- `/spec-status` — dashboard
- `/design` — when user wants the full brainstorm→consolidate flow before entering /start's standard path

## Important

- **This skill is guidance, not a gate.** If the user wants to skip phases, let them — but note what's being skipped.
- **Save progress after every phase transition.** This is what enables cross-session resumption.
- **Don't duplicate sub-skill logic.** Call `/generate-spec`, `/finish`, etc. — don't reimplement them.
- **Keep output concise.** The user wants to make progress, not read a manual. Report phase, context, and next action — nothing more.
- **Respect the user's scale assessment.** If they say "just fix it," don't insist on a spec. Note the skip and move on.

$ARGUMENTS
