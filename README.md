# Arboretum

**A spec-driven development framework for AI code agents.**

Arboretum gives AI-assisted projects a document-first workflow where every line of code traces to a human-authored specification. You define *what* to build and *why*; the AI implements *how* — within boundaries you control.

Arboretum externalizes the practices that experienced software engineers carry intuitively — project structure, work sequencing, safe evolution — into a process that anyone can follow.

## Who This Is For

Arboretum is for **domain experts building software with AI code agents**. If you have deep knowledge in your field but limited experience structuring software projects, this framework gives you opinionated guidance on how to think about what you're building, how to sequence the work, and how to evolve your project safely.

## What This Is Not

- **Not a library or framework you import** — there are no runtime dependencies. Arboretum is a workflow system made of documents, templates, and AI skills.
- **Not a CI/CD tool** — it complements your build pipeline, it doesn't replace it.
- **Not language-specific** — the governed workflow works with any language or stack.

## Principles

These are the ideas behind the workflow. Each one addresses a mistake that's expensive to learn the hard way.

### Think before you build

Every project starts with an architecture interview that helps you articulate what you're building, where it stops, what the risks are, and what needs exploration before committing to code. This happens before any implementation.

### Shape ideas before writing code

Work flows from abstract to concrete: problem statement → spike-spec cycles → governed spec → implementation. Spikes are cheap exploration tied to specific architectural questions. Code only gets written when the idea is mature — when a spec moves from draft to in-progress.

### Make the right thing easy

Templates, automation, and slash skills reduce the gap between knowing what to do and actually doing it. If the right thing requires manual discipline to remember, it won't happen consistently. Arboretum encodes good practices into the tools so the path of least resistance is also the correct path.

### Own every line

Every source file is owned by exactly one specification. This is single responsibility at the document level — if you need to change behaviour, you find the spec that owns it, update the spec, then update the code. No orphaned files, no ambiguous ownership, no changes without context.

### Change without breaking

Software lives longer than you expect, and requirements shift. These principles make evolution cheap and safe:

- **Single responsibility** — components that do one thing don't cause ripple effects when changed.
- **Low coupling** — components that don't know about each other can't break each other.
- **Explicit contracts** — when the interface between A and B is written down, internals can change freely.
- **Small, frequent changes** — easier to reason about, easier to revert.
- **Tests as change detectors** — test-driven development tells you what you broke before your users do.

### Learn from each cycle

Natural stopping points (after a PR merges, after a spike completes) include a prompt to reflect on what you learned. The value isn't the log — it's building the habit of extracting lessons while the context is fresh.

## Components

### Architecture modeling

The `/architect` skill guides you through a structured interview to determine your project's shape. It matches your project to an architecture archetype (e.g., pipeline, library) that provides canonical structure, essential decisions to make early, and areas that need exploratory spikes.

Projects use a 4-level architecture model:

| Level | What it captures | Artifact |
|-------|-----------------|----------|
| **System** | What the project is, who uses it | `ARCHITECTURE.md` |
| **Spec Group** | Major capability areas | `docs/groups/<name>.md` |
| **Spec** | Single responsibility units | `docs/specs/<name>.spec.md` |
| **Code** | Source files | Files with `# owner: <spec-name>` header |

### Workflow stages

The development workflow sequences decisions so they happen in the right order:

```
Problem / Issue
    │
    ▼
Architecture Interview ──── /architect
    │
    ▼
Design ◄──── brainstorm → consolidate into governed spec
    │
    ▼
Plan ──────── implementation plan with test strategy
    │
    ▼
Implement ─── TDD: red → green → refactor
    │
    ▼
Finish ────── verification → spec promotion → PR
    │
    ▼
Reflect ───── what did you learn?
    │
    ▼
Cleanup ───── post-merge housekeeping
```

Two paths exist: **planned** (you know what to build) and **exploratory** (you need to investigate first). The exploratory path adds spike-spec cycles before implementation.

### Progressive governance

Arboretum scales with your project:

- **Layer 0 (Foundation)** — CLAUDE.md, minimal specs, core skills. Always on.
- **Layer 1 (Structure)** — Architecture doc, auto-register, shared definitions. Activates at 3+ specs.
- **Layer 2 (Governance)** — Version pins, CI integration, team review gates. Activates for multi-dev.

Start simple. Add governance only when complexity warrants it.

### Skills

Skills are slash commands that automate governance tasks:

| Skill | What it does |
|-------|-------------|
| `/architect` | Guided architecture interview and scaffolding |
| `/init-project` | Bootstrap project governance end-to-end |
| `/start` | Entry point for new work — routes to the right workflow path |
| `/generate-spec` | Create a new spec from a template |
| `/health-check` | Detect drift between specs and code |
| `/spec-status` | Show the current state of all specs |

## Getting Started

### Prerequisites

- **macOS or Linux** (Windows: use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install))
- [Git](https://git-scm.com/)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (CLI)

### Create a New Project

```bash
# Clone arboretum (once)
git clone <arboretum-repo-url> ~/arboretum

# Bootstrap a new project
~/arboretum/bin/arboretum bootstrap ~/Projects/my-project
```

This creates a project with arboretum-owned scaffolding (workflow, templates, skills) and project-owned files (CLAUDE.md, specs, code) that you control.

### Update an Existing Project

```bash
# From inside your project
./arboretum update
```

This refreshes arboretum-owned files (workflow docs, skills, hooks) without touching your project files.

## Where Flexibility Exists

Arboretum is opinionated, but not rigid:

- **Architecture archetypes are starting points** — they give you a structure to begin with. If your project doesn't fit an archetype, the system scaffolds a minimal architecture you can shape yourself.
- **Governance is progressive** — you opt into complexity when your project needs it. A solo project with 2 specs doesn't need version pins or CI gates.
- **Spikes are first-class** — when you don't know the answer, the framework expects you to explore before committing. Spikes are not failure; they're the process working correctly.
- **Skills suggest, not block** — workflow skills recommend next steps but don't prevent you from working differently if you have a reason.

## Sample Project

See `examples/rule-flow-engine/` for a fully governed sample with every arboretum artifact: architecture, definitions, specs, register, and version pins.

## Contributing

Arboretum is maintained at [arboretum-dev](https://github.com/stvangaal/arboretum-dev). If you'd like to contribute, open an issue there.
