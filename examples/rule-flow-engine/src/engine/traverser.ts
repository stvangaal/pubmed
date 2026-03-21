// Wizard state machine — drives the step-by-step traversal of a schema.
// No React dependency. Pure state management.

import type { RuleFlowSchema, Node, Option, Result, Goto } from "./types";

export interface HistoryEntry {
  nodeId: string;
  question: string;
  selectedOption: Option;
  selectedIndex: number;
}

export interface TraverserState {
  currentNodeId: string | null;
  currentResultId: string | null;
  supplementaryResultIds: string[];
  variables: Record<string, string | boolean>;
  history: HistoryEntry[];
  stepNumber: number;
}

/** Resolve a goto value against the current variable state. */
function resolveGoto(
  goto: Goto,
  variables: Record<string, string | boolean>
): string {
  if (typeof goto === "string") return goto;

  for (const branch of goto.if) {
    const matches = Object.entries(branch.condition).every(
      ([key, val]) => variables[key] === val
    );
    if (matches) return branch.goto;
  }

  return goto.default;
}

/** Parse a goto target string. */
function parseTarget(target: string): { type: "node" | "result"; id: string } {
  if (target.startsWith("result:")) {
    return { type: "result", id: target.slice(7) };
  }
  return { type: "node", id: target };
}

/** Create the initial traverser state for a schema. */
export function createInitialState(schema: RuleFlowSchema): TraverserState {
  return {
    currentNodeId: schema.start_node,
    currentResultId: null,
    supplementaryResultIds: [],
    variables: {},
    history: [],
    stepNumber: 1,
  };
}

/** Get the current node object, or null if we're at a result. */
export function getCurrentNode(
  schema: RuleFlowSchema,
  state: TraverserState
): Node | null {
  if (!state.currentNodeId) return null;
  return schema.nodes[state.currentNodeId] ?? null;
}

/** Get the current result object, or null if we're at a question. */
export function getCurrentResult(
  schema: RuleFlowSchema,
  state: TraverserState
): Result | null {
  if (!state.currentResultId) return null;
  return schema.results[state.currentResultId] ?? null;
}

/** Get supplementary result objects. */
export function getSupplementaryResults(
  schema: RuleFlowSchema,
  state: TraverserState
): Result[] {
  return state.supplementaryResultIds
    .map((id) => {
      const parsed = parseTarget(id);
      return schema.results[parsed.type === "result" ? parsed.id : id];
    })
    .filter(Boolean);
}

/**
 * Select an option at the current node. Returns a new state.
 * Immutable — does not modify the input state.
 */
export function selectOption(
  schema: RuleFlowSchema,
  state: TraverserState,
  optionIndex: number
): TraverserState {
  if (!state.currentNodeId) return state;

  const node = schema.nodes[state.currentNodeId];
  if (!node) return state;

  const option = node.options[optionIndex];
  if (!option) return state;

  // Apply variable assignments
  const newVariables = { ...state.variables };
  for (const [key, val] of Object.entries(option.sets)) {
    newVariables[key] = val;
  }

  // Record in history
  const historyEntry: HistoryEntry = {
    nodeId: state.currentNodeId,
    question: node.question,
    selectedOption: option,
    selectedIndex: optionIndex,
  };

  // Resolve goto
  const target = resolveGoto(option.goto, newVariables);
  const parsed = parseTarget(target);

  // Collect supplementary results
  const supplementary = option.supplementary ?? [];

  if (parsed.type === "result") {
    return {
      currentNodeId: null,
      currentResultId: parsed.id,
      supplementaryResultIds: supplementary,
      variables: newVariables,
      history: [...state.history, historyEntry],
      stepNumber: state.stepNumber + 1,
    };
  }

  return {
    currentNodeId: parsed.id,
    currentResultId: null,
    supplementaryResultIds: [],
    variables: newVariables,
    history: [...state.history, historyEntry],
    stepNumber: state.stepNumber + 1,
  };
}

/**
 * Go back one step. Returns a new state with the last selection undone.
 * Variables set by the undone step are rolled back.
 */
export function goBack(
  _schema: RuleFlowSchema,
  state: TraverserState
): TraverserState {
  if (state.history.length === 0) return state;

  const newHistory = state.history.slice(0, -1);

  // Rebuild variable state by replaying history
  const newVariables: Record<string, string | boolean> = {};
  for (const entry of newHistory) {
    for (const [key, val] of Object.entries(entry.selectedOption.sets)) {
      newVariables[key] = val;
    }
  }

  // The current node is the node from the last history entry
  const lastEntry = state.history[state.history.length - 1];

  return {
    currentNodeId: lastEntry.nodeId,
    currentResultId: null,
    supplementaryResultIds: [],
    variables: newVariables,
    history: newHistory,
    stepNumber: Math.max(1, state.stepNumber - 1),
  };
}

/** Check if we're at a result (terminal state). */
export function isComplete(state: TraverserState): boolean {
  return state.currentResultId !== null;
}

/** Check if we can go back. */
export function canGoBack(state: TraverserState): boolean {
  return state.history.length > 0;
}

/**
 * Estimate progress as a fraction (0–1).
 * Uses a simple heuristic: current depth / estimated max depth.
 * Estimated max depth is computed by averaging all path depths from the schema.
 */
export function estimateProgress(
  schema: RuleFlowSchema,
  state: TraverserState
): number {
  if (isComplete(state)) return 1;

  const avgDepth = estimateAverageDepth(schema);
  if (avgDepth === 0) return 0;

  return Math.min(state.history.length / avgDepth, 0.95);
}

/** Estimate average path depth via DFS sampling. */
function estimateAverageDepth(schema: RuleFlowSchema): number {
  const depths: number[] = [];

  function dfs(nodeId: string, depth: number, visited: Set<string>): void {
    if (visited.has(nodeId)) return;
    const node = schema.nodes[nodeId];
    if (!node) return;

    visited.add(nodeId);

    for (const option of node.options) {
      const targets =
        typeof option.goto === "string"
          ? [option.goto]
          : [option.goto.default, ...option.goto.if.map((b) => b.goto)];

      for (const target of targets) {
        const parsed = parseTarget(target);
        if (parsed.type === "result") {
          depths.push(depth + 1);
        } else {
          dfs(parsed.id, depth + 1, new Set(visited));
        }
      }
    }
  }

  dfs(schema.start_node, 0, new Set());

  if (depths.length === 0) return 1;
  return depths.reduce((a, b) => a + b, 0) / depths.length;
}
