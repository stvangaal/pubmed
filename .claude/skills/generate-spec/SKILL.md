---
name: generate-spec
description: Create governed specification, definition, or architecture documents following the spec-driven workflow. Use when you need a new spec, shared definition, reference document, or architecture doc.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Edit, Write
layer: 0
---

# Spec Document Generator

You are generating a governed document for the spec-driven workflow. Follow this procedure exactly.

## Step 1: Gather Context

Read these files to understand the current project state:

1. `SPEC-WORKFLOW.md` — the full workflow, templates, and rules
2. `docs/ARCHITECTURE.md` — if it exists, for component and definition context
3. `docs/REGISTER.md` — if it exists, for existing specs, definitions, and ownership
4. `contracts.yaml` — if it exists, for current version pins

Also scan `docs/definitions/` and `docs/specs/` for existing documents.

## Step 2: Ask Clarifying Questions

Ask the user **all of the following** in a single AskUserQuestion call to determine what they need:

**Question 1 — Document type:**
Ask what kind of document they want to create. Options:
- **Specification** — a new spec for a bounded piece of implementation (most common)
- **Shared Definition** — a data structure or contract shared across specs
- **Reference Document** — domain knowledge, governance, or context material
- **Architecture Document** — the system-level architecture (only one per project)

**Question 2 — Scope description:**
Ask the user to describe in a few sentences what this document covers. What problem does it solve? What module or data structure does it describe?

Based on their answers, you may need a follow-up round of questions (Step 3).

## Step 3: Type-Specific Clarification

### If Specification:

Ask these follow-up questions:

1. **Minimal or full template?** Ask: "Does this spec share data structures or contracts with other specs?"
   - **No (standalone)** → use the minimal template (`docs/templates/spec-minimal.md`). This is the default for new specs.
   - **Yes (shared dependencies)** → use the full template (`docs/templates/spec-full.md`), which includes Requires/Provides tables and frontmatter with `requires:`/`provides:` fields.

2. **Which component/area does this spec cover?** List the components from ARCHITECTURE.md (if it exists). Let them pick one or describe a new one.

3. **Target phase?** Show the phases from the architecture or project plan. The user picks which phase this spec belongs to.

4. **What does the user already know about the behaviour?** Ask them to describe:
   - The key behaviours / rules this module must implement
   - Any known inputs and outputs
   - Any known constraints or edge cases
   - Any unresolved questions they're aware of

5. **Are there existing documents with relevant content?** List any reference or legacy docs that might contain source material. Let them select which ones to mine.

### If Shared Definition:

Ask:

1. **What data structure or contract does this define?** (e.g., "the User domain object", "the QueryInterface abstract class")
2. **Which specs will provide or require this?** Check against the register or existing specs.
3. **What notation should the schema use?** Default is Python dataclasses.

### If Reference Document:

Ask:

1. **What domain knowledge does this capture?**
2. **Which specs will reference this?**

### If Architecture Document:

Confirm they want to create the single project-level architecture document. Check if one already exists — if so, warn that it will be replaced and suggest editing instead.

## Step 4: Mine Source Material

If the user identified existing documents or other sources, read them and extract the relevant content:

- For specs: extract stage descriptions, decision items, done criteria, interface descriptions
- For definitions: extract schema fields, constraints, relationships
- For architecture: extract component descriptions, data flows, integration points, cross-cutting decisions

Summarize what you found and present it to the user for confirmation before proceeding.

## Step 5: Generate the Document

Use the appropriate template for the chosen document type. Fill in sections as follows:

### For Minimal Specifications (standalone, no shared dependencies):

Read `docs/templates/spec-minimal.md` and use it as the base. Fill in the YAML frontmatter and sections:

| Field / Section | How to fill |
|---|---|
| **`name` (frontmatter)** | Spec identifier — matches the filename without `.spec.md` (e.g., `auth-service`) |
| **`status` (frontmatter)** | `draft` |
| **`owner` (frontmatter)** | GitHub username (e.g., `@username`) from user's answer, or `TBD` |
| **`owns` (frontmatter)** | List of glob patterns for files this spec owns (e.g., `src/auth/**/*.ts`, `tests/auth/**/*.ts`). Derive from the user's scope description and any existing code on disk. If unknown, leave as a placeholder and note it is unresolved. |
| **Title (`# ...`)** | Human-readable spec name |
| **Purpose** | Write 1-3 sentences from user's scope description |
| **Behaviour** | Write from user's description + mined source material. Be precise. Flag ambiguities as "**Unresolved:**" items rather than guessing. |
| **Tests — Unit** | Derive test cases from each behaviour rule. One test per distinct behaviour. |

### For Full Specifications (with shared definitions or cross-spec dependencies):

Read `docs/templates/spec-full.md` and use it as the base. Fill in the YAML frontmatter and sections:

| Section | How to fill |
|---|---|
| **`name` (frontmatter)** | Spec identifier — matches the filename without `.spec.md` |
| **`status` (frontmatter)** | `draft` |
| **`owner` (frontmatter)** | GitHub username (e.g., `@username`) from user's answer, or `TBD` |
| **`owns` (frontmatter)** | List of glob patterns for files this spec owns. Derive from user's scope description. |
| **`requires` (frontmatter)** | List entries with `name` (definition or spec identifier) and `version`. This is the machine-readable source of truth; mirrors the Requires table. |
| **`provides` (frontmatter)** | List entries with `name` (export identifier) and `version`. This is the machine-readable source of truth; mirrors the Provides table. |
| **Status** | `draft` |
| **Owner** | Ask user, or leave as "TBD (architecture owner assigns)" |
| **Target Phase** | From user's answer in Step 3 |
| **Purpose** | Write 1-3 sentences from user's scope description |
| **Requires** | Derive from behaviour description — identify which shared definitions and other specs' provides are needed. Cross-reference with existing definitions. Keep in sync with `requires:` frontmatter. |
| **Provides** | Derive from behaviour description — what functions, classes, or interfaces will this spec export? Keep in sync with `provides:` frontmatter. |
| **Behaviour** | Write from user's description + mined source material. Be precise. Flag ambiguities as "**Unresolved:**" items rather than guessing. |
| **Decisions** | Migrate any relevant entries from existing documents. Leave table empty if none apply yet. |
| **Tests — Unit** | Derive test cases from each behaviour rule. One test per distinct behaviour. |
| **Tests — Contract** | If Requires or Provides references shared definitions: generate test descriptions verifying conformance. If none: write "N/A — no shared definition references." |
| **Tests — Integration** | If cross-spec dependencies exist: describe integration scenarios. If none: write "N/A — no cross-spec dependencies." |
| **Environment Requirements** | Include if external runtime is needed. Omit if fully locally testable. |
| **Implementation Notes** | Include guidance from existing docs, user input, or architectural constraints. |

### For Shared Definitions:

| Section | How to fill |
|---|---|
| **Status** | `draft` |
| **Version** | `v0` (draft definitions always start at v0) |
| **Description** | From user's scope description |
| **Schema** | Use the project's chosen notation. Derive fields from source material and user description. |
| **Constraints** | Validation rules, invariants, nullability. Mine from existing documents. |
| **Changelog** | Initial entry with today's date. |

### For Architecture:

Follow the architecture template from SPEC-WORKFLOW.md §3. Keep under 5,000 words. Reference shared definitions for schemas — do not inline them.

### For Reference:

No required template. Organize the domain knowledge clearly with sections appropriate to the content.

## Step 6: Gap Analysis

After generating the document, present a summary to the user:

1. **Completeness check** — list any sections that are thin or placeholder
2. **Unresolved questions** — list all ambiguities flagged as "Unresolved" in the behaviour section
3. **Missing dependencies** — list any shared definitions or specs that this document references but don't exist yet
4. **Suggested next steps** — what should be created or decided before this document can move from `draft` to `ready`

## Step 7: Write the File

Write the document to the correct location:

- Specs: `docs/specs/<name>.spec.md`
- Definitions: `docs/definitions/<name>.md`
- Architecture: `docs/ARCHITECTURE.md`
- Reference: `docs/reference/<name>.md`

If `docs/REGISTER.md` exists, update it with the new document entry. If `contracts.yaml` exists and the document has version pins, update it too.

## Important Rules

- **Never invent behaviour.** If you don't have enough information to fill a section precisely, flag it as unresolved rather than guessing. The human owns "what" and "why"; you handle "traceability" and "structure".
- **Follow collaborative authoring.** The human writes Purpose and Behaviour intent; you derive Requires/Provides tables, test stubs, and boilerplate.
- **Respect the creation order.** If prerequisites don't exist (e.g., no ARCHITECTURE.md when creating a spec), warn the user and suggest creating prerequisites first — but proceed if they choose to.
- **Use today's date** (from CLAUDE.md) for changelog entries and file naming.
- **Cross-reference existing documents.** If the document being created relates to existing specs, definitions, or reference docs, use them for source material and consistency.

$ARGUMENTS
