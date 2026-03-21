# CLAUDE.md — arboretum

## Project Overview

Arboretum is a spec-driven development framework for AI code agents. It provides a document-first workflow where every line of code traces back to a human-authored specification. The primary AI agent is Claude Code.

## Key Documents

| Document | Purpose |
|---|---|
| `SPEC-WORKFLOW.md` | Full workflow specification and governing rules |
| `docs/templates/` | Starter templates for specs and other document types |
| `.claude/skills/` | Slash skills (Claude Code commands) |
| `examples/rule-flow-engine/` | Fully governed sample project |

## CLI Usage

```bash
# Bootstrap a new spec-driven project
bin/arboretum bootstrap ~/Projects/my-project

# Update an existing project (run from within the project)
./arboretum update
```

## Development Workflow Rules

- **Ownership headers:** Every source file must include `# owner: <spec-name>` as its first comment line (language-appropriate comment syntax, always lowercase). No exceptions — configuration files, test helpers, scripts, and infrastructure files are all owned by exactly one spec.
- **4-level model:** Arboretum uses a 4-level architecture: System (`ARCHITECTURE.md`) → Spec Group (`docs/groups/`) → Spec (`docs/specs/`) → Code (source files). Every object declares its one owner via the `owner:` label at every level. All relationships are derivable by walking this ownership spine.

## Available Skills

| Skill | Purpose |
|---|---|
| `/generate-spec` | Create specs interactively |
| `/health-check` | Check for drift and orphaned files |
| `/pr` | Spec-aware pull request creation |
| `/consolidate` | Generate specs from existing code |
| `/check-register` | File ownership audit |
| `/promote-spec` | Advance spec through status machine |
| `/architect` | Design and maintain architecture structure |
