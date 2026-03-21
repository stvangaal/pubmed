---
name: start
description: Entry point for new work — ensures a GitHub issue exists, determines whether the change is planned or exploratory, and routes to the appropriate workflow path. Auto-invoked by CLAUDE.md when a change request is detected.
disable-model-invocation: false
allowed-tools: Bash, Read, Grep, Glob
layer: 0
---

# Start

Entry point for all change requests. Establishes context and routes the user into the correct workflow path.

## When to invoke

Claude should invoke this skill (or follow its logic) whenever the user:
- Asks to add a feature, fix a bug, refactor code, or make any change
- References a GitHub issue they want to work on
- Starts a session with an intent to modify the project

This skill is read-only and does not modify any files. It gathers context and recommends next steps.

## Procedure

### 1. Identify the change request

From the user's message, extract:
- **What** they want to change (feature, bug fix, refactor, docs, etc.)
- **Why** (if stated)
- **Any referenced issue number** (e.g., "fix #12", "working on issue 42")

### 2. Check for a GitHub issue

If the user referenced an issue number:
```bash
gh issue view <number> --json title,state,body
```

If no issue was referenced, check if there's an open issue that matches:
```bash
gh issue list --state open --limit 20
```

Present what you found:
- If a matching issue exists: "Found issue #N: <title>. Working from this?"
- If no issue exists: "No GitHub issue found for this work. Want me to create one, or proceed without?"

Do not block on issue creation — suggest it but proceed if the user declines.

### 2b. Orient against project graph

If `project-graph.yaml` exists at the project root, run `/orient` with the issue title and body (or the user's change description if no issue) to understand where this change fits in the existing project structure. Present the orientation results to the user before continuing.

If `project-graph.yaml` does not exist, skip this step silently.

### 3. Check current branch and project state

```bash
git rev-parse --abbrev-ref HEAD
git status --short
```

Report:
- Current branch (are they already on a feature branch?)
- Any uncommitted work
- Whether they need to create a feature branch

### 4. Determine the workflow path

Based on the user's request, recommend one of two paths:

**Planned path** — when the user knows what they want to build:
- Clear feature request ("add X", "change Y to do Z")
- Bug with known root cause ("the auth handler doesn't validate expiry")
- Refactor with clear scope ("split the router into per-resource files")

**Exploratory path** — when the user needs to investigate first:
- Unclear bug ("something is wrong with login")
- Open-ended exploration ("can we improve performance?")
- Unfamiliar area ("I need to understand how the auth system works before changing it")

Present your recommendation:
> "This sounds like a **planned change** — you know what you want to build. I'd recommend:
> 1. Design the change (brainstorm → governed spec)
> 2. Plan the implementation
> 3. Implement on a feature branch
>
> Want to start with the design?"

Or:
> "This sounds like it needs **exploration first** — let's investigate before committing to an approach. I'd recommend:
> 1. Create a feature branch
> 2. Explore / spike to understand the problem
> 3. Once you have clarity, formalize into a spec and implement properly
>
> Want to start exploring?"

### 5. Route to next step

Based on the user's choice:

- **Planned path:** Suggest invoking the brainstorming skill to design the change. After brainstorming completes, Claude should guide the user to run `/consolidate` to create the governed spec, then proceed to planning and implementation.

- **Exploratory path:** Help create a feature branch if needed. Let the user explore freely. When they signal readiness ("OK I understand now", "let's do it properly"), guide them to run `/consolidate` to formalize their learnings.

## Important

- This skill is **guidance, not a gate**. If the user wants to skip straight to coding, let them — but note what governance steps they're skipping.
- Do not create files, modify code, or make commits. This skill only gathers context and recommends.
- If the project is at Layer 0 with no governed documents yet, mention that `/init-project` can set up the infrastructure, but don't block on it.
- Keep the output concise. The user wants to start working, not read a manual.

$ARGUMENTS
