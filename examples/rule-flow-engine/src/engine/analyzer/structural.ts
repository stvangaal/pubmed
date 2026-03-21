// Structural checks (errors) — schema is invalid if any of these fail.
// Checks: orphan nodes, dangling edges, missing terminals,
//         duplicate IDs, invalid variable references.

import type { RuleFlowSchema, Goto } from "../types";
import type { Finding } from "./types";

/** Extract all goto target strings from a Goto value (simple or conditional). */
function extractGotoTargets(goto: Goto): string[] {
  if (typeof goto === "string") return [goto];
  const targets = [goto.default];
  for (const branch of goto.if) {
    targets.push(branch.goto);
  }
  return targets;
}

/** Extract all goto targets from all options across all nodes. */
function allEdgeTargets(schema: RuleFlowSchema): string[] {
  const targets: string[] = [];
  for (const node of Object.values(schema.nodes)) {
    for (const option of node.options) {
      targets.push(...extractGotoTargets(option.goto));
      if (option.supplementary) {
        targets.push(...option.supplementary);
      }
    }
  }
  return targets;
}

/** Resolve a goto target to either a node ID or result ID. */
function parseTarget(target: string): { type: "node" | "result"; id: string } {
  if (target.startsWith("result:")) {
    return { type: "result", id: target.slice(7) };
  }
  return { type: "node", id: target };
}

/** BFS from start_node to find all reachable node IDs. */
function reachableNodes(schema: RuleFlowSchema): Set<string> {
  const visited = new Set<string>();
  const queue = [schema.start_node];

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (visited.has(current)) continue;
    visited.add(current);

    const node = schema.nodes[current];
    if (!node) continue;

    for (const option of node.options) {
      for (const target of extractGotoTargets(option.goto)) {
        const parsed = parseTarget(target);
        if (parsed.type === "node" && !visited.has(parsed.id)) {
          queue.push(parsed.id);
        }
      }
    }
  }

  return visited;
}

/** Check: node IDs and result IDs must not overlap. */
function checkDuplicateIds(schema: RuleFlowSchema): Finding[] {
  const findings: Finding[] = [];
  const nodeIds = new Set(Object.keys(schema.nodes));
  const resultIds = new Set(Object.keys(schema.results));

  for (const id of nodeIds) {
    if (resultIds.has(id)) {
      findings.push({
        type: "duplicate_id",
        description: `ID "${id}" is used as both a node and a result.`,
        suggestion: "Rename one of them to be unique.",
      });
    }
  }

  return findings;
}

/** Check: start_node must exist in nodes. */
function checkStartNode(schema: RuleFlowSchema): Finding[] {
  if (!schema.nodes[schema.start_node]) {
    return [
      {
        type: "invalid_start_node",
        description: `start_node "${schema.start_node}" does not exist in nodes.`,
        suggestion: `Set start_node to one of: ${Object.keys(schema.nodes).join(", ")}`,
      },
    ];
  }
  return [];
}

/** Check: nodes not reachable from start_node. */
function checkOrphanNodes(schema: RuleFlowSchema): Finding[] {
  const reachable = reachableNodes(schema);
  const findings: Finding[] = [];

  for (const nodeId of Object.keys(schema.nodes)) {
    if (!reachable.has(nodeId)) {
      findings.push({
        type: "orphan_node",
        description: `Node "${nodeId}" is not reachable from start_node "${schema.start_node}".`,
        suggestion: "Remove it or add an edge leading to it.",
      });
    }
  }

  return findings;
}

/** Check: goto targets referencing non-existent nodes or results. */
function checkDanglingEdges(schema: RuleFlowSchema): Finding[] {
  const findings: Finding[] = [];
  const targets = allEdgeTargets(schema);

  for (const target of targets) {
    const parsed = parseTarget(target);
    if (parsed.type === "node" && !schema.nodes[parsed.id]) {
      findings.push({
        type: "dangling_edge",
        description: `Goto references non-existent node "${parsed.id}".`,
        suggestion: "Fix the goto target or create the missing node.",
      });
    } else if (parsed.type === "result" && !schema.results[parsed.id]) {
      findings.push({
        type: "dangling_edge",
        description: `Goto references non-existent result "${parsed.id}".`,
        suggestion: "Fix the goto target or create the missing result.",
      });
    }
  }

  return findings;
}

/** Check: every path from start_node must reach a result: terminal. */
function checkMissingTerminals(schema: RuleFlowSchema): Finding[] {
  const findings: Finding[] = [];
  // DFS to find nodes where all options lead to results or other valid nodes
  // A node is "stuck" if any option leads to a node that doesn't exist
  // (caught by dangling edges) or if there's a cycle with no exit.
  // We detect cycles: if we revisit a node on the current path, that's a
  // path that never terminates.

  function dfs(nodeId: string, path: Set<string>): boolean {
    const node = schema.nodes[nodeId];
    if (!node) return false; // dangling — caught elsewhere

    if (path.has(nodeId)) {
      // Cycle detected — this path never reaches a terminal
      return false;
    }

    path.add(nodeId);
    let allTerminate = true;

    for (const option of node.options) {
      for (const target of extractGotoTargets(option.goto)) {
        const parsed = parseTarget(target);
        if (parsed.type === "result") {
          continue; // This branch terminates
        }
        if (!dfs(parsed.id, new Set(path))) {
          allTerminate = false;
        }
      }
    }

    return allTerminate;
  }

  if (schema.nodes[schema.start_node]) {
    if (!dfs(schema.start_node, new Set())) {
      findings.push({
        type: "missing_terminal",
        description:
          "At least one path from start_node does not reach a result terminal (possible cycle or dead end).",
        suggestion:
          "Ensure every option chain from start_node eventually reaches a result: target.",
      });
    }
  }

  return findings;
}

/** Check: sets references variables not in schema.variables, or invalid enum values. */
function checkInvalidVariableRefs(schema: RuleFlowSchema): Finding[] {
  const findings: Finding[] = [];

  for (const [nodeId, node] of Object.entries(schema.nodes)) {
    for (const option of node.options) {
      for (const [varName, value] of Object.entries(option.sets)) {
        const varDef = schema.variables[varName];
        if (!varDef) {
          findings.push({
            type: "invalid_variable_ref",
            description: `Node "${nodeId}" option "${option.label}" sets undefined variable "${varName}".`,
            suggestion: `Define "${varName}" in the variables object, or fix the sets field.`,
          });
          continue;
        }

        if (varDef.type === "enum") {
          if (typeof value !== "string" || !varDef.values.includes(value)) {
            findings.push({
              type: "invalid_variable_value",
              description: `Node "${nodeId}" option "${option.label}" sets "${varName}" to "${value}", which is not in [${varDef.values.join(", ")}].`,
              suggestion: `Use one of: ${varDef.values.join(", ")}`,
            });
          }
        } else if (varDef.type === "boolean") {
          if (typeof value !== "boolean") {
            findings.push({
              type: "invalid_variable_value",
              description: `Node "${nodeId}" option "${option.label}" sets boolean variable "${varName}" to non-boolean value "${value}".`,
              suggestion: "Use true or false.",
            });
          }
        }
      }
    }
  }

  return findings;
}

/** Run all structural checks. Returns errors array. */
export function runStructuralChecks(schema: RuleFlowSchema): Finding[] {
  return [
    ...checkStartNode(schema),
    ...checkDuplicateIds(schema),
    ...checkOrphanNodes(schema),
    ...checkDanglingEdges(schema),
    ...checkMissingTerminals(schema),
    ...checkInvalidVariableRefs(schema),
  ];
}

// Re-export helpers needed by coverage analysis
export { extractGotoTargets, parseTarget, reachableNodes };
