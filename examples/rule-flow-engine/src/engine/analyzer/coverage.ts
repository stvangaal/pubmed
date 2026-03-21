// Coverage and logic checks (warnings).
// Enumerates the variable state space, simulates traversal for each combination,
// and identifies gaps, conflicts, and depth asymmetry.

import type {
  RuleFlowSchema,
  Variable,
  Option,
  Goto,
} from "../types";
import type { Finding } from "./types";
import { extractGotoTargets, parseTarget } from "./structural";

// --- State space enumeration ---

type VarState = Record<string, string | boolean>;

/** Generate the Cartesian product of all variable values. */
function enumerateStateSpace(
  variables: Record<string, Variable>
): VarState[] {
  const varNames = Object.keys(variables);
  if (varNames.length === 0) return [{}];

  const valueSets: Array<{ name: string; values: (string | boolean)[] }> = [];
  for (const [name, def] of Object.entries(variables)) {
    if (def.type === "enum") {
      valueSets.push({ name, values: def.values });
    } else {
      valueSets.push({ name, values: [true, false] });
    }
  }

  // Build Cartesian product iteratively
  let states: VarState[] = [{}];
  for (const { name, values } of valueSets) {
    const next: VarState[] = [];
    for (const state of states) {
      for (const val of values) {
        next.push({ ...state, [name]: val });
      }
    }
    states = next;
  }

  return states;
}

/** Compute total state space size without allocating all combinations. */
function stateSpaceSize(variables: Record<string, Variable>): number {
  let size = 1;
  for (const def of Object.values(variables)) {
    size *= def.type === "enum" ? def.values.length : 2;
  }
  return size;
}

// --- Traversal simulation ---

/** Resolve a conditional goto given the current variable state. */
function resolveGoto(goto: Goto, state: VarState): string {
  if (typeof goto === "string") return goto;

  // Check conditional branches in order
  for (const branch of goto.if) {
    const matches = Object.entries(branch.condition).every(
      ([key, val]) => state[key] === val
    );
    if (matches) return branch.goto;
  }

  return goto.default;
}

interface TraversalResult {
  resultId: string | null;
  depth: number;
  state: VarState;
}

/**
 * Simulate traversal from start_node, choosing options that are consistent
 * with the given target state. Returns the result reached (or null if stuck).
 *
 * Strategy: at each node, pick the first option whose `sets` values are all
 * consistent with the target state (i.e. every value in sets matches the
 * target state for that variable).
 */
function simulateTraversal(
  schema: RuleFlowSchema,
  targetState: VarState
): TraversalResult {
  let currentNode = schema.start_node;
  const actualState: VarState = {};
  const visited = new Set<string>();
  let depth = 0;

  while (true) {
    if (visited.has(currentNode)) {
      return { resultId: null, depth, state: actualState }; // cycle
    }
    visited.add(currentNode);

    const node = schema.nodes[currentNode];
    if (!node) {
      return { resultId: null, depth, state: actualState }; // dangling
    }

    depth++;

    // Find first option consistent with target state
    const option = findConsistentOption(node.options, targetState);
    if (!option) {
      return { resultId: null, depth, state: actualState }; // no matching option
    }

    // Apply variable assignments
    for (const [key, val] of Object.entries(option.sets)) {
      actualState[key] = val;
    }

    // Resolve goto
    const target = resolveGoto(option.goto, actualState);
    const parsed = parseTarget(target);

    if (parsed.type === "result") {
      return { resultId: parsed.id, depth, state: actualState };
    }

    currentNode = parsed.id;
  }
}

/**
 * Find the first option whose `sets` values are all consistent with the
 * target state. An option is consistent if for every variable it sets,
 * the value matches what the target state expects for that variable.
 */
function findConsistentOption(
  options: Option[],
  targetState: VarState
): Option | null {
  for (const option of options) {
    const consistent = Object.entries(option.sets).every(
      ([key, val]) => !(key in targetState) || targetState[key] === val
    );
    if (consistent) return option;
  }
  return null;
}

// --- Coverage gap detection ---

/** Format a variable state as a human-readable string. */
function formatState(state: VarState): string {
  return Object.entries(state)
    .map(([k, v]) => `${k}=${v}`)
    .join(", ");
}

export function checkCoverageGaps(schema: RuleFlowSchema): {
  findings: Finding[];
  coveredCount: number;
  uncoveredCount: number;
  stateSpace: number;
} {
  const findings: Finding[] = [];
  const totalSpace = stateSpaceSize(schema.variables);

  // For schemas with no variables, there's exactly 1 state (the empty state)
  const allStates = enumerateStateSpace(schema.variables);
  let coveredCount = 0;

  for (const targetState of allStates) {
    const result = simulateTraversal(schema, targetState);
    if (result.resultId) {
      coveredCount++;
    } else {
      findings.push({
        type: "coverage_gap",
        description: `No path covers: ${formatState(targetState)}`,
        suggestion:
          "Add a pathway for this combination or route to a fallback result.",
      });
    }
  }

  return {
    findings,
    coveredCount,
    uncoveredCount: totalSpace - coveredCount,
    stateSpace: totalSpace,
  };
}

// --- Conflict detection ---

export function checkConflicts(schema: RuleFlowSchema): Finding[] {
  const findings: Finding[] = [];
  // Map: serialized actual state → result ID. If same state leads to
  // different results, that's a conflict.
  const stateResultMap = new Map<string, string>();
  const allStates = enumerateStateSpace(schema.variables);

  for (const targetState of allStates) {
    const result = simulateTraversal(schema, targetState);
    if (!result.resultId) continue;

    // Key by the actual state that was set during traversal (not the target)
    const stateKey = formatState(result.state);
    const existing = stateResultMap.get(stateKey);

    if (existing && existing !== result.resultId) {
      findings.push({
        type: "redundant_path",
        description: `State {${stateKey}} leads to both "${existing}" and "${result.resultId}".`,
        suggestion:
          "This may indicate a genuine conflict in the business rules. Verify which result is correct.",
      });
      // Only report once per state
      stateResultMap.set(stateKey, result.resultId + "+" + existing);
    } else if (!existing) {
      stateResultMap.set(stateKey, result.resultId);
    }
  }

  return findings;
}

// --- Path depth analysis ---

interface PathInfo {
  depth: number;
  resultId: string;
}

/** Walk all paths from start_node via DFS, collecting depths. */
function allPathDepths(schema: RuleFlowSchema): PathInfo[] {
  const paths: PathInfo[] = [];

  function dfs(nodeId: string, depth: number, visited: Set<string>): void {
    if (visited.has(nodeId)) return;
    const node = schema.nodes[nodeId];
    if (!node) return;

    visited.add(nodeId);

    for (const option of node.options) {
      for (const target of extractGotoTargets(option.goto)) {
        const parsed = parseTarget(target);
        if (parsed.type === "result") {
          paths.push({ depth: depth + 1, resultId: parsed.id });
        } else {
          dfs(parsed.id, depth + 1, new Set(visited));
        }
      }
    }
  }

  dfs(schema.start_node, 0, new Set());
  return paths;
}

export function checkAsymmetricDepth(schema: RuleFlowSchema): {
  findings: Finding[];
  maxDepth: number;
  minDepth: number;
} {
  const paths = allPathDepths(schema);
  if (paths.length === 0) {
    return { findings: [], maxDepth: 0, minDepth: 0 };
  }

  const depths = paths.map((p) => p.depth);
  const maxDepth = Math.max(...depths);
  const minDepth = Math.min(...depths);
  const findings: Finding[] = [];

  // Flag if max depth is more than 3x the min depth (significant asymmetry)
  if (minDepth > 0 && maxDepth / minDepth > 3) {
    findings.push({
      type: "asymmetric_depth",
      description: `Path depths range from ${minDepth} to ${maxDepth} steps (${(maxDepth / minDepth).toFixed(1)}x ratio).`,
      suggestion:
        "Consider restructuring to reduce the depth disparity for a more balanced UX.",
    });
  }

  return { findings, maxDepth, minDepth };
}

// --- Style checks (info) ---

export function checkStyleIssues(schema: RuleFlowSchema): Finding[] {
  const findings: Finding[] = [];

  // Long paths (> 8 steps)
  const paths = allPathDepths(schema);
  const longPaths = paths.filter((p) => p.depth > 8);
  if (longPaths.length > 0) {
    findings.push({
      type: "long_path",
      description: `${longPaths.length} path(s) exceed 8 steps (max: ${Math.max(...longPaths.map((p) => p.depth))}).`,
      suggestion: "Consider restructuring to reduce the number of steps.",
    });
  }

  // Fat nodes (> 5 options)
  for (const [nodeId, node] of Object.entries(schema.nodes)) {
    if (node.options.length > 5) {
      findings.push({
        type: "fat_node",
        description: `Node "${nodeId}" has ${node.options.length} options.`,
        suggestion:
          "Consider splitting into sub-questions to reduce cognitive load.",
      });
    }
  }

  // Empty details
  for (const [resultId, result] of Object.entries(schema.results)) {
    if (!result.detail || result.detail.trim() === "") {
      findings.push({
        type: "empty_detail",
        description: `Result "${resultId}" has no detail text.`,
        suggestion: "Add detail text to help the user understand the recommendation.",
      });
    }
  }

  // Unused variables (defined but never set)
  const setVars = new Set<string>();
  for (const node of Object.values(schema.nodes)) {
    for (const option of node.options) {
      for (const key of Object.keys(option.sets)) {
        setVars.add(key);
      }
    }
  }
  for (const varName of Object.keys(schema.variables)) {
    if (!setVars.has(varName)) {
      findings.push({
        type: "unused_variable",
        description: `Variable "${varName}" is defined but never set by any option.`,
        suggestion: "Remove it or add it to the relevant option sets.",
      });
    }
  }

  return findings;
}

// --- Edge counting ---

export function countEdges(schema: RuleFlowSchema): number {
  let count = 0;
  for (const node of Object.values(schema.nodes)) {
    for (const option of node.options) {
      count += extractGotoTargets(option.goto).length;
      if (option.supplementary) {
        count += option.supplementary.length;
      }
    }
  }
  return count;
}
