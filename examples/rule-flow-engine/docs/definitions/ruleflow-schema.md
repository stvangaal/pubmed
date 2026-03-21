# RuleFlow Schema Types

## Status
stable

## Version
v1

## Description
The canonical type system for RuleFlow decision tree schemas. Defines the data shape that all engine modules consume: the traverser walks it, the analyzer validates it, and the mermaid generator renders it. Exists as a shared definition because all three specs import from the same `types.ts` — one canonical source prevents schema divergence.

## Schema

```typescript
// --- Variables ---

export interface EnumVariable {
  type: "enum";
  values: string[];
  label: string;
}

export interface BooleanVariable {
  type: "boolean";
  label: string;
}

export type Variable = EnumVariable | BooleanVariable;

// --- Goto targets ---

export interface ConditionalGoto {
  default: string;
  if: Array<{
    condition: Record<string, string | boolean>;
    goto: string;
  }>;
}

export type Goto = string | ConditionalGoto;

// --- Options ---

export interface Option {
  label: string;
  sublabel?: string;
  icon?: string;
  sets: Record<string, string | boolean>;
  goto: Goto;
  supplementary?: string[];
}

// --- Nodes ---

export interface Node {
  question: string;
  subtitle?: string;
  warning?: string | null;
  options: Option[];
}

// --- Results ---

export type Severity = "recommendation" | "warning" | "escalation";

export interface Result {
  title: string;
  detail: string;
  category: string;
  severity: Severity;
  tags: Record<string, string>;
  supplementary?: string[];
}

// --- Metadata ---

export interface Metadata {
  institution?: string;
  source?: string;
  last_reviewed?: string;
  authors?: string[];
  disclaimer?: string;
}

// --- Display ---

export interface DisplayTheme {
  primary_color?: string;
  font?: string;
}

export interface DisplayBranding {
  header_title?: string;
  header_subtitle?: string;
  footer?: string;
}

export interface Display {
  theme?: DisplayTheme;
  category_colors?: Record<string, string>;
  branding?: DisplayBranding;
}

// --- Top-level Schema ---

export interface RuleFlowSchema {
  id: string;
  version: string;
  title: string;
  description: string;
  metadata: Metadata;
  start_node: string;
  variables: Record<string, Variable>;
  nodes: Record<string, Node>;
  results: Record<string, Result>;
  display?: Display;
}
```

## Constraints
- Node and result IDs must be `snake_case`
- Goto targets use `"node_id"` for questions, `"result:result_id"` for terminals
- Variables must be declared in top-level `variables` before use in any option's `sets`
- Every option's `sets` values must match the variable's type (enum value from allowed list, or boolean)
- Every path from `start_node` must reach a `result:` terminal
- Node IDs and result IDs must not overlap

## Changelog
| Date | Version | Change | Affected Specs |
|------|---------|--------|----------------|
| 2026-03-15 | v1 | Initial stable release | traverser, analyzer, mermaid-generator |
