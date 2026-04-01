#!/usr/bin/env bash
# health-check.sh — Detect drift across the spec-driven workflow
#
# Requires bash 4+ (uses process substitution, arrays, [[ ]]).
#
# Usage:
#   ./scripts/health-check.sh [project-dir]
#
# Runs eight checks:
#   1. Register vs. disk (do owned files exist? are any source files unowned?)
#   2. contracts.yaml vs. spec Requires tables (are pins in sync?)
#   3. contracts.yaml vs. definition versions (are pins current?)
#   4. Spec status consistency (implemented specs should have code)
#   5. Missing governed documents
#   6. Plan files missing Tests section (advisory)
#   7. Graph freshness (project-graph.yaml vs. source files)
#
# Produces a drift report. Does not fix anything.
# Exit code: 0 if healthy, 1 if drift detected.

set -euo pipefail

# Guard: fail if sourced or invoked with a non-bash shell (e.g. sh, dash)
if [ -z "${BASH_VERSION:-}" ]; then
  echo "Error: this script requires bash. Run with: bash $0" >&2
  exit 1
fi

PROJECT_DIR="${1:-$(pwd)}"
REGISTER="$PROJECT_DIR/docs/REGISTER.md"
CONTRACTS="$PROJECT_DIR/contracts.yaml"
DEFS_DIR="$PROJECT_DIR/docs/definitions"
SPECS_DIR="$PROJECT_DIR/docs/specs"

drift_found=false
check_count=0
issue_count=0

# ── Helpers ──────────────────────────────────────────────────────────

header() {
  echo ""
  echo "━━━ $1 ━━━"
  ((check_count++)) || true
}

ok() {
  echo "  ✓ $1"
}

warn() {
  echo "  ✗ $1"
  drift_found=true
  ((issue_count++)) || true
}

info() {
  echo "  · $1"
}

# ── Check 0: Missing governed documents ──────────────────────────────

header "Check 1: Governed documents exist"

[ -f "$PROJECT_DIR/SPEC-WORKFLOW.md" ] && ok "SPEC-WORKFLOW.md" || warn "SPEC-WORKFLOW.md missing"
[ -f "$PROJECT_DIR/CLAUDE.md" ] && ok "CLAUDE.md" || warn "CLAUDE.md missing"
[ -f "$PROJECT_DIR/docs/ARCHITECTURE.md" ] && ok "docs/ARCHITECTURE.md" || warn "docs/ARCHITECTURE.md missing"
[ -f "$REGISTER" ] && ok "docs/REGISTER.md" || warn "docs/REGISTER.md missing"
[ -f "$CONTRACTS" ] && ok "contracts.yaml" || warn "contracts.yaml missing"
[ -d "$DEFS_DIR" ] && ok "docs/definitions/" || warn "docs/definitions/ missing"
[ -d "$SPECS_DIR" ] && ok "docs/specs/" || warn "docs/specs/ missing"

# If register doesn't exist, we can't run most checks
if [ ! -f "$REGISTER" ]; then
  echo ""
  echo "Register not found — skipping checks 2-5."
  echo ""
  echo "Summary: $issue_count issues found across $check_count checks."
  exit 1
fi

# ── Check 1: Register owned files vs. disk ───────────────────────────

header "Check 2: Register owned files vs. disk"

# Extract owned file/directory patterns from register
# Format: | spec.md | phase | status | owns | depends |
missing_files=()
spec_owns_map=""

while IFS='|' read -r _ spec _ _ owns _; do
  spec=$(echo "$spec" | xargs)
  owns=$(echo "$owns" | xargs)
  [ -z "$spec" ] || [ -z "$owns" ] && continue

  for pattern in $(echo "$owns" | tr ',' '\n'); do
    pattern=$(echo "$pattern" | xargs)
    [ -z "$pattern" ] && continue

    # Skip ellipsis patterns like "pyproject.toml, setup.cfg, ..."
    [ "$pattern" = "..." ] && continue

    # Handle glob patterns
    if [[ "$pattern" == *"**"* ]]; then
      dir="${pattern%%\*\*}"
      dir="${dir%/}"
      if [ -d "$PROJECT_DIR/$dir" ]; then
        ok "$pattern (directory exists)"
      else
        warn "$pattern (directory missing, owned by $spec)"
      fi
    else
      if [ -e "$PROJECT_DIR/$pattern" ]; then
        ok "$pattern"
      else
        warn "$pattern (file missing, owned by $spec)"
      fi
    fi

    spec_owns_map+="$pattern:$spec"$'\n'
  done
done < <(grep -E '^\| [a-z][a-z0-9_-]+ \| Phase' "$REGISTER" 2>/dev/null || true)

# Check for unowned source files
header "Check 3: Unowned source files"

unowned_count=0
# Look for Python files in likely implementation directories
for src_dir in src "$( basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' )" tests; do
  [ ! -d "$PROJECT_DIR/$src_dir" ] && continue

  while IFS= read -r file; do
    rel_path="${file#$PROJECT_DIR/}"
    # Skip __pycache__, .pyc files
    [[ "$rel_path" == *"__pycache__"* ]] && continue
    [[ "$rel_path" == *.pyc ]] && continue

    # Check if this file is covered by any ownership pattern
    owned=false
    while IFS=: read -r pattern owner; do
      [ -z "$pattern" ] && continue
      if [[ "$pattern" == *"**"* ]]; then
        dir="${pattern%%\*\*}"
        if [[ "$rel_path" == "$dir"* ]]; then
          owned=true
          break
        fi
      elif [ "$rel_path" = "$pattern" ]; then
        owned=true
        break
      fi
    done <<< "$spec_owns_map"

    if [ "$owned" = false ]; then
      warn "Unowned: $rel_path"
      ((unowned_count++)) || true
    fi
  done < <(find "$PROJECT_DIR/$src_dir" -name '*.py' -type f 2>/dev/null)
done

[ "$unowned_count" -eq 0 ] && ok "No unowned source files found"

# ── Check 3: contracts.yaml vs. spec Requires tables ─────────────────

header "Check 4: contracts.yaml vs. spec Requires tables"

if [ ! -f "$CONTRACTS" ]; then
  warn "contracts.yaml missing — cannot check version pin sync"
else
  sync_issues=0

  # For each spec file, extract its Requires table pins and compare to contracts.yaml
  for spec_file in "$SPECS_DIR"/*.spec.md; do
    [ ! -f "$spec_file" ] && continue
    spec_name=$(basename "$spec_file" .md)

    # Extract definition@version references from the spec's Requires table
    # Look for patterns like definitions/foo.md@v1
    spec_pins=$(grep -oE 'definitions/[^@|]+@v[0-9]+' "$spec_file" 2>/dev/null || true)

    while IFS= read -r pin; do
      [ -z "$pin" ] && continue
      def_path=$(echo "$pin" | cut -d@ -f1)
      spec_version=$(echo "$pin" | cut -d@ -f2)

      # Check if contracts.yaml has this pin
      # Look for the definition path under this spec's section
      yaml_version=$(grep -A50 "^  ${spec_name%.spec}:" "$CONTRACTS" 2>/dev/null \
        | grep "$def_path" | head -1 \
        | grep -oE 'v[0-9]+' || true)

      if [ -z "$yaml_version" ]; then
        warn "$spec_name: $def_path@$spec_version in spec but missing from contracts.yaml"
        ((sync_issues++)) || true
      elif [ "$yaml_version" != "$spec_version" ]; then
        warn "$spec_name: $def_path — spec says $spec_version, contracts.yaml says $yaml_version"
        ((sync_issues++)) || true
      fi
    done <<< "$spec_pins"
  done

  [ "$sync_issues" -eq 0 ] && ok "All spec pins match contracts.yaml"
fi

# ── Check 4: contracts.yaml vs. definition current versions ──────────

header "Check 5: contracts.yaml vs. definition versions (staleness)"

if [ ! -f "$CONTRACTS" ] || [ ! -d "$DEFS_DIR" ]; then
  info "Skipped — contracts.yaml or definitions/ missing"
else
  stale_count=0

  # Extract all definition references and pinned versions from contracts.yaml
  pins=$(grep -E '^\s+definitions/' "$CONTRACTS" 2>/dev/null | sed 's/#.*//' || true)

  while IFS=: read -r def_path pinned_version; do
    [ -z "$def_path" ] && continue
    def_path=$(echo "$def_path" | xargs)
    pinned_version=$(echo "$pinned_version" | xargs)
    [ -z "$pinned_version" ] && continue

    def_file="$PROJECT_DIR/docs/$def_path"
    if [ ! -f "$def_file" ]; then
      warn "Definition not found: $def_path (pinned at $pinned_version in contracts.yaml)"
      ((stale_count++)) || true
      continue
    fi

    # Extract current version from definition file
    current_version=$(grep -A1 '^## Version' "$def_file" 2>/dev/null \
      | grep -oE 'v[0-9]+' | head -1 || true)

    if [ -z "$current_version" ]; then
      warn "$def_path: no version found in file (pinned at $pinned_version)"
      ((stale_count++)) || true
    elif [ "$current_version" != "$pinned_version" ]; then
      warn "$def_path: pinned=$pinned_version, current=$current_version — STALE"
      ((stale_count++)) || true
    else
      ok "$def_path: $current_version (current)"
    fi
  done <<< "$pins"

  [ "$stale_count" -eq 0 ] && [ -n "$pins" ] && ok "All version pins are current"
fi

# ── Check 5: Spec status consistency ─────────────────────────────────

header "Check 6: Spec status consistency"

while IFS='|' read -r _ spec _ status owns _; do
  spec=$(echo "$spec" | xargs)
  status=$(echo "$status" | xargs)
  owns=$(echo "$owns" | xargs)
  [ -z "$spec" ] && continue

  spec_file="$SPECS_DIR/${spec}.spec.md"

  case "$status" in
    implemented)
      # Implemented specs should have owned files that exist
      if [ -z "$owns" ] || [ "$owns" = "(none)" ]; then
        warn "$spec: status=implemented but owns no files"
      fi
      ;;
    draft)
      # Draft specs probably shouldn't have implementation files yet
      # (warning, not error — draft mode allows continuing)
      ;;
    revision-needed)
      warn "$spec: status=revision-needed — requires attention"
      ;;
  esac

  # Check that the spec file itself exists
  if [ ! -f "$spec_file" ]; then
    warn "$spec: listed in register but file does not exist"
  fi
done < <(grep -E '^\| [a-z][a-z0-9_-]+ \| Phase' "$REGISTER" 2>/dev/null || true)

ok "Status consistency check complete"

# ── Check 6: Plan files missing Tests section ────────────────────────

header "Check 7: Plan files — Tests section"

PLANS_DIR="$PROJECT_DIR/docs/plans"
if [ ! -d "$PLANS_DIR" ]; then
  info "Skipped — docs/plans/ not found"
else
  plans_checked=0
  plans_warned=0

  for plan_file in "$PLANS_DIR"/*.md; do
    [ ! -f "$plan_file" ] && continue
    plan_name=$(basename "$plan_file")

    # Skip templates
    [[ "$plan_name" == "TEMPLATE.md" ]] && continue
    [[ "$plan_name" == *template* ]] && continue

    plan_content=$(cat "$plan_file")

    # Determine if the plan is test-prudent:
    # Contains source file extensions or implementation keywords
    is_test_prudent=false

    if echo "$plan_content" | grep -qE '\.(ts|js|sh|py|go|rs|rb|java|tsx|jsx)\b'; then
      is_test_prudent=true
    elif echo "$plan_content" | grep -qiE 'implement|create function|add endpoint|write code|add method|new file|modify|refactor'; then
      is_test_prudent=true
    fi

    # If only docs/config references, skip
    if [ "$is_test_prudent" = false ]; then
      continue
    fi

    ((plans_checked++)) || true

    # Check for a ## Tests or ## Test heading
    if echo "$plan_content" | grep -qE '^## Tests?(\s|$)'; then
      ok "$plan_name has a Tests section"
    else
      info "$plan_name: test-prudent plan without a ## Tests section"
      ((plans_warned++)) || true
    fi
  done

  [ "$plans_checked" -eq 0 ] && info "No test-prudent plans found"
  [ "$plans_checked" -gt 0 ] && [ "$plans_warned" -eq 0 ] && ok "All test-prudent plans have a Tests section"
fi

# ── Check 7: Graph freshness ────────────────────────────────────────

header "Check 8: project-graph.yaml freshness"

GRAPH_FILE="$PROJECT_DIR/project-graph.yaml"

if [ ! -f "$GRAPH_FILE" ]; then
  info "project-graph.yaml not found — run: bash scripts/generate-graph.sh"
else
  graph_mtime=$(stat -f %m "$GRAPH_FILE" 2>/dev/null || stat -c %Y "$GRAPH_FILE" 2>/dev/null || echo 0)
  stale=false

  # Check if any source is newer than the graph
  while IFS= read -r source_file; do
    [ -f "$source_file" ] || continue
    source_mtime=$(stat -f %m "$source_file" 2>/dev/null || stat -c %Y "$source_file" 2>/dev/null || echo 0)
    if [ "$source_mtime" -gt "$graph_mtime" ]; then
      stale=true
      warn "project-graph.yaml is older than $(basename "$source_file") — regenerate with: bash scripts/generate-graph.sh"
      break
    fi
  done < <(
    find "$PROJECT_DIR/docs/specs" -name "*.spec.md" -type f 2>/dev/null
    find "$PROJECT_DIR/.claude/skills" -name "SKILL.md" -type f 2>/dev/null
    echo "$PROJECT_DIR/.claude/settings.json"
    echo "$PROJECT_DIR/docs/REGISTER.md"
    echo "$PROJECT_DIR/contracts.yaml"
  )

  if [ "$stale" = false ]; then
    ok "project-graph.yaml is up to date"
  fi
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$drift_found" = true ]; then
  echo "DRIFT DETECTED: $issue_count issues found across $check_count checks."
  echo ""
  echo "Review the issues above and resolve before implementing."
  echo "Do not auto-fix — the architecture owner approves changes."
  exit 1
else
  echo "HEALTHY: No drift detected across $check_count checks."
  exit 0
fi
