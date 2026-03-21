---
name: orient
description: Codebase orientation — given a change description, queries project-graph.yaml to show which specs, skills, and scripts are relevant and where gaps exist. Use at the start of new work or when unsure where a change fits.
disable-model-invocation: false
allowed-tools: Bash, Read, Grep, Glob
argument-hint: <change description or issue number>
layer: 0
---

# Orient

Given a change description (issue body, feature request, bug report, or free text), query `project-graph.yaml` to identify which parts of the project are relevant and whether existing specs cover the change.

## When to invoke

- At the start of new work (called by `/start` after fetching the issue)
- During design exploration (called by `/design` before brainstorming)
- When grouping changes (called by `/consolidate`)
- Directly by the user: `/orient <description>`

## Prerequisites

`project-graph.yaml` must exist at the project root. If missing, tell the user:
> "No project graph found. Run `bash scripts/generate-graph.sh` to generate it."

## Procedure

### 1. Resolve input

If `$ARGUMENTS` is a number (e.g., `42`), fetch the issue:
```bash
gh issue view $ARGUMENTS --json title,body --jq '"\(.title)\n\(.body)"'
```

Otherwise, use `$ARGUMENTS` as the change description directly.

### 2. Read the graph

Read `project-graph.yaml` from the project root.

### 3. Extract search terms

From the change description, extract meaningful terms:
- File paths (e.g., `scripts/health-check.sh`)
- Skill references (e.g., `/start`, `/validate-refs`)
- Spec names (e.g., `consolidate-spec`, `git-workflow-tooling`)
- Keywords related to project concepts (e.g., "register", "hook", "branch", "definition", "contract")

Filter out common words (the, a, is, this, that, for, with, etc.)

### 4. Match against graph nodes

For each node in the graph, score it:
- **+3** for exact ID match (search term matches node ID)
- **+2** for path match (search term appears in node path)
- **+1** for description/name match (search term appears in node description or name)

### 5. Walk edges for proximity

For each node that scored > 0, follow edges one hop:
- `owns` edge → add +1 to the connected node
- `calls`/`runs` edge → add +1 to the connected node
- `requires`/`provides` edge → add +1 to the connected node
- `belongs-to-stage` → find other nodes in the same stage, add +1

### 6. Rank and filter

Sort all nodes by score descending. Take the top 5-8 with score > 0.

Group into:
- **Closest matches** (score >= 3): directly relevant
- **Related by proximity** (score 1-2): structurally nearby

### 7. Gap detection

If the highest score is <= 2, or if the change description mentions concepts that don't match any node, flag:
> **Gap:** No existing spec covers [concept]. New spec likely needed.

### 8. Present the orientation report

Format:
```
## Orientation: [Issue title or description summary]

**Closest matches:**
- [node id] ([stage/type]) — [why it matched]

**Related by proximity:**
- [node id] — [relationship that connected it]

**Gap:** [if applicable]

**Suggested routing:**
- [Modify existing spec X / Create new spec / This spans specs X and Y]
```

## Important

- This skill is **read-only and informational**. It never modifies files, creates specs, or blocks workflow.
- If `project-graph.yaml` seems stale (file is older than any spec or skill), note this in the output.
- Keep the report concise — orientation should take seconds to read, not minutes.
