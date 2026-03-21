---
name: validate-refs
description: Validate cross-references between specs, definitions, register, and contracts.yaml. Catches broken references, missing files, and notation inconsistencies.
disable-model-invocation: false
allowed-tools: Bash(bash scripts/validate-cross-refs.sh *), Read
argument-hint: [project-dir]
layer: 2
---

# Validate Cross-References

Check that all cross-references between governed documents resolve correctly.

## Procedure

1. Run `bash scripts/validate-cross-refs.sh` against the project root (or `$ARGUMENTS` if a directory is provided)
2. Present results grouped by check type:

   **Check 1 — Spec definition references exist:**
   - Every definition path in a spec's Requires/Provides table should resolve to a file in `docs/definitions/`

   **Check 2 — Register specs exist on disk:**
   - Every spec listed in REGISTER.md should exist as a file in `docs/specs/`

   **Check 3 — contracts.yaml matches spec tables:**
   - Pins in contracts.yaml should match what each spec's Requires/Provides tables say

   **Check 4 — Register dependency notation consistency:**
   - Definition refs should use `.md` extension
   - Spec deps should use `.spec.md` suffix

3. If the script exits with code 0, confirm all cross-references are consistent
4. If issues are found, list each one with a suggested fix

## Important

- This is a read-only check — it does not modify any files
- For fixing contracts.yaml mismatches, suggest `/sync-contracts`
- For missing definitions, suggest `/generate-spec` to create them
