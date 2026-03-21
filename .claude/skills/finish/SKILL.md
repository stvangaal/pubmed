---
name: finish
description: Complete implementation work — verify, promote spec to implemented, and create a pull request. Use when implementation is done and you're ready to ship.
disable-model-invocation: true
allowed-tools: Bash, Read, Edit, Grep, Glob
layer: 0
---

# Finish

Guides the transition from "code is done" to "PR is created." Orchestrates verification, spec promotion, and PR creation in the right order.

## When to use

- Implementation is complete
- User says "I think we're done", "create a PR", "let's wrap up"
- After the implement → commit loop is finished

## Procedure

### Step 1: Verify implementation state

Check the current state:

```bash
git status --short
git log $(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||' || echo main)..HEAD --oneline
```

Report:
- **Uncommitted changes:** If any, warn: "You have uncommitted changes. Commit them first?"
- **Commits on branch:** List them so the user can confirm the work is complete
- **Current branch:** Confirm it's a feature branch

If there are uncommitted changes, wait for the user to resolve them before proceeding.

### Step 2: Identify affected specs

If `docs/REGISTER.md` exists:

1. Get all changed files on this branch:
   ```bash
   BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||' || echo main)
   git diff $BASE...HEAD --name-only
   ```

2. Read the register and map changed files to owning specs
3. Read each owning spec and check its status

Present:
```
## Specs affected by this branch

| Spec | Current Status | Action needed |
|------|---------------|---------------|
| <name> | in-progress | Promote to implemented |
| <name> | draft | Still in draft — promote? |
```

If any specs are still `draft` or `ready`, flag this — they should be `in-progress` or `implemented` before creating a PR.

### Step 3: Run health check

If `scripts/health-check.sh` exists:

```bash
bash scripts/health-check.sh "$(git rev-parse --show-toplevel)" 2>&1
```

Present results. If issues are found:
> "Health check found issues. Fix these before creating the PR? Or proceed anyway?"

### Step 4: Promote specs

For each spec that should be promoted to `implemented`:

1. Run the promotion gate checks from `/promote-spec`:
   - All owned files exist on disk
   - No health check drift for this spec's files
   - Ask: "Do all tests pass for this spec?"
   - Ask: "Has the register been updated with final file ownership?"

2. If gates pass, update the spec status to `implemented` and update the register.

3. If any gates fail, report which ones and ask the user how to proceed.

Skip this step if there are no specs to promote (e.g., documentation-only changes).

### Step 5: Security review (if applicable)

Check if any changed files are agent-facing:
- `.claude/hooks/**`, `.claude/skills/**`, `.githooks/**`, `scripts/**`
- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`

If any match:
> "This branch modifies agent-facing code. Run `/security-review` before creating the PR? (Recommended but not required)"

If the user agrees, run the security review. If they decline, proceed.

### Step 6: Create PR

Invoke the `/pr` skill to create the pull request. It handles:
- Health check summary
- Spec context
- Pushing the branch
- Creating the PR via `gh pr create`

Present the PR URL when done.

### Step 7: Suggest next steps

After the PR is created:
> "PR created: <url>
>
> After it's approved and merged, run `/cleanup` to switch to main, pull, and delete this branch."

## Important

- This skill orchestrates existing skills (`/promote-spec` logic, `/security-review`, `/pr`). It doesn't duplicate their internals — it calls them in the right order.
- Steps are sequential and each depends on the previous one. Don't skip ahead.
- If the user wants to create a PR without promoting specs or running health checks, let them — this is guidance, not a gate. But note what was skipped.
- For documentation-only branches (no source code changes), skip spec promotion and security review — go straight to health check and PR.

$ARGUMENTS
