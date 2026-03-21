---
name: check-register
description: Audit file ownership — finds source files not listed in REGISTER.md and specs listed in the register whose files don't exist on disk. Use after adding new files or refactoring.
disable-model-invocation: false
allowed-tools: Bash(bash scripts/health-check.sh *), Read, Glob, Grep
layer: 1
---

# Check Register (File Ownership Audit)

Find source files that no spec owns, and register entries pointing to files that don't exist.

## Procedure

1. Run `bash scripts/health-check.sh` and focus on checks 2 and 3 (register vs. disk, unowned source files)
2. Additionally, perform a broader scan:
   - Glob for source files: `src/**/*.{py,ts,js,tsx,jsx}`, `tests/**/*`, and any other source directories
   - Read `docs/REGISTER.md` and extract all file ownership entries from the spec index table
   - Cross-reference: which source files on disk are NOT covered by any ownership pattern in the register?
3. Present findings in two groups:

   **Missing files (register says they exist, but they don't):**
   - List each missing file and which spec claims to own it
   - Suggest: either create the file or update the register

   **Unowned files (exist on disk, no spec owns them):**
   - List each orphaned file
   - Based on directory location and content, suggest which existing spec should own it
   - If no spec fits, suggest creating a new spec

4. If the register itself doesn't exist, say so and suggest running `/generate-spec` to create the governed documents

## Important

- Do NOT auto-fix — ownership changes require the architecture owner's approval
- Ignore non-source files: docs, configs, scripts, and other non-implementation files are not required to be owned
