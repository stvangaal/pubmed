// Main analyzer entry point.
// Pure function: schema → AnalysisReport

import type { RuleFlowSchema } from "../types";
import type { AnalysisReport, Finding } from "./types";
import { runStructuralChecks } from "./structural";
import {
  checkCoverageGaps,
  checkConflicts,
  checkAsymmetricDepth,
  checkStyleIssues,
  countEdges,
} from "./coverage";

export function analyze(schema: RuleFlowSchema): AnalysisReport {
  // Structural checks (errors)
  const errors = runStructuralChecks(schema);

  // Logic checks (warnings) — only run if no structural errors,
  // since coverage simulation needs valid graph structure
  let warnings: Finding[] = [];
  let coveredCount = 0;
  let uncoveredCount = 0;
  let stateSpace = 0;
  let maxDepth = 0;
  let minDepth = 0;

  if (errors.length === 0) {
    const coverage = checkCoverageGaps(schema);
    coveredCount = coverage.coveredCount;
    uncoveredCount = coverage.uncoveredCount;
    stateSpace = coverage.stateSpace;

    const conflicts = checkConflicts(schema);
    const depth = checkAsymmetricDepth(schema);
    maxDepth = depth.maxDepth;
    minDepth = depth.minDepth;

    warnings = [...coverage.findings, ...conflicts, ...depth.findings];
  } else {
    // Still compute state space size even with errors
    stateSpace = 1;
    for (const def of Object.values(schema.variables)) {
      stateSpace *= def.type === "enum" ? def.values.length : 2;
    }
  }

  // Style checks (info) — always run
  const info = checkStyleIssues(schema);

  return {
    schema_id: schema.id,
    schema_version: schema.version,
    timestamp: new Date().toISOString(),
    summary: {
      total_nodes: Object.keys(schema.nodes).length,
      total_results: Object.keys(schema.results).length,
      total_edges: countEdges(schema),
      max_path_depth: maxDepth,
      min_path_depth: minDepth,
      variable_state_space: stateSpace,
      covered_states: coveredCount,
      uncovered_states: uncoveredCount,
      coverage_pct:
        stateSpace > 0
          ? Math.round((coveredCount / stateSpace) * 1000) / 10
          : 100,
    },
    errors,
    warnings,
    info,
  };
}

export type { AnalysisReport, Finding, FindingLevel } from "./types";
