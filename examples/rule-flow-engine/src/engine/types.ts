// RuleFlow Schema TypeScript Types
// These types define the JSON schema format for decision tree wizards.
// See docs/SCHEMA_SPEC.md for the canonical format reference.

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
