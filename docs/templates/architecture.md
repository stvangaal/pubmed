# [Project Name] — Architecture

## Architecture Owner
<!-- The person or role with final authority over shared definitions,
     cross-spec conflicts, and architectural decisions. -->

## Overview
<!-- What does this system do, at the highest level. Who/what are
     its users and external dependencies.

     Keep this document under ~5,000 words. It is read by the AI
     at the start of every implementation session. Push detailed
     component descriptions into specs. -->

## Components
<!-- Name each major component/module. For each: a 1–2 sentence
     description of its responsibility, and which spec owns it. -->

## Phase Map
<!-- Which specs are delivered in which phase. Derived from
     each spec's Target Phase field. -->

| Phase | Specs | Goal |
|-------|-------|------|

## Data Model
<!-- The key entities and their relationships. Reference shared
     definitions for schemas. An ERD or equivalent diagram is
     appropriate here. -->

## Data Flows
<!-- How data moves through the system. Identify the major
     workflows and describe them as sequences of component interactions.
     Reference the provides/requires contracts. -->

## Integration Points
<!-- External APIs, databases, third-party services. What shared
     definitions govern these boundaries. -->

## Cross-Cutting Concerns
<!-- Authentication, logging, error handling, configuration —
     anything that spans multiple specs. Identify which spec
     owns each concern and which shared definitions apply. -->

## Dependency Graph
<!-- Which specs depend on which other specs, derived from the
     provides/requires declarations. This determines implementation
     order within each phase. Can be a list, a table, or a
     Mermaid diagram. -->

## Decisions and Rationale
<!-- Cross-cutting decisions that affect 2+ specs.
     Spec-scoped decisions live in each spec's Decisions section.

     Record: the decision, alternatives considered, rationale,
     and which specs are affected. -->

| ID | Decision | Alternatives | Rationale | Affected Specs | Date |
|----|----------|-------------|-----------|----------------|------|
