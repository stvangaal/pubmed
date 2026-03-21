// Analysis report types matching SPEC.md §4.3

export type FindingLevel = "error" | "warning" | "info";

export interface Finding {
  type: string;
  description: string;
  suggestion?: string;
}

export interface AnalysisSummary {
  total_nodes: number;
  total_results: number;
  total_edges: number;
  max_path_depth: number;
  min_path_depth: number;
  variable_state_space: number;
  covered_states: number;
  uncovered_states: number;
  coverage_pct: number;
}

export interface AnalysisReport {
  schema_id: string;
  schema_version: string;
  timestamp: string;
  summary: AnalysisSummary;
  errors: Finding[];
  warnings: Finding[];
  info: Finding[];
}
