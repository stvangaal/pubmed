---
name: generate-register
description: Auto-generate REGISTER.md from spec frontmatter. Shows diff before writing.
disable-model-invocation: false
allowed-tools: Bash, Read, Glob, Grep
---

# Generate Register

Auto-generate `docs/REGISTER.md` by reading YAML frontmatter from all `docs/specs/*.spec.md` files. Extracts name, status, owner, and owns patterns, resolves globs to actual files, and produces a complete register.

## Procedure

1. Run the generator in dry-run mode to preview changes:

   ```bash
   bash scripts/generate-register.sh --dry-run
   ```

2. If `docs/REGISTER.md` already exists, show the diff between the current register and the generated output:

   ```bash
   diff <(cat docs/REGISTER.md) <(bash scripts/generate-register.sh --dry-run) || true
   ```

   Present the diff to the user.

3. If no spec files exist in `docs/specs/`, inform the user: "No spec files found. Nothing to generate."

4. **Ask the user for confirmation before writing.** Present the diff (or the full generated content if REGISTER.md doesn't exist yet) and wait for approval.

5. On approval, run the generator to write the file:

   ```bash
   bash scripts/generate-register.sh
   ```

6. Confirm the update: show how many specs were processed and that the file was written.

## Important

- Always show the diff or preview before overwriting.
- The generator preserves "## Unowned Code" and "## Dependency Resolution Order" sections from the existing REGISTER.md.
- If the existing register has manual edits outside those preserved sections (e.g., Definitions Index entries), warn the user that they will be overwritten.
