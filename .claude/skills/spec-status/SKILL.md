---
name: spec-status
description: Show a dashboard of all specification statuses, ownership, and dependencies. Use to understand project state at a glance.
disable-model-invocation: false
allowed-tools: Read, Grep, Glob
context: fork
agent: Explore
layer: 1
---

# Spec Status Dashboard

Generate an on-demand dashboard showing all specs, their statuses, what they own, and what's blocking progress.

## Procedure

1. **Read the register.** Read `docs/REGISTER.md`. Extract the spec index table. If no register exists, fall back to scanning `docs/specs/*.spec.md` directly.

2. **Read each spec.** For every spec found, read the spec file and extract:
   - `## Status` value
   - `## Requires` table entries (definition dependencies with versions)
   - `## Provides` table entries
   - File ownership (from the register's "Owns" column, or from the spec's Implementation Notes)

3. **Check definition health.** For each required definition, check if the definition file exists and whether the pinned version matches the definition's current `## Version` header.

4. **Present the dashboard** as a formatted table:

   ```
   | Spec | Status | Owns | Requires | Blockers |
   |------|--------|------|----------|----------|
   ```

   Where:
   - **Owns** = count of owned files (e.g., "3 files")
   - **Requires** = list of definition dependencies (e.g., "schema@v1")
   - **Blockers** = any issues: stale pins, missing definitions, missing owned files

5. **Highlight actionable items:**
   - Specs in `revision-needed` status (need attention)
   - Specs in `in-progress` status (active work)
   - Specs in `ready` status (can be started)
   - Any stale version pins

6. **Show summary stats:**
   ```
   Total: N specs | Implemented: N | In Progress: N | Ready: N | Draft: N | Revision Needed: N
   ```

7. **Show dependency resolution order** if available in the register (which specs should be implemented first based on their dependencies).

## Output format

Keep the output concise and scannable. Use the table format above. Bold or highlight anything that needs attention. If a project directory is provided as `$ARGUMENTS`, use that instead of the current directory.

$ARGUMENTS
