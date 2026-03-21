---
name: consolidate
description: Formalize your code into specs — scan branch changes, group by responsibility, generate governed specs
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
argument-hint: "[path/to/superpowers-spec.md]"
layer: 0
---

# Consolidate

Formalize code on the current branch into governed specs. Scans changed and new files, groups them by responsibility, and generates minimal spec files with ownership populated — turning exploratory code into spec-governed code.

## Procedure

### Step 1: Detect base branch and gather changes

1. Determine the base branch:

   ```bash
   git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||' || echo "main"
   ```

2. Find the merge base:

   ```bash
   git merge-base <base-branch> HEAD
   ```

3. List all changed files on this branch:

   ```bash
   git diff --name-only <merge-base>...HEAD
   ```

4. If no changed files are found, exit early: "No changes to consolidate on this branch."

5. Categorise each changed file:

   | Category | Glob patterns | Needs spec ownership? |
   |----------|--------------|----------------------|
   | Source | `src/**`, `scripts/**`, `.claude/skills/**/SKILL.md`, `.claude/hooks/**`, `tests/**` | Yes |
   | Governance | `docs/specs/**`, `docs/REGISTER.md`, `docs/ARCHITECTURE.md`, `docs/definitions/**`, `contracts.yaml` | No (outputs of this process) |
   | Ephemeral | `docs/plans/**`, `docs/superpowers/**` | No (harvest, don't own) |
   | Config/meta | `CLAUDE.md`, `.gitignore`, `settings.json`, `*.yaml` (non-contracts) | No |

   Files not matching any pattern default to **Source** (need ownership).

6. Present a summary to the user:

   ```
   ## Branch Analysis

   Branch: <branch-name> (vs <base-branch>)
   Changed files: <count>

   ### Source files (need spec ownership): <count>
   - <file list>

   ### Governance files: <count>
   - <file list>

   ### Ephemeral files: <count>
   - <file list>

   ### Config/meta files: <count>
   - <file list>
   ```

### Step 2: Check for superpowers specs

1. If the user provided a path as `$ARGUMENTS`, use that as the superpowers spec. Read it and proceed to Step 3.

2. Otherwise, scan for superpowers **specs** (not plans — `docs/superpowers/plans/` files are implementation plans, not design specs, and are never harvested or deleted):

   ```bash
   ls docs/superpowers/specs/*.md 2>/dev/null
   ```

3. If no superpowers specs exist, note: "No superpowers specs found. Will analyse code changes only (Mode B)." Proceed to Step 3.

4. If superpowers specs exist, present them to the user:

   ```
   ## Superpowers Specs Found

   These design specs may contain content to harvest into governed specs:

   1. `docs/superpowers/specs/<file1>.md` — <first heading from file>
   2. `docs/superpowers/specs/<file2>.md` — <first heading from file>
   ...
   N. None of these — proceed without harvesting

   Which specs are relevant to this branch? (comma-separated numbers, or N for none)
   ```

5. Read the selected superpowers specs in full. Note their content sections for harvesting in Step 5.

### Step 3: Check existing governance state

1. Check if required templates exist:

   ```bash
   ls docs/templates/spec-minimal.md docs/templates/spec-full.md docs/templates/register.md 2>/dev/null
   ```

   If either spec template or the register template is missing, error: "Required template missing: `docs/templates/<name>.md`. Cannot proceed." Stop.

2. Check if `docs/REGISTER.md` exists:
   - If yes: read it. Build a map of file → owning spec from the "Spec Index" table's "Owns (files/directories)" column.
   - If no: note "REGISTER.md not found — will bootstrap from template."

3. Check if `docs/specs/` directory exists:
   - If yes: read existing governed specs to understand current coverage.
   - If no: note "docs/specs/ not found — will create."

4. Cross-reference the **source files** from Step 1 against the register map:
   - **Owned + changed** — file has a spec owner, but the spec may need updating. Read the owning spec.
   - **Unowned** — file has no spec owner (needs assignment to a new or existing spec).

   Note: Even if all files are owned, proceed to Step 4 — the reconciliation plan may still identify spec updates needed or superpowers specs to harvest. The idempotency exit ("Nothing to consolidate") happens naturally in Step 4 when the plan is empty.

### Step 4: Propose reconciliation plan

#### Orient each group (if project-graph.yaml exists)

For each group of related changes, run `/orient` with a brief description of the group's purpose. This helps determine whether the group belongs to an existing spec or needs a new one. Include the orientation results in the reconciliation plan presentation.

Present a structured reconciliation plan to the user. Group source files into proposed governed specs using SPEC-WORKFLOW.md's spec sizing criteria: single reason to change, files that always change together, cohesive responsibility. When in doubt, propose groupings and let the user adjust.

    ## Reconciliation Plan

    ### Bootstrapping required
    <!-- Only show if needed -->
    - [ ] Create `docs/REGISTER.md` from template
    - [ ] Create `docs/specs/` directory

    ### New governed specs to create
    <!-- For each group of unowned files -->
    - `docs/specs/<proposed-name>.spec.md`
      - Would own: `<file1>`, `<file2>`, ...
      - Content source: harvested from `<superpowers-spec>` / code analysis only
      - Status: draft

    ### Governed specs to update
    <!-- For each owned+changed file whose spec needs changes -->
    - `docs/specs/<existing-name>.spec.md` — owns `<changed-file>`
      - Changes needed: [summary of what changed and how the spec should reflect it]
      - Status transition: implemented → revision-needed (if applicable)

    ### Superpowers specs to consume
    <!-- For each selected superpowers spec -->
    - `docs/superpowers/specs/<file>.md` → delete after harvest

    ### Files not requiring spec ownership
    - <config/meta/governance/ephemeral files>

When grouping files, assign test files (`tests/**`) to the same spec as the source files they test.

Ask the user: "Does this plan look right? You can adjust groupings, rename proposed specs, or exclude files."

Wait for user approval before proceeding.

### Step 5: Execute on approval

#### 5a. Bootstrap (if needed)

1. If `docs/specs/` does not exist, create it.
2. If `docs/REGISTER.md` does not exist, read `docs/templates/register.md` and create `docs/REGISTER.md` from it. The tables will be populated as specs are created below.

#### 5b. Create new governed specs

For each new governed spec in the approved plan:

1. Read `docs/templates/spec-full.md` for the template structure (use `spec-minimal.md` for standalone specs without shared definitions or cross-spec dependencies).

2. **If a superpowers spec is being harvested** (transplanting human-authored material, not inventing):
   - **Status:** `draft`
   - **Purpose** ← extract from the superpowers spec's problem statement / purpose section
   - **Behaviour** ← extract from deliverable specs, procedure sections, design notes. This preserves human authorship from the superpowers spec.
   - **Decisions** ← extract design principles and tradeoffs
   - **Tests** ← extract test specifications or acceptance criteria
   - **Requires/Provides** ← derive from the Behaviour section + any referenced definitions

3. **If no superpowers spec** (code-analysis-only mode):
   - **Status:** `draft`
   - **Purpose** ← factual summary derived from reading the source files
   - **Behaviour** ← `<!-- TODO: Human must write Behaviour for this spec -->`. Do NOT generate Behaviour from code — per the collaborative authoring model, Behaviour is human-authored.
   - **Requires/Provides** ← derive from code imports/exports
   - **Tests** ← stub sections

4. Present the drafted spec to the user for review. Wait for approval before writing to disk.

5. Write the spec to `docs/specs/<name>.spec.md`.

#### 5c. Update existing governed specs

For each existing governed spec to update:

1. Read the current spec.
2. If the spec is at `implemented` status, propose transitioning it to `revision-needed` and invoke `/promote-spec <name>` inline to handle the transition. This keeps the governance state consistent within a single flow rather than requiring the user to remember a follow-up step.
3. Identify sections that need updating based on what changed in the code and in any harvested superpowers spec content.
4. Propose specific edits and present to the user.
5. Apply approved edits.

#### 5d. Update REGISTER.md

1. Add entries for each new spec to the "Spec Index" table:
   - Spec name, phase, status (`draft`), owned files/directories, dependencies
2. Update entries for any existing specs whose owned files changed.
3. Check the "Definitions Index" — update if new specs reference definitions.

#### 5e. Update contracts.yaml

1. If `contracts.yaml` exists and new specs reference shared definitions, add version pins.
2. If `contracts.yaml` does not exist or is empty, skip and note: "contracts.yaml not updated — no shared definitions referenced (or file not found)."

#### 5f. Delete consumed superpowers specs

1. For each superpowers spec that was successfully harvested into governed specs:
   ```bash
   rm docs/superpowers/specs/<consumed-file>.md
   ```
2. Note each deletion in the output.

#### 5g. Promote specs to in-progress

For each spec that was created or updated in this consolidation:

1. Ask the user: "These specs are ready for implementation. Promote to `in-progress`?"
   - List each spec with its current status
2. If the user confirms (for all or a subset):
   - Update the `## Status` line in each confirmed spec to `in-progress`
   - Update the status column in `docs/REGISTER.md` for each confirmed spec
3. If the user declines, leave specs at their current status and note: "Specs left at current status. Run `/promote-spec <name>` when ready to implement."

This absorbs the promote step so users don't need to remember a separate `/promote-spec` invocation after consolidation.

### Step 6: Verify

1. Run `/health-check` to verify governance is clean.
2. Present the health check results.
3. Summarise what was done:

       ## Consolidation Complete

       ### Created
       - <new spec files>
       - <REGISTER.md if bootstrapped>

       ### Updated
       - <modified spec files>
       - <REGISTER.md entries>
       - <contracts.yaml if updated>

       ### Deleted
       - <consumed superpowers specs>

       ### Promoted
       - <specs promoted to in-progress, if any>

       ### Health Check
       <pass/fail summary>

## Important Notes

- **Never auto-commit.** All changes to governed documents require user approval before writing to disk. Present drafts and proposed edits, then wait for confirmation.
- **Respect collaborative authoring.** When harvesting from superpowers specs, transplant human-authored content. When no superpowers spec exists, stub Behaviour for the human to write — do not generate it from code.
- **Follow existing patterns.** Use `docs/templates/spec-full.md` as the template for new specs that have shared definitions or cross-spec dependencies, or `docs/templates/spec-minimal.md` for standalone specs. Follow the register table format from `docs/templates/register.md`.
- **Graceful degradation.** If `contracts.yaml` is missing or empty, skip version pin updates. If `ARCHITECTURE.md` is missing, skip — do not create it.
- **Idempotency.** Running this skill twice on the same branch should be safe. If all files are already owned and specs are up-to-date, exit early.

$ARGUMENTS
