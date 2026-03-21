---
name: sync-contracts
description: Regenerate contracts.yaml from spec Requires/Provides tables. Use after editing spec dependencies. Shows a dry-run diff first for approval.
disable-model-invocation: true
allowed-tools: Bash(bash scripts/sync-contracts.sh *), Read
layer: 2
---

# Sync Contracts

Regenerate contracts.yaml by parsing all spec Requires/Provides tables. Always previews before writing.

## Procedure

1. Read the current `contracts.yaml` to show the user what exists now
2. Run `bash scripts/sync-contracts.sh --dry-run` to generate the proposed new version
3. Present a clear comparison:
   - What pins were added (new spec dependencies)
   - What pins were removed (specs no longer reference these definitions)
   - What pins changed version (spec re-pinned to a different version)
   - What stayed the same
4. Ask the user to confirm before applying
5. If confirmed, run `bash scripts/sync-contracts.sh` (without --dry-run) to write the file
6. Show the final result

## Important

- ALWAYS show the dry-run first — never write directly
- The sync script derives pins from spec files, so if a spec's Requires table is wrong, the output will be wrong too
- After syncing, suggest running `/check-contracts` to verify everything is consistent
- This does NOT update definition version headers or spec Requires tables — it only regenerates contracts.yaml to match what specs currently say

$ARGUMENTS
