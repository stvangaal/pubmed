#!/usr/bin/env bash
# PostToolUse hook for Bash: after a git commit, check if the register needs updating.
# Inspects the committed files and cross-references against REGISTER.md to flag:
# - New files not listed in any spec's ownership
# - Changes to definition files (version bump needed?)
# - Changes to spec files (register status update needed?)
# - Changes to contracts.yaml without corresponding spec updates
#
# Non-blocking: outputs context only.

set -euo pipefail

INPUT=$(cat)

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
REGISTER="$PROJECT_DIR/docs/REGISTER.md"

# Layer 2+ only — skip for Layer 0-1 projects
LAYER=$(sed -n 's/^layer:[[:space:]]*\([0-9]\).*/\1/p' "$PROJECT_DIR/.arboretum.yml" 2>/dev/null)
LAYER="${LAYER:-0}"
[ "$LAYER" -lt 2 ] && exit 0

# Only fire on git commit commands
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
if ! echo "$COMMAND" | grep -qE 'git\s+commit'; then
  exit 0
fi

# Check if the commit actually succeeded (tool output should not be an error)
TOOL_OUTPUT=$(echo "$INPUT" | jq -r '.tool_output // empty')
if echo "$TOOL_OUTPUT" | grep -qiE '(error|fatal|nothing to commit)'; then
  exit 0
fi

[ ! -f "$REGISTER" ] && exit 0

# ── Get list of files changed in the last commit ────────────────────

cd "$PROJECT_DIR"
committed_files=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null || true)
[ -z "$committed_files" ] && exit 0

# ── Categorize committed files ───────────────────────────────────────

new_impl_files=""
definition_changes=""
spec_changes=""
contracts_changed=false
register_changed=false

while IFS= read -r file; do
  case "$file" in
    docs/definitions/*.md)
      definition_changes+="  $file"$'\n'
      ;;
    docs/specs/*.spec.md)
      spec_changes+="  $file"$'\n'
      ;;
    contracts.yaml)
      contracts_changed=true
      ;;
    docs/REGISTER.md)
      register_changed=true
      ;;
    src/*|tests/*)
      # Check if this file is listed in the register
      if ! grep -qF "$file" "$REGISTER" 2>/dev/null; then
        # Also check if a parent directory glob covers it
        dir=$(dirname "$file")
        if ! grep -qE "${dir}/?\*\*" "$REGISTER" 2>/dev/null; then
          new_impl_files+="  $file"$'\n'
        fi
      fi
      ;;
  esac
done <<< "$committed_files"

# ── Build advisory output ────────────────────────────────────────────

context=""

# Helper: format a file list inline (comma-separated) if <3 files, multi-line otherwise.
format_file_list() {
  local files="$1"
  local count
  count=$(echo "$files" | grep -c '[^[:space:]]' || true)
  if [ "$count" -lt 3 ]; then
    echo "$files" | xargs | tr ' ' ',' | sed 's/,/, /g'
  else
    echo "$files"
  fi
}

if [ -n "$new_impl_files" ]; then
  local_list=$(format_file_list "$new_impl_files")
  context+="[Unregistered Files] New implementation files not in register: $local_list"$'\n'
  context+="  → Why: Unregistered files have no spec owner and risk becoming orphan code."$'\n'
  context+="    Assign them to a spec in REGISTER.md. See SPEC-WORKFLOW.md §4."$'\n'
fi

if [ -n "$definition_changes" ]; then
  local_list=$(format_file_list "$definition_changes")
  context+="[Definition Changed] These definitions were modified: $local_list"$'\n'
  context+="  → Why: Definition changes may be breaking — consuming specs must review and re-pin."$'\n'
  context+="    Bump the version, update the changelog, and update pins in contracts.yaml. See SPEC-WORKFLOW.md §1."$'\n'
fi

if [ -n "$spec_changes" ]; then
  local_list=$(format_file_list "$spec_changes")
  context+="[Spec Changed] These specs were modified: $local_list"$'\n'
  context+="  → Why: Spec changes may affect status, ownership, or dependencies in the register."$'\n'
  context+="    Verify REGISTER.md is still accurate or run /generate-register. See SPEC-WORKFLOW.md §4."$'\n'
fi

if [ "$contracts_changed" = true ] && [ -n "$spec_changes" ] && [ "$register_changed" = false ]; then
  context+="[Sync Check] contracts.yaml was updated but REGISTER.md was not."$'\n'
  context+="  → Why: These must stay in sync — mismatches cause false positives in staleness checks."$'\n'
  context+="    Verify the register or run /generate-register. See SPEC-WORKFLOW.md §1."$'\n'
fi

if [ -n "$definition_changes" ] && [ "$contracts_changed" = false ]; then
  context+="[Sync Check] Definition files changed but contracts.yaml was not updated."$'\n'
  context+="  → Why: contracts.yaml must reflect current definition versions — stale pins cause false test results."$'\n'
  context+="    Run /sync-contracts to reconcile. See SPEC-WORKFLOW.md §1."$'\n'
fi

if [ -n "$context" ]; then
  echo "$context"
fi

exit 0
