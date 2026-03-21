// Schema → Mermaid flowchart string generator.
// Pure function: (schema, options?) → string
// See SPEC.md §5 for generation rules.

import type { RuleFlowSchema, Goto } from "./types";

export interface MermaidOptions {
  /** Start from a specific node instead of schema.start_node */
  root?: string;
  /** Maximum depth from root (nodes beyond this become "..." placeholders) */
  depth?: number;
}

/** Truncate text to maxLen characters, appending "..." if truncated. */
function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen - 3) + "...";
}

/**
 * Escape characters that break Mermaid syntax inside node labels and edge labels.
 * Mermaid uses quotes for labels, so we need to handle special chars.
 */
function escapeLabel(text: string): string {
  return text
    .replace(/"/g, "#quot;")
    .replace(/\(/g, "#40;")
    .replace(/\)/g, "#41;")
    .replace(/\[/g, "#91;")
    .replace(/\]/g, "#93;")
    .replace(/\{/g, "#123;")
    .replace(/\}/g, "#125;");
}

/** Parse a goto target into node or result reference. */
function parseTarget(target: string): { type: "node" | "result"; id: string } {
  if (target.startsWith("result:")) {
    return { type: "result", id: target.slice(7) };
  }
  return { type: "node", id: target };
}

/** Build the edge label, including condition info for conditional gotos. */
function buildEdgeLabels(
  goto: Goto,
  optionLabel: string
): Array<{ target: string; label: string }> {
  const truncatedLabel = truncate(optionLabel, 40);

  if (typeof goto === "string") {
    return [{ target: goto, label: truncatedLabel }];
  }

  // Conditional goto: label the default edge with the option label,
  // and each conditional branch with "option label [condition]"
  const edges: Array<{ target: string; label: string }> = [];

  for (const branch of goto.if) {
    const condStr = Object.entries(branch.condition)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    edges.push({
      target: branch.goto,
      label: truncate(`${optionLabel} [${condStr}]`, 40),
    });
  }

  edges.push({ target: goto.default, label: truncatedLabel });
  return edges;
}

/**
 * Generate a Mermaid flowchart TD string from a RuleFlow schema.
 */
export function generateMermaid(
  schema: RuleFlowSchema,
  options: MermaidOptions = {}
): string {
  const rootNode = options.root ?? schema.start_node;
  const maxDepth = options.depth ?? Infinity;

  // BFS to collect reachable nodes within depth limit
  const visitedNodes = new Set<string>();
  const visitedResults = new Set<string>();
  const edges: string[] = [];
  const depthLimited = new Set<string>(); // nodes beyond depth limit

  interface QueueItem {
    nodeId: string;
    currentDepth: number;
  }

  const queue: QueueItem[] = [{ nodeId: rootNode, currentDepth: 0 }];

  while (queue.length > 0) {
    const { nodeId, currentDepth } = queue.shift()!;

    if (visitedNodes.has(nodeId)) continue;
    const node = schema.nodes[nodeId];
    if (!node) continue;

    visitedNodes.add(nodeId);

    for (const option of node.options) {
      const edgeLabels = buildEdgeLabels(option.goto, option.label);

      for (const { target, label } of edgeLabels) {
        const parsed = parseTarget(target);
        const escapedLabel = escapeLabel(label);

        if (parsed.type === "result") {
          // Always show results (they're terminals)
          visitedResults.add(parsed.id);
          edges.push(
            `  ${nodeId} -->|"${escapedLabel}"| result_${parsed.id}`
          );
        } else if (currentDepth + 1 >= maxDepth) {
          // Beyond depth limit — show placeholder
          const placeholderId = `placeholder_${parsed.id}`;
          depthLimited.add(placeholderId);
          edges.push(
            `  ${nodeId} -->|"${escapedLabel}"| ${placeholderId}`
          );
        } else {
          edges.push(
            `  ${nodeId} -->|"${escapedLabel}"| ${parsed.id}`
          );
          if (!visitedNodes.has(parsed.id)) {
            queue.push({
              nodeId: parsed.id,
              currentDepth: currentDepth + 1,
            });
          }
        }
      }

      // Supplementary edges (option → supplementary result)
      if (option.supplementary) {
        for (const supp of option.supplementary) {
          const parsed = parseTarget(supp);
          if (parsed.type === "result") {
            visitedResults.add(parsed.id);
          }
        }
      }
    }
  }

  // Build the Mermaid string
  const lines: string[] = ["flowchart TD"];

  // Node definitions (rhombus shape for questions)
  for (const nodeId of visitedNodes) {
    const node = schema.nodes[nodeId];
    if (!node) continue;
    const label = escapeLabel(truncate(node.question, 60));
    lines.push(`  ${nodeId}{"${label}"}`);
  }

  // Result definitions (rounded rectangle)
  for (const resultId of visitedResults) {
    const result = schema.results[resultId];
    if (!result) continue;
    const label = escapeLabel(truncate(result.title, 60));
    lines.push(`  result_${resultId}(["${label}"])`);
  }

  // Depth-limited placeholders
  for (const placeholderId of depthLimited) {
    const originalId = placeholderId.replace("placeholder_", "");
    const node = schema.nodes[originalId];
    const label = node
      ? escapeLabel(truncate(node.question, 40)) + " ..."
      : `${originalId} ...`;
    lines.push(`  ${placeholderId}["${label}"]`);
  }

  // Blank line before edges
  lines.push("");

  // Edges
  lines.push(...edges);

  // Style directives for result nodes by category
  const categoryColors = schema.display?.category_colors ?? {};
  const styledCategories = new Set<string>();

  for (const resultId of visitedResults) {
    const result = schema.results[resultId];
    if (!result) continue;
    const color = categoryColors[result.category];
    if (color && !styledCategories.has(result.category)) {
      // Collect all result nodes of this category
      const nodesInCategory = [...visitedResults].filter(
        (rid) => schema.results[rid]?.category === result.category
      );
      if (nodesInCategory.length > 0) {
        const nodeList = nodesInCategory
          .map((rid) => `result_${rid}`)
          .join(",");
        lines.push(`  style ${nodeList} fill:${color}1a,stroke:${color},color:#1a1a1a`);
        styledCategories.add(result.category);
      }
    }
  }

  return lines.join("\n") + "\n";
}
