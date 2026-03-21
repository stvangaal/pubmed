# Arboretum — Architecture

## Architecture Owner

The project maintainer (currently @stvangaal). Final authority over shared definitions, cross-spec conflicts, skill/hook design, and layered enforcement decisions.

## Overview

Arboretum is a spec-driven development framework for AI code agents. It provides governance infrastructure — hooks, skills, document templates, and `CLAUDE.md` guidance — so that every line of code in a project traces back to a human-authored specification.

**Users:** Solo developers working with Claude Code (the primary AI agent). The framework is designed for one person playing all roles: architecture owner, spec author, reviewer.

**External dependencies:** Claude Code's hook system (SessionStart, PreToolUse, PostToolUse events), GitHub (issues, PRs, Actions), and Bash (all automation is shell-based, no runtime dependencies).

**Two-repo model:** `arboretum-dev` (this repo) is the development repository containing specs, plans, dev-only skills, and tests. `arboretum` is the public distribution. Code flows one-way via GitHub Actions (`sync-public.yml`) on push to main.

## Component Model

Arboretum has three component types that work together to enforce the spec-driven workflow:

### Hooks (Automatic Enforcement)

Shell scripts in `.claude/hooks/` that fire on Claude Code events. They provide guardrails regardless of which skills are active or what the user is doing. All hooks degrade gracefully when governed documents don't exist yet.

| Hook | File | Trigger | What it does | Blocking? |
|---|---|---|---|---|
| **SessionStart** | `session-start.sh` | Session init | Scans register, contracts, specs. Produces project state summary: missing docs, spec statuses, stale pins, layer-appropriate skills. | No |
| **Pre-implementation** | `pre-implementation-check.sh` | Edit/Write to `src/` or `tests/` | Looks up file ownership in register, checks spec's definition pins against current versions, warns if unowned. Layer 1+ only. | No |
| **Pre-commit branch** | `pre-commit-branch-check.sh` | `git commit` command | Blocks commits to protected branches (main/master). Layer 2+ only. | Yes |
| **Post-commit** | `post-commit-check.sh` | After `git commit` | Categorizes committed files, flags unowned implementation files, definition changes without contract updates, spec changes without register updates. Layer 2+ only. | No |

### Skills (On-demand Operations)

Markdown-based skill definitions in `.claude/skills/<name>/SKILL.md`. Each skill is a prompt that Claude executes when invoked. Skills are categorized by function and by whether they are arboretum-owned (governance) or external (development process).

**Governance skills** (arboretum-owned — enforce the spec-driven workflow):

| Skill | Type | What it does |
|---|---|---|
| `/health-check` | Read | Full 8-check drift report: register vs. disk, unowned files, imports vs. requires, contracts vs. specs, contracts vs. definitions, spec status consistency, plan test sections, graph freshness |
| `/check-contracts` | Read | Version pin staleness check (`contracts.yaml` vs. definition files) |
| `/check-register` | Read | File ownership audit (unowned files, missing owned files) |
| `/validate-refs` | Read | Cross-reference consistency between specs, definitions, register |
| `/spec-status` | Read | Dashboard of all specs with statuses, dependencies, blockers |
| `/sync-contracts` | Write | Regenerate `contracts.yaml` from spec frontmatter (dry-run first) |
| `/promote-spec` | Write | Advance spec through status state machine (`draft` → `ready` → `in-progress` → `implemented`) |
| `/generate-spec` | Write | Interactive generator for specs, definitions, architecture, reference docs from templates |
| `/generate-register` | Write | Auto-generate `REGISTER.md` from spec frontmatter `owns:` fields |
| `/consolidate` | Write | Formalize code changes into governed specs (bridge from code-first to spec-first) |
| `/init-project` | Write | Bootstrap a new spec-driven project with templates, hooks, skills, and `CLAUDE.md` |
| `/pr` | Write | Create spec-aware pull request: runs health check, identifies affected specs, pushes branch, creates PR with governance summary |
| `/security-review` | Write | Prompt injection analysis for agent-facing code (hooks, skills, `CLAUDE.md`) |

**Wrapper pattern:** Arboretum wraps external tools at transition points rather than replacing them. `/pr` wraps `gh pr create` by adding a health-check summary and spec awareness. `/consolidate` wraps the design-to-governance transition by converting superpowers design specs into governed specs. This keeps the underlying tools accessible while adding governance at the seams.

**Workflow wrapper skills** (orchestrate transitions between stages):

| Skill | Type | What it does |
|---|---|---|
| `/start` | Read | Entry point: detect change request, ensure issue exists, route to planned/exploratory path |
| `/design` | Write | Brainstorm → consolidate flow: run external design thinking, then wrap output into governed specs |
| `/finish` | Write | Verify → promote spec → PR flow: health check, security review (if needed), then create PR |
| `/cleanup` | Read | Post-merge: switch to main, pull, delete feature branch, verify spec status |

### CLAUDE.md (Guidance and Orchestration)

The `CLAUDE.md` file at the project root provides persistent context to Claude Code. It is read at the start of every session and serves as the orchestration layer between hooks and skills:

- **Spec-first gate:** Instructs Claude not to modify source files unless implementing a spec with status `in-progress`. This is guidance-level enforcement (Layer 0), not hook enforcement.
- **Skill routing:** Documents available skills and when to use them, enabling Claude to suggest appropriate skills based on user intent.
- **Workflow rules:** Git conventions (branch naming, explicit staging, commit messages), draft-mode behaviour, revision protocol.
- **Project context:** Package structure, key documents, design decisions — the orientation material Claude needs to make good decisions.

`CLAUDE.md` is the only component that works at every layer. Hooks can be disabled; skills can be uninvoked; but `CLAUDE.md` is always present in Claude's context.

## Layered Enforcement Model

Arboretum uses a three-layer model so projects can adopt governance incrementally. Each layer adds automation on top of the previous one. The current layer is configured in `.arboretum.yml` (`layer: 0`, `1`, or `2`).

### Layer 0 — Starter (Manual enforcement via CLAUDE.md)

**What's active:** `CLAUDE.md` guidance, document templates, `SPEC-WORKFLOW.md`, all skills (skills declare their own layer, but all are available at Layer 0).

**What's enforced:** The spec-first gate is enforced by `CLAUDE.md` instruction, not by hooks. The SessionStart hook runs but only checks for missing documents and reports spec statuses. No hooks block any operations.

**What it gives you:** A document hierarchy and a workflow. Claude knows the rules and follows them because `CLAUDE.md` says to. The human is the enforcement mechanism.

**When to use:** New projects, small projects, or projects where the overhead of automated checks isn't worth it yet.

### Layer 1 — Structure (Automated file ownership + register generation)

**What's added:** The pre-implementation hook (`pre-implementation-check.sh`) activates. On every Edit/Write to implementation files (`src/`, `tests/`), it looks up file ownership in the register and reports the owning spec's status and definition pin freshness.

**What it gives you:** Real-time ownership awareness. When Claude edits a file, it immediately sees which spec owns it and whether that spec's dependencies are current. The `/generate-register` skill becomes especially useful here — it auto-generates the register from spec frontmatter.

**Upgrade signal:** The SessionStart hook suggests Layer 1 when it detects 3+ specs in `docs/specs/`.

### Layer 2 — Governance (Branch protection + post-commit validation)

**What's added:** The pre-commit branch check (`pre-commit-branch-check.sh`) blocks commits to `main`/`master`. The post-commit check (`post-commit-check.sh`) fires after every commit, flagging unowned files, definition changes without contract updates, and spec changes without register updates.

**What it gives you:** Automated enforcement of the git workflow. Commits to protected branches are blocked (not just discouraged). Post-commit drift detection catches governance gaps immediately after each commit.

**Upgrade signal:** The SessionStart hook suggests Layer 2 when it detects CI workflows or multiple git authors.

### Layer Interaction

All layers are additive. A Layer 2 project has everything from Layers 0 and 1 plus its own hooks. Skills are available at all layers but declare their own layer in frontmatter, which the SessionStart hook uses to show layer-appropriate skill suggestions.

The key design choice: `CLAUDE.md` guidance (Layer 0) is the foundation that everything else builds on. Hooks at Layers 1 and 2 are defense-in-depth, not replacements for the guidance. If all hooks were disabled, `CLAUDE.md` would still instruct Claude to follow the workflow.

## Data Model

Arboretum manages five governed document types plus ephemeral plans. The relationships form a directed graph:

```
Architecture (the map)
    ├── identifies boundaries → Shared Definitions (the contracts)
    └── names components → Specifications (the blueprints)

Shared Definitions ←→ Specifications (version-pinned requires/provides)

Specifications → Source Code (owns files, defines tests)

Register (the index) → indexes Specs, Definitions, and Code

contracts.yaml (version pins) → machine-readable pins from Spec tables, compared against Definition headers
```

**Key entities:**

- **Spec** — Owns source files, declares requires/provides, progresses through status state machine (`draft` → `ready` → `in-progress` → `implemented`, with `revision-needed` as backward path)
- **Shared Definition** — Versioned data contract (v0 while draft, v1+ when stable; every bump is breaking)
- **Register entry** — Maps spec to phase, status, owned files, and dependencies
- **Version pin** — A spec's declared dependency on a specific definition version, tracked in three places (spec tables, `contracts.yaml`, definition headers)

## 4-Level Architecture Model

Arboretum projects use a 4-level hierarchy with single ownership at every level:

| Level | Artifact | Ownership declaration |
|-------|---------|----------------------|
| System | `ARCHITECTURE.md` | — (top of chain) |
| Spec Group | `docs/groups/<name>.md` | `owner: architecture` in frontmatter |
| Spec | `docs/specs/<name>.spec.md` | `owner: <group-name>` in frontmatter |
| Code | Source files | `# owner: <spec-name>` in first comment line |

The `owner:` label is used consistently at every level, always lowercase. A single `grep "owner:"` finds every ownership declaration in the project.

Architecture archetypes define how the Spec Group layer is organized. The `/architect` skill interviews users to match their project to an archetype and scaffold the appropriate structure. Currently two archetypes exist: pipeline (temporal grouping by data transformation stages) and library (functional grouping by capability area).

## Data Flows

### Issue-to-PR Flow

The primary workflow moves changes from GitHub issue to merged pull request:

```
GitHub Issue → Spec (create/update) → Feature Branch → Implement → Commit → PR → Merge
```

Two paths exist:
- **Planned:** Issue → brainstorm (design spec in `docs/superpowers/specs/`) → `/consolidate` (governed spec in `docs/specs/`) → implement
- **Exploratory:** Issue → branch → spike/experiment → `/consolidate` → implement properly

Both paths converge: a governed spec must exist and be `in-progress` before production code is written.

### Spec Implementation Flow

When Claude implements a spec, context is derived automatically:

1. Read `docs/ARCHITECTURE.md` (always)
2. Read the spec being implemented
3. From the spec's Requires table, resolve each dependency to its definition or provider spec
4. Via `docs/REGISTER.md`, find owned files of required specs
5. Read any files referenced in Implementation Notes

### Three-way Version Sync

Definition versions are tracked in three places that must stay in sync:

```
Definition file (## Version header)  ← canonical source
         ↕
Spec tables (Requires/Provides)      ← human-readable
         ↕
contracts.yaml                        ← machine-readable, used by contract tests
```

When a definition version bumps, all three must be updated. Contract tests detect staleness by comparing `contracts.yaml` pins against definition file headers. The `/check-contracts` and `/sync-contracts` skills automate detection and repair.

### Design-to-Governance Flow

Design specs in `docs/superpowers/specs/` are informal, exploratory documents. The `/consolidate` skill converts them into governed specs in `docs/specs/` with correct frontmatter, status tracking, and register integration. This is a one-way promotion — governed specs are the source of truth once they exist.

## Integration Points

### Claude Code Hook System

Arboretum depends on Claude Code's event system for automatic enforcement. Hooks are configured in `.claude/settings.json` and fire on:
- `SessionStart` (startup matcher)
- `PreToolUse` (Edit|Write matcher for implementation checks; Bash matcher for commit checks)
- `PostToolUse` (Bash matcher for post-commit checks)

Hooks receive tool input as JSON on stdin and can output `additionalContext` (non-blocking) or exit code 2 (blocking).

### GitHub

- **Issues:** Entry point for all work. Referenced in commit messages and PR descriptions.
- **Pull requests:** Created via `/pr` skill, which wraps `gh pr create` with governance metadata.
- **Actions:** `sync-public.yml` workflow syncs `arboretum-dev` → `arboretum` on push to main.

### File System

All governance state lives in the file system — no database, no external service. The register, specs, definitions, and `contracts.yaml` are plain text files that git tracks. This means governance state is versioned, diffable, and branchable.

## Cross-Cutting Concerns

### Graceful Degradation

Every piece of automation handles missing documents without failing. The SessionStart hook reports missing docs rather than crashing. The pre-implementation hook exits silently if no register exists. Skills check for document existence before operating. This is critical because:
- New projects start with no governed documents
- The document creation order is strict (architecture → definitions → specs → register → contracts.yaml)
- Each document depends on its predecessors existing

### Layer-Aware Activation

Hooks check `.arboretum.yml` for the current layer and skip themselves if below their activation layer. Skills declare their layer in frontmatter. The SessionStart hook advertises which skills are active at the current layer. This prevents overwhelming new projects with automation they haven't opted into.

### Two-Repo Distribution

The `arboretum-dev` → `arboretum` sync excludes:
- Skills prefixed with `dev-` (project-internal)
- `docs/specs/`, `docs/plans/`, `docs/superpowers/`, `docs/reviews/` (dev-only)
- Files listed in `.graduateignore`

Public-facing file pairs: `CLAUDE.public.md` → `CLAUDE.md`, `README.public.md` → `README.md` in the public repo.

## Phase Map

| Phase | Specs | Goal |
|-------|-------|------|
| Phase 0 (current) | `consolidate-spec.spec.md`, `git-workflow-tooling.spec.md` | Bootstrap governance infrastructure and validate with sample project |

## Dependency Graph

Both current specs are independent (no cross-spec dependencies):

```
Phase 0:
  1. git-workflow-tooling.spec (no dependencies)
  2. consolidate-spec.spec (no dependencies)
```

As the project matures and more specs are added, this graph will show the implementation order derived from requires/provides declarations.

## Project Graph

The project maintains a persistent, derived graph (`project-graph.yaml`) that captures relationships between all project entities. Unlike REGISTER.md (file ownership) and contracts.yaml (version pins), which each track one type of relationship, the project graph aggregates all relationship types into a single queryable artifact.

**The graph is derived, not authoritative.** REGISTER.md, contracts.yaml, and spec/skill frontmatter remain the sources of truth. The graph is regenerated from them by `scripts/generate-graph.sh` and validated for staleness by the health check.

### Nodes

Specs, skills, scripts, hooks, governed documents, and shared definitions.

### Edges

| Relationship | Meaning | Source |
|---|---|---|
| `owns` | Spec owns a file | REGISTER.md |
| `requires` / `provides` | Spec dependency | Spec tables, contracts.yaml |
| `calls` / `suggests` | Skill invokes another skill | Skill body text |
| `runs` | Skill executes a script | Skill body text |
| `belongs-to-stage` | Skill belongs to workflow stage | Generator stage map |

### Usage

The `/orient` skill queries the graph to provide codebase-aware orientation: given a change description, it identifies which specs, skills, and scripts are relevant and flags gaps where no spec covers the proposed change. It is called by `/start`, `/design`, and `/consolidate` to inform routing decisions.

## Decisions and Rationale

| ID | Decision | Alternatives | Rationale | Affected Specs | Date |
|----|----------|-------------|-----------|----------------|------|
| A1 | Three-layer enforcement model (L0/L1/L2) | All-or-nothing enforcement; per-hook toggles | Layers let projects adopt incrementally. Per-hook toggles are too granular. All-or-nothing discourages adoption. | All specs | 2026-03-17 |
| A2 | `CLAUDE.md` as Layer 0 foundation | Hooks-only enforcement; external config file | `CLAUDE.md` is always in context — it works even with no hooks. Hooks are defense-in-depth, not primary enforcement. | All specs | 2026-03-15 |
| A3 | Wrapper pattern for external tools | Replace external tools; ignore external tools | Wrapping preserves access to underlying tools while adding governance at transition points. Replacement creates lock-in. Ignoring misses enforcement opportunities. | `git-workflow-tooling.spec` | 2026-03-17 |
| A4 | Three-way version sync (spec tables, contracts.yaml, definition headers) | Single source of truth; two-way sync | Spec tables are human-readable, `contracts.yaml` is machine-readable, definition headers are canonical. The sync cost is accepted; contract tests detect drift mechanically. | All specs using shared definitions | 2026-03-15 |
| A5 | Skills declare their own layer in frontmatter | Central skill registry; no layer awareness | Keeps skill metadata co-located with skill definition. SessionStart reads frontmatter to build layer-appropriate suggestions. No central registry to maintain. | All specs | 2026-03-17 |
| A6 | Graceful degradation over strict prerequisite checks | Fail-fast when documents missing; silent skip | Reporting what's missing is more useful than crashing. Silent skip hides problems. Projects must be able to start from zero and build up. | All specs | 2026-03-15 |
| A7 | File-system-only governance state | Database; external service; git notes | Plain text files are versioned, diffable, branchable. No external dependencies. The register is a lookup table, not a queryable store. | All specs | 2026-03-15 |
| A8 | 4-level architecture model with consistent `owner:` label | C4 as-is; flat spec list; per-level labels | C4's Container level is empty for small projects. Consistent `owner:` label enables `grep "owner:"` across the entire project. The model adapts to project shape via archetypes. | All specs | 2026-03-20 |
