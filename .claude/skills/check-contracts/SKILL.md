---
name: check-contracts
description: Check version pin staleness — compares contracts.yaml against definition files and spec Requires/Provides tables. Use after editing definitions or specs.
disable-model-invocation: false
allowed-tools: Bash(bash scripts/*), Read, Grep
layer: 2
---

# Check Contracts (Version Pin Staleness)

Focused check on whether contracts.yaml is in sync with definition headers and spec Requires/Provides tables.

## Procedure

1. Run `bash scripts/health-check.sh` and focus on checks 4 and 5 (contracts.yaml sync and definition staleness)
2. Also run `bash scripts/validate-cross-refs.sh` and focus on check 3 (contracts.yaml matches spec tables)
3. Present findings in two groups:

   **Spec ↔ contracts.yaml sync:**
   - For each spec, compare its Requires/Provides pins against contracts.yaml entries
   - Flag any mismatches or missing entries

   **Definition ↔ contracts.yaml staleness:**
   - For each definition referenced in contracts.yaml, compare the pinned version against the definition file's `## Version` header
   - Flag stale pins (pinned version < current version)

4. If stale pins are found:
   - Show which specs need to re-pin and which definitions changed
   - Offer to run `bash scripts/sync-contracts.sh --dry-run` to preview the fix
   - Explain that re-pinning means the spec owner reviewed the definition change and confirmed compatibility

## Important

- Do NOT auto-fix — stale pins require the spec owner to review the definition change
- A stale pin means the definition was updated but the spec hasn't confirmed it works with the new version
