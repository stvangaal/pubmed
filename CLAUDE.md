# CLAUDE.md — arboretum

## Project Overview

Arboretum is a spec-driven development framework for AI code agents. It provides a document-first workflow where every line of code traces back to a human-authored specification. The primary AI agent is Claude Code.

## Key Documents

| Document | Purpose |
|---|---|
| `SPEC-WORKFLOW.md` | Full workflow specification and governing rules |
| `docs/templates/` | Starter templates for specs and other document types |
| `.claude/skills/` | Slash skills (Claude Code commands) |

## CLI Usage

```bash
# Bootstrap a new spec-driven project
bin/arboretum bootstrap ~/Projects/my-project

# Update is planned but not yet implemented.
# For now, re-run bootstrap — it is idempotent.
```

## Development Workflow Rules

- **Ownership headers:** Every source file must include `# owner: <spec-name>` as its first comment line (language-appropriate comment syntax, always lowercase). No exceptions — configuration files, test helpers, scripts, and infrastructure files are all owned by exactly one spec.
- **4-level model:** Arboretum uses a 4-level architecture: System (`ARCHITECTURE.md`) → Spec Group (`docs/groups/`) → Spec (`docs/specs/`) → Code (source files). Every object declares its one owner via the `owner:` label at every level. All relationships are derivable by walking this ownership spine.

## Available Skills

| Skill | Purpose |
|---|---|
| `/architect` | Design and maintain architecture structure |
| `/check-contracts` | Check version pin staleness |
| `/check-register` | File ownership audit |
| `/cleanup` | Post-merge cleanup |
| `/consolidate` | Generate specs from existing code |
| `/design` | Orchestrate design phase |
| `/finish` | Complete implementation, verify, create PR |
| `/generate-register` | Auto-generate REGISTER.md from spec frontmatter |
| `/generate-spec` | Create specs interactively |
| `/health-check` | Check for drift and orphaned files |
| `/init-project` | Initialize new project with spec governance |
| `/orient` | Codebase orientation via project-graph.yaml |
| `/pr` | Spec-aware pull request creation |
| `/promote-spec` | Advance spec through status machine |
| `/reflect` | Lightweight learning interview |
| `/security-review` | Analyze AI-facing code for prompt injection |
| `/spec-status` | Dashboard of all spec statuses |
| `/start` | **Orchestrator** — guides from idea through issue, spec, plan, tests, and code. Detects scale. Cross-session resumption via `.claude/progress/`. |
| `/sync-contracts` | Regenerate contracts.yaml from specs |
| `/validate-refs` | Cross-reference validation |
