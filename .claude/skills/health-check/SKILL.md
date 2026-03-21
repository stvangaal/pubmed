---
name: health-check
description: Run a full project health check — detects drift between register, contracts, definitions, and specs. Use when starting work, before committing, or when something feels off.
disable-model-invocation: false
allowed-tools: Bash(bash scripts/health-check.sh *), Read
argument-hint: [project-dir]
layer: 0
---

# Project Health Check

Run the project health check to detect drift across the spec-driven workflow.

## Procedure

1. Run `bash scripts/health-check.sh` against the project root (or `$ARGUMENTS` if a directory is provided)
2. Present the results clearly, grouping by check type:
   - Check 1: Governed documents exist
   - Check 2: Register owned files vs. disk
   - Check 3: Unowned source files
   - Check 4: contracts.yaml vs. spec Requires tables
   - Check 5: contracts.yaml vs. definition versions (staleness)
   - Check 6: Spec status consistency
3. If the script exits with code 0 (healthy), confirm the project is in good shape
4. If the script exits with code 1 (drift detected), summarize the issues found and suggest specific fixes

## Important

- Do NOT auto-fix any issues — the architecture owner approves changes
- If version pins are stale, suggest running `/sync-contracts` to preview the fix
- If unowned files are found, suggest which spec should own them based on directory location
- If the health-check script is not found, check that `scripts/health-check.sh` exists and is executable
