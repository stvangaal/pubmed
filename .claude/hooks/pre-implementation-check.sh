#!/usr/bin/env bash
# PreToolUse hook for Edit/Write: staleness check before modifying implementation files.
# When Claude edits a file under src/ or tests/, this hook:
# 1. Looks up which spec owns the file in REGISTER.md
# 2. Checks that spec's definition pins against current versions
# 3. Adds context about ownership and staleness
#
# Skips non-implementation files (docs, config, etc.) for speed.
# Non-blocking: outputs additionalContext, never exits 2.

set -euo pipefail

INPUT=$(cat)

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
REGISTER="$PROJECT_DIR/docs/REGISTER.md"
CONTRACTS="$PROJECT_DIR/contracts.yaml"

# Layer 1+ only — skip for Layer 0 projects
LAYER=$(sed -n 's/^layer:[[:space:]]*\([0-9]\).*/\1/p' "$PROJECT_DIR/.arboretum.yml" 2>/dev/null)
LAYER="${LAYER:-0}"
[ "$LAYER" -lt 1 ] && exit 0

# Extract the file being edited
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE_PATH" ] && exit 0

# Make path relative to project dir
REL_PATH="${FILE_PATH#$PROJECT_DIR/}"

# Only check implementation files (src/ and tests/)
# NOTE: Update the pattern below to match your project's source directory
case "$REL_PATH" in
  src/*|tests/*) ;;
  *) exit 0 ;;
esac

# Need register to look up ownership
[ ! -f "$REGISTER" ] && exit 0

# ── Find owning spec ─────────────────────────────────────────────────

# Look for the file (or its parent directory pattern) in the register's Spec Index
# Register format: | spec.md | phase | status | owns | depends |
owning_spec=""
spec_status=""

while IFS='|' read -r _ spec _ status owns _; do
  spec=$(echo "$spec" | xargs)
  status=$(echo "$status" | xargs)
  owns=$(echo "$owns" | xargs)
  [ -z "$spec" ] && continue

  # Check if our file matches any owned path or glob pattern
  for pattern in $(echo "$owns" | tr ',' '\n'); do
    pattern=$(echo "$pattern" | xargs)
    [ -z "$pattern" ] && continue

    # Handle directory glob patterns (e.g., src/module/**)
    dir_pattern="${pattern%%\*\*}"
    if [ "$dir_pattern" != "$pattern" ]; then
      # It's a glob pattern — check if file starts with the directory
      if [[ "$REL_PATH" == "$dir_pattern"* ]]; then
        owning_spec="$spec"
        spec_status="$status"
        break 2
      fi
    else
      # Exact file match
      if [ "$REL_PATH" = "$pattern" ]; then
        owning_spec="$spec"
        spec_status="$status"
        break 2
      fi
    fi
  done
done < <(grep -E '^\| [a-z]' "$REGISTER" 2>/dev/null || true)

# ── Build context output ─────────────────────────────────────────────

context=""

if [ -n "$owning_spec" ]; then
  if [ "$spec_status" = "in-progress" ]; then
    context="[Spec Ownership] $REL_PATH is owned by $owning_spec (status: $spec_status)."
  else
    context="[Spec Ownership] $REL_PATH is owned by $owning_spec (status: $spec_status)."
    context+=$'\n'"  → Why: Edits should align with spec status — this spec is not in-progress."
    context+=$'\n'"    Confirm the spec approves this change before proceeding. See SPEC-WORKFLOW.md §8."
  fi

  # Check for staleness if spec is in-progress or implemented
  if [ -f "$CONTRACTS" ] && [[ "$spec_status" =~ ^(in-progress|implemented)$ ]]; then
    spec_key="${owning_spec%.md}"
    spec_key="${spec_key%.spec}"

    # Extract this spec's pins from contracts.yaml
    stale_pins=""
    in_spec_section=false

    while IFS= read -r line; do
      if echo "$line" | grep -qE "^  ${spec_key}"; then
        in_spec_section=true
        continue
      elif echo "$line" | grep -qE '^  [a-z]' && [ "$in_spec_section" = true ]; then
        break
      fi

      if [ "$in_spec_section" = true ]; then
        def_pin=$(echo "$line" | grep -oE 'definitions/[^:]+:\s*v[0-9]+' || true)
        if [ -n "$def_pin" ]; then
          def_path=$(echo "$def_pin" | cut -d: -f1 | xargs)
          pinned=$(echo "$def_pin" | cut -d: -f2 | xargs)
          def_file="$PROJECT_DIR/docs/$def_path"

          if [ -f "$def_file" ]; then
            current=$(grep -A1 '^## Version' "$def_file" 2>/dev/null \
              | grep -oE 'v[0-9]+' | head -1 || true)
            if [ -n "$current" ] && [ "$current" != "$pinned" ]; then
              stale_pins+=" $def_path (pinned=$pinned, current=$current)"
            fi
          fi
        fi
      fi
    done < "$CONTRACTS"

    if [ -n "$stale_pins" ]; then
      context+=$'\n'"[Stale Pins] Definition pins are outdated:$stale_pins."
      context+=$'\n'"  → Why: Implementing against stale pins risks code diverging from the current contract."
      context+=$'\n'"    Update the spec and contracts.yaml to reflect current versions. See SPEC-WORKFLOW.md §7."
    fi
  fi

  # Warn if spec needs revision
  if [ "$spec_status" = "revision-needed" ]; then
    context+=$'\n'"[Spec Needs Revision] $owning_spec is marked revision-needed."
    context+=$'\n'"  → Why: A known issue was found — changes may conflict with the upcoming revision."
    context+=$'\n'"    Review the spec's revision notes before proceeding. See SPEC-WORKFLOW.md §7."
  fi
else
  context="[Unowned File] $REL_PATH is not listed in any spec's owned files in REGISTER.md."
  context+=$'\n'"  → Why: Every source file must have exactly one spec owner for traceability."
  context+=$'\n'"    Assign this file to a spec in REGISTER.md. See SPEC-WORKFLOW.md §2."
fi

if [ -n "$context" ]; then
  jq -n --arg ctx "$context" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: $ctx
    }
  }'
fi

exit 0
