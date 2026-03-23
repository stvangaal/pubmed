#!/usr/bin/env bash
# SessionStart hook: produce a compact project state summary for Claude's context.
# Reads REGISTER.md, contracts.yaml, and definition files to surface:
# - Which specs exist and their statuses
# - Any stale version pins (contracts.yaml vs definition files)
# - What's next in the dependency resolution order
#
# Output goes to Claude's context as additionalContext.
# Must be fast — runs on every session start.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
REGISTER="$PROJECT_DIR/docs/REGISTER.md"
CONTRACTS="$PROJECT_DIR/contracts.yaml"
DEFS_DIR="$PROJECT_DIR/docs/definitions"
CONFIG="$PROJECT_DIR/.arboretum.yml"

# Detect current layer (default: 0)
LAYER=$(sed -n 's/^layer:[[:space:]]*\([0-9]\).*/\1/p' "$CONFIG" 2>/dev/null || true)
LAYER="${LAYER:-0}"

output=""

# ── Check if governed documents exist ────────────────────────────────

missing=()
[ ! -f "$PROJECT_DIR/docs/ARCHITECTURE.md" ] && missing+=("ARCHITECTURE.md")
[ ! -f "$REGISTER" ] && missing+=("REGISTER.md")
[ ! -f "$CONTRACTS" ] && missing+=("contracts.yaml")
[ ! -d "$DEFS_DIR" ] && missing+=("docs/definitions/")

if [ ${#missing[@]} -gt 0 ]; then
  output+="[Spec Workflow] Missing governed documents: ${missing[*]}."
  output+=$'\n'"  → Why: The document chain must exist top-down before specs can be implemented."
  output+=$'\n'"    Create them in order: ARCHITECTURE.md → definitions/ → specs → REGISTER.md → contracts.yaml. See SPEC-WORKFLOW.md §7."
fi

# ── Parse register for spec statuses ─────────────────────────────────

if [ -f "$REGISTER" ]; then
  # Extract spec index table rows (lines matching "| something.spec.md |")
  spec_lines=$(grep -E '^\|.*\.spec\.md' "$REGISTER" 2>/dev/null || true)

  if [ -n "$spec_lines" ]; then
    draft_count=0
    ready_count=0
    in_progress_count=0
    implemented_count=0
    revision_count=0
    in_progress_specs=""
    revision_specs=""
    ready_specs=""

    while IFS='|' read -r _ spec phase status _ _; do
      spec=$(echo "$spec" | xargs)
      status=$(echo "$status" | xargs)
      case "$status" in
        draft) ((draft_count += 1)) || true ;;
        ready)
          ((ready_count += 1)) || true
          ready_specs+="$spec, "
          ;;
        in-progress)
          ((in_progress_count += 1)) || true
          in_progress_specs+="$spec, "
          ;;
        implemented) ((implemented_count += 1)) || true ;;
        revision-needed)
          ((revision_count += 1)) || true
          revision_specs+="$spec, "
          ;;
      esac
    done <<< "$spec_lines"

    output+=$'\n'"[Spec Status] "
    output+="draft:$draft_count ready:$ready_count in-progress:$in_progress_count "
    output+="implemented:$implemented_count revision-needed:$revision_count"

    if [ -n "$in_progress_specs" ]; then
      output+=$'\n'"[In Progress] ${in_progress_specs%, }"
    fi
    if [ -n "$revision_specs" ]; then
      output+=$'\n'"[Needs Revision] ${revision_specs%, }"
    fi
    if [ -n "$ready_specs" ]; then
      output+=$'\n'"[Ready to Implement] ${ready_specs%, }"
    fi
  fi
fi

# ── Check register staleness ─────────────────────────────────────────

if [ -f "$REGISTER" ] && [ -d "$PROJECT_DIR/docs/specs" ]; then
  register_stale=false
  for spec_file in "$PROJECT_DIR"/docs/specs/*.spec.md; do
    [ -f "$spec_file" ] || continue
    if [ "$spec_file" -nt "$REGISTER" ]; then
      register_stale=true
      break
    fi
  done
  if [ "$register_stale" = true ]; then
    output+=$'\n'"[Register] REGISTER.md may be stale — spec files are newer than the register."
    output+=$'\n'"  → Why: Stale register data causes incorrect staleness checks and ownership lookups."
    output+=$'\n'"    Run /generate-register to resync. See SPEC-WORKFLOW.md §4."
  fi
fi

# ── Check version pin staleness ──────────────────────────────────────

if [ -f "$CONTRACTS" ] && [ -d "$DEFS_DIR" ]; then
  stale=""

  # Extract definition paths and pinned versions from contracts.yaml
  # Format: definitions/foo.md: v1
  pins=$(grep -E '^\s+definitions/' "$CONTRACTS" 2>/dev/null | sed 's/#.*//' || true)

  while IFS=: read -r def_path pinned_version; do
    [ -z "$def_path" ] && continue
    def_path=$(echo "$def_path" | xargs)
    pinned_version=$(echo "$pinned_version" | xargs)
    [ -z "$pinned_version" ] && continue

    def_file="$PROJECT_DIR/docs/$def_path"
    if [ -f "$def_file" ]; then
      # Extract current version from definition file's ## Version section
      current_version=$(grep -A1 '^## Version' "$def_file" 2>/dev/null \
        | grep -oE 'v[0-9]+' | head -1 || true)

      if [ -n "$current_version" ] && [ "$current_version" != "$pinned_version" ]; then
        stale+="  $def_path: pinned=$pinned_version current=$current_version"$'\n'
      fi
    fi
  done <<< "$pins"

  if [ -n "$stale" ]; then
    output+=$'\n'"[Stale Version Pins] Definition versions have drifted from contracts.yaml:"$'\n'"$stale"
    output+="  → Why: Implementing against stale pins risks silent drift between code and contracts."
    output+=$'\n'"    Run /health-check or /sync-contracts to reconcile. See SPEC-WORKFLOW.md §7."
  fi
fi

# ── Layer upgrade suggestions ────────────────────────────────────────

if [ "$LAYER" -lt 1 ]; then
  # Count specs to suggest Layer 1
  spec_count=0
  if [ -d "$PROJECT_DIR/docs/specs" ]; then
    spec_count=$(find "$PROJECT_DIR/docs/specs" -name "*.spec.md" 2>/dev/null | wc -l | tr -d ' ')
  fi
  if [ "$spec_count" -ge 3 ]; then
    output+=$'\n'"[Layer Suggestion] $spec_count specs detected at Layer 0."
    output+=$'\n'"  → Why: Layer 1 adds ownership context on every edit and auto-register updates — useful once you have 3+ specs."
    output+=$'\n'"    Set layer: 1 in .arboretum.yml to activate."
  fi
fi

if [ "$LAYER" -lt 2 ]; then
  # Check for multi-author or CI to suggest Layer 2
  suggest_l2=false
  if [ -d "$PROJECT_DIR/.github/workflows" ]; then
    ci_count=$(find "$PROJECT_DIR/.github/workflows" -name "*.yml" -o -name "*.yaml" 2>/dev/null | wc -l | tr -d ' ')
    [ "$ci_count" -gt 0 ] && suggest_l2=true
  fi
  if [ "$suggest_l2" = false ]; then
    author_count=$(git -C "$PROJECT_DIR" log --format='%ae' 2>/dev/null | sort -u | wc -l | tr -d ' ')
    [ "$author_count" -ge 2 ] && suggest_l2=true
  fi
  if [ "$suggest_l2" = true ]; then
    output+=$'\n'"[Layer Suggestion] CI workflows or multiple git authors detected at Layer $LAYER."
    output+=$'\n'"  → Why: Layer 2 adds version-pin enforcement, branch protection, and post-commit drift detection — valuable for multi-author projects."
    output+=$'\n'"    Set layer: 2 in .arboretum.yml to activate."
  fi
fi

# ── Active skills by layer ───────────────────────────────────────────

SKILLS_DIR="$PROJECT_DIR/.claude/skills"
if [ -d "$SKILLS_DIR" ]; then
  # Build skill lists per layer
  layer0_skills=""
  layer1_skills=""
  layer2_skills=""

  for skill_dir in "$SKILLS_DIR"/*/; do
    [ ! -d "$skill_dir" ] && continue
    skill_file="$skill_dir/SKILL.md"
    [ ! -f "$skill_file" ] && continue
    skill_name="$(basename "$skill_dir")"

    # Extract layer from YAML frontmatter (between --- markers)
    skill_layer=$(sed -n '/^---$/,/^---$/{ s/^layer:[[:space:]]*\([0-9]\).*/\1/p; }' "$skill_file")
    [ -z "$skill_layer" ] && continue

    case "$skill_layer" in
      0) layer0_skills+="/$skill_name, " ;;
      1) layer1_skills+="/$skill_name, " ;;
      2) layer2_skills+="/$skill_name, " ;;
    esac
  done

  active_output=""
  if [ -n "$layer0_skills" ] && [ "$LAYER" -ge 0 ]; then
    active_output+="Layer 0: ${layer0_skills%, }"
  fi
  if [ -n "$layer1_skills" ] && [ "$LAYER" -ge 1 ]; then
    active_output+="; Layer 1: ${layer1_skills%, }"
  fi
  if [ -n "$layer2_skills" ] && [ "$LAYER" -ge 2 ]; then
    active_output+="; Layer 2: ${layer2_skills%, }"
  fi

  if [ -n "$active_output" ]; then
    output+=$'\n'"[Active Skills] $active_output"
  fi
fi

# ── Output ───────────────────────────────────────────────────────────

if [ -n "$output" ]; then
  echo "$output"
fi

exit 0
