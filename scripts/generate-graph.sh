#!/usr/bin/env bash
# generate-graph.sh — Generate project-graph.yaml from specs, skills, hooks, scripts, and the register.
#
# Reads all governed artifacts and produces a dependency graph in YAML format.
# The graph is a derived artifact — REGISTER.md, contracts.yaml, and spec/skill
# frontmatter remain the authoritative sources of truth.
#
# Usage:
#   ./scripts/generate-graph.sh [project-dir] [--dry-run]
#
# Options:
#   --dry-run   Print generated YAML to stdout instead of writing to file.
#
# Requires bash 4+ (uses arrays).

set -euo pipefail

if [ -z "${BASH_VERSION:-}" ]; then
  echo "Error: this script requires bash. Run with: bash $0" >&2
  exit 1
fi

# ── Parse arguments ──────────────────────────────────────────────────

DRY_RUN=false
PROJECT_DIR=""

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    *) [ -z "$PROJECT_DIR" ] && PROJECT_DIR="$arg" ;;
  esac
done

PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
OUTPUT_FILE="$PROJECT_DIR/project-graph.yaml"

# ── Helpers ──────────────────────────────────────────────────────────

# Extract YAML frontmatter (between --- delimiters) from a file.
extract_frontmatter() {
  local file="$1"
  local in_fm=false
  local fm_done=false
  local delimiters=0
  local result=""

  while IFS= read -r line; do
    if [ "$fm_done" = true ]; then break; fi
    if [[ "$line" == "---" ]]; then
      ((delimiters++)) || true
      if [ "$delimiters" -eq 1 ]; then in_fm=true; fi
      if [ "$delimiters" -eq 2 ]; then fm_done=true; fi
      continue
    fi
    if [ "$in_fm" = true ]; then
      result+="$line"$'\n'
    fi
  done < "$file"

  if [ "$delimiters" -lt 2 ]; then
    echo ""
    return 1
  fi

  echo "$result"
}

# Extract a scalar value from YAML frontmatter text.
extract_scalar() {
  local frontmatter="$1"
  local field="$2"
  echo "$frontmatter" | sed -n "s/^${field}:[[:space:]]*//p" | head -1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# Extract content under a markdown ## section heading from a spec file.
# Used for specs that use markdown sections instead of YAML frontmatter.
extract_spec_section() {
  local file="$1"
  local section="$2"
  local in_section=false
  local result=""

  while IFS= read -r line; do
    if [[ "$line" =~ ^##[[:space:]]+"$section"[[:space:]]*$ ]] || [[ "$line" =~ ^##[[:space:]]+"$section"$ ]]; then
      in_section=true
      continue
    fi
    if [ "$in_section" = true ]; then
      if [[ "$line" =~ ^##[[:space:]] ]]; then
        break
      fi
      # Strip leading/trailing whitespace and skip blank lines for single-value sections
      local trimmed
      trimmed=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
      if [ -n "$trimmed" ]; then
        result+="$trimmed"$'\n'
      fi
    fi
  done < "$file"

  # Return first non-empty line (for scalar sections like Status, Owner)
  echo "$result" | head -1
}

# Map skill name to workflow stage.
get_stage() {
  local skill_name="$1"
  case "$skill_name" in
    start)              echo "start" ;;
    design)             echo "design" ;;
    consolidate)        echo "design" ;;
    finish)             echo "finish" ;;
    cleanup)            echo "cleanup" ;;
    promote-spec)       echo "finish" ;;
    pr)                 echo "finish" ;;
    generate-spec)      echo "design" ;;
    generate-register)  echo "governance" ;;
    health-check)       echo "governance" ;;
    init-project)       echo "governance" ;;
    check-register)     echo "governance" ;;
    spec-status)        echo "governance" ;;
    check-contracts)    echo "governance" ;;
    validate-refs)      echo "governance" ;;
    sync-contracts)     echo "governance" ;;
    security-review)    echo "finish" ;;
    orient)             echo "start" ;;
    architect)          echo "governance" ;;
    *)                  echo "unknown" ;;
  esac
}

# Escape a string for YAML (wrap in quotes if it contains special characters).
yaml_escape() {
  local val="$1"
  if [[ "$val" =~ [:\#\[\]\{\}\,\|\>\<\&\*\!\%@\`\"] ]] || [[ "$val" =~ ^[[:space:]] ]] || [[ "$val" =~ [[:space:]]$ ]]; then
    # Double-quote and escape internal double-quotes
    val="${val//\"/\\\"}"
    echo "\"$val\""
  else
    echo "$val"
  fi
}

# ── Collect all known skill names (for edge detection) ───────────────

skill_names=()
while IFS= read -r skill_dir; do
  [ -n "$skill_dir" ] && skill_names+=("$(basename "$skill_dir")")
done < <(find "$PROJECT_DIR/.claude/skills" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

# ── Build output ─────────────────────────────────────────────────────

output=""
output+="# Do not edit manually — regenerate with: bash scripts/generate-graph.sh"$'\n'
output+="---"$'\n'

# ── NODES ────────────────────────────────────────────────────────────

output+="nodes:"$'\n'

# ── Spec nodes ───────────────────────────────────────────────────────

spec_files=()
while IFS= read -r f; do
  [ -n "$f" ] && spec_files+=("$f")
done < <(find "$PROJECT_DIR/docs/specs" -name "*.spec.md" -type f 2>/dev/null | sort)

for spec_file in "${spec_files[@]}"; do
  filename=$(basename "$spec_file")
  spec_id="${filename%.spec.md}"
  rel_path="${spec_file#"$PROJECT_DIR/"}"

  # Try YAML frontmatter first
  frontmatter=$(extract_frontmatter "$spec_file" 2>/dev/null) || true

  if [ -n "$frontmatter" ]; then
    spec_name=$(extract_scalar "$frontmatter" "name")
    spec_status=$(extract_scalar "$frontmatter" "status")
  else
    # Fall back to markdown sections
    spec_name=$(extract_spec_section "$spec_file" "Name") || true
    spec_status=$(extract_spec_section "$spec_file" "Status") || true
  fi

  # Use filename stem as name if empty
  [ -z "$spec_name" ] && spec_name="$spec_id"
  [ -z "$spec_status" ] && spec_status="unknown"

  output+="  - id: spec:${spec_id}"$'\n'
  output+="    type: spec"$'\n'
  output+="    name: $(yaml_escape "$spec_name")"$'\n'
  output+="    status: ${spec_status}"$'\n'
  output+="    path: ${rel_path}"$'\n'
done

# ── Skill nodes ──────────────────────────────────────────────────────

for skill_name in "${skill_names[@]}"; do
  skill_file="$PROJECT_DIR/.claude/skills/$skill_name/SKILL.md"
  [ ! -f "$skill_file" ] && continue

  rel_path="${skill_file#"$PROJECT_DIR/"}"
  frontmatter=$(extract_frontmatter "$skill_file" 2>/dev/null) || true

  skill_layer=""
  skill_desc=""
  if [ -n "$frontmatter" ]; then
    skill_layer=$(extract_scalar "$frontmatter" "layer")
    skill_desc=$(extract_scalar "$frontmatter" "description")
  fi
  [ -z "$skill_layer" ] && skill_layer="0"

  skill_stage=$(get_stage "$skill_name")

  output+="  - id: skill:${skill_name}"$'\n'
  output+="    type: skill"$'\n'
  output+="    layer: ${skill_layer}"$'\n'
  output+="    stage: ${skill_stage}"$'\n'
  if [ -n "$skill_desc" ]; then
    output+="    description: $(yaml_escape "$skill_desc")"$'\n'
  fi
  output+="    path: ${rel_path}"$'\n'
done

# ── Script nodes ─────────────────────────────────────────────────────

script_files=()
while IFS= read -r f; do
  [ -n "$f" ] && script_files+=("$f")
done < <(find "$PROJECT_DIR/scripts" -name "*.sh" -type f 2>/dev/null | sort)

for script_file in "${script_files[@]}"; do
  filename=$(basename "$script_file")
  script_id="${filename%.sh}"
  rel_path="${script_file#"$PROJECT_DIR/"}"

  output+="  - id: script:${script_id}"$'\n'
  output+="    type: script"$'\n'
  output+="    path: ${rel_path}"$'\n'
done

# ── Hook nodes ───────────────────────────────────────────────────────

settings_file="$PROJECT_DIR/.claude/settings.json"
hook_files=()
while IFS= read -r f; do
  [ -n "$f" ] && hook_files+=("$f")
done < <(find "$PROJECT_DIR/.claude/hooks" -name "*.sh" -type f 2>/dev/null | sort)

for hook_file in "${hook_files[@]}"; do
  filename=$(basename "$hook_file")
  hook_id="${filename%.sh}"
  rel_path="${hook_file#"$PROJECT_DIR/"}"

  # Derive trigger type from settings.json by finding which event section
  # references this hook file
  trigger="unknown"
  if [ -f "$settings_file" ]; then
    # Search for the hook filename in settings.json and find the enclosing event type
    # The structure is: "SessionStart": [...], "PreToolUse": [...], "PostToolUse": [...]
    # We look for the filename and then find the nearest preceding event key
    current_event=""
    while IFS= read -r line; do
      # Match event type keys (SessionStart, PreToolUse, PostToolUse)
      if [[ "$line" =~ \"(SessionStart|PreToolUse|PostToolUse)\" ]]; then
        current_event="${BASH_REMATCH[1]}"
      fi
      if [[ "$line" == *"$filename"* ]]; then
        trigger="$current_event"
        break
      fi
    done < "$settings_file"
  fi

  output+="  - id: hook:${hook_id}"$'\n'
  output+="    type: hook"$'\n'
  output+="    trigger: ${trigger}"$'\n'
  output+="    path: ${rel_path}"$'\n'
done

# ── Document nodes ───────────────────────────────────────────────────

doc_checks=(
  "SPEC-WORKFLOW.md"
  "docs/REGISTER.md"
  "docs/ARCHITECTURE.md"
  "contracts.yaml"
)

for doc_path in "${doc_checks[@]}"; do
  if [ -f "$PROJECT_DIR/$doc_path" ]; then
    # Create an id from the filename without extension
    doc_basename=$(basename "$doc_path")
    doc_id="${doc_basename%%.*}"
    # Lowercase the id
    doc_id=$(echo "$doc_id" | tr '[:upper:]' '[:lower:]')

    output+="  - id: doc:${doc_id}"$'\n'
    output+="    type: document"$'\n'
    output+="    path: ${doc_path}"$'\n'
  fi
done

# ── Definition nodes ─────────────────────────────────────────────────

if [ -d "$PROJECT_DIR/docs/definitions" ]; then
  while IFS= read -r def_file; do
    [ -z "$def_file" ] && continue
    filename=$(basename "$def_file")
    def_id="${filename%%.*}"
    rel_path="${def_file#"$PROJECT_DIR/"}"

    # Try to extract version from frontmatter
    def_version=""
    frontmatter=$(extract_frontmatter "$def_file" 2>/dev/null) || true
    if [ -n "$frontmatter" ]; then
      def_version=$(extract_scalar "$frontmatter" "version")
    fi
    [ -z "$def_version" ] && def_version="v0"

    output+="  - id: def:${def_id}"$'\n'
    output+="    type: definition"$'\n'
    output+="    version: ${def_version}"$'\n'
    output+="    path: ${rel_path}"$'\n'
  done < <(find "$PROJECT_DIR/docs/definitions" -type f 2>/dev/null | sort)
fi

# ── EDGES ────────────────────────────────────────────────────────────

output+="edges:"$'\n'

# ── Ownership edges from REGISTER.md ─────────────────────────────────

register_file="$PROJECT_DIR/docs/REGISTER.md"
if [ -f "$register_file" ]; then
  in_spec_index=false
  while IFS= read -r line; do
    # Detect the Spec Index table by its header row
    if [[ "$line" == *"| Spec |"* ]]; then
      in_spec_index=true
      continue
    fi
    # Skip separator row
    if [ "$in_spec_index" = true ] && [[ "$line" == *"---"* ]] && [[ "$line" == "|"* ]]; then
      continue
    fi
    # End of table
    if [ "$in_spec_index" = true ] && [[ "$line" != "|"* ]]; then
      in_spec_index=false
      continue
    fi
    if [ "$in_spec_index" = true ]; then
      # Parse table row: | Spec | Phase | Status | Owns | Depends On |
      # Use awk to extract columns — $2 is spec, $5 is owns
      spec_col=$(echo "$line" | awk -F'|' '{print $2}' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
      owns_col=$(echo "$line" | awk -F'|' '{print $5}' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

      if [ -z "$spec_col" ] || [ "$spec_col" = "—" ]; then continue; fi
      if [ -z "$owns_col" ] || [ "$owns_col" = "—" ]; then continue; fi

      # Derive spec id from filename
      spec_id="${spec_col%.spec.md}"

      # owns_col contains comma-separated backtick-wrapped paths
      # Strip backticks and split on comma
      owns_clean=$(echo "$owns_col" | sed 's/`//g')
      IFS=',' read -ra owns_items <<< "$owns_clean"
      for item in "${owns_items[@]}"; do
        item=$(echo "$item" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [ -z "$item" ] && continue
        output+="  - from: spec:${spec_id}"$'\n'
        output+="    to: \"file:${item}\""$'\n'
        output+="    rel: owns"$'\n'
      done
    fi
  done < "$register_file"
fi

# ── Skill call-graph edges ───────────────────────────────────────────

for skill_name in "${skill_names[@]}"; do
  skill_file="$PROJECT_DIR/.claude/skills/$skill_name/SKILL.md"
  [ ! -f "$skill_file" ] && continue

  # Read the file body (skip frontmatter)
  body=""
  in_fm=false
  fm_done=false
  delimiters=0
  while IFS= read -r line; do
    if [[ "$line" == "---" ]]; then
      ((delimiters++)) || true
      if [ "$delimiters" -eq 2 ]; then fm_done=true; fi
      continue
    fi
    if [ "$fm_done" = true ]; then
      body+="$line"$'\n'
    fi
  done < "$skill_file"

  # If no frontmatter, use the whole file as body
  if [ "$delimiters" -lt 2 ]; then
    body=$(cat "$skill_file")
  fi

  # Track already-emitted edges to avoid duplicates
  emitted_calls=()
  emitted_suggests=()
  emitted_runs=()

  # Check each line for references to other skills and scripts
  while IFS= read -r line; do
    # Skip empty lines
    [ -z "$line" ] && continue

    # Look for /skill-name references
    for target_skill in "${skill_names[@]}"; do
      # Skip self-references
      [ "$target_skill" = "$skill_name" ] && continue

      # Check if this line mentions /target_skill
      if [[ "$line" == *"/${target_skill}"* ]]; then
        # Determine edge type based on context words
        lower_line=$(echo "$line" | tr '[:upper:]' '[:lower:]')

        if [[ "$lower_line" == *"suggest"* ]] || [[ "$lower_line" == *"optionally"* ]] || [[ "$lower_line" == *"if needed"* ]] || [[ "$lower_line" == *"recommend"* ]]; then
          # Check for duplicates
          is_dup=false
          for e in "${emitted_suggests[@]+"${emitted_suggests[@]}"}"; do
            [ "$e" = "$target_skill" ] && is_dup=true
          done
          if [ "$is_dup" = false ]; then
            output+="  - from: skill:${skill_name}"$'\n'
            output+="    to: skill:${target_skill}"$'\n'
            output+="    rel: suggests"$'\n'
            emitted_suggests+=("$target_skill")
          fi
        elif [[ "$lower_line" == *"call"* ]] || [[ "$lower_line" == *"invoke"* ]] || [[ "$lower_line" == *"run"* ]] || [[ "$lower_line" == *"then"* ]] || [[ "$lower_line" == *"orchestrate"* ]]; then
          is_dup=false
          for e in "${emitted_calls[@]+"${emitted_calls[@]}"}"; do
            [ "$e" = "$target_skill" ] && is_dup=true
          done
          if [ "$is_dup" = false ]; then
            output+="  - from: skill:${skill_name}"$'\n'
            output+="    to: skill:${target_skill}"$'\n'
            output+="    rel: calls"$'\n'
            emitted_calls+=("$target_skill")
          fi
        else
          # Default: if mentioned without clear context, treat as "calls"
          is_dup=false
          for e in "${emitted_calls[@]+"${emitted_calls[@]}"}"; do
            [ "$e" = "$target_skill" ] && is_dup=true
          done
          if [ "$is_dup" = false ]; then
            output+="  - from: skill:${skill_name}"$'\n'
            output+="    to: skill:${target_skill}"$'\n'
            output+="    rel: calls"$'\n'
            emitted_calls+=("$target_skill")
          fi
        fi
      fi
    done

    # Look for scripts/*.sh references
    if [[ "$line" == *"scripts/"*".sh"* ]]; then
      # Extract script paths from the line
      while [[ "$line" =~ scripts/([a-zA-Z0-9_-]+)\.sh ]]; do
        script_ref="${BASH_REMATCH[1]}"
        # Check for duplicates
        is_dup=false
        for e in "${emitted_runs[@]+"${emitted_runs[@]}"}"; do
          [ "$e" = "$script_ref" ] && is_dup=true
        done
        if [ "$is_dup" = false ]; then
          output+="  - from: skill:${skill_name}"$'\n'
          output+="    to: script:${script_ref}"$'\n'
          output+="    rel: runs"$'\n'
          emitted_runs+=("$script_ref")
        fi
        # Remove the match to find additional occurrences
        line="${line#*"scripts/${script_ref}.sh"}"
      done
    fi
  done <<< "$body"
done

# ── Spec requires edges ──────────────────────────────────────────────

for spec_file in "${spec_files[@]}"; do
  filename=$(basename "$spec_file")
  spec_id="${filename%.spec.md}"

  # Look for Requires table and extract document path references
  in_requires=false
  while IFS= read -r line; do
    if [[ "$line" =~ ^##[[:space:]]+Requires ]] || [[ "$line" =~ ^##[[:space:]]+Inbound ]]; then
      in_requires=true
      continue
    fi
    if [ "$in_requires" = true ]; then
      # End of section at next ## heading
      if [[ "$line" =~ ^##[[:space:]] ]] && ! [[ "$line" =~ ^###[[:space:]] ]]; then
        in_requires=false
        continue
      fi
      # Parse table rows for backtick-wrapped paths
      if [[ "$line" == "|"* ]]; then
        # Skip header and separator rows
        if [[ "$line" == *"Dependency"* ]] || [[ "$line" == *"---"* ]]; then
          continue
        fi
        # Extract paths from backticks in the Source column
        while [[ "$line" =~ \`([^\`]+)\` ]]; do
          ref="${BASH_REMATCH[1]}"
          # Only emit edges for document-like paths (not inline descriptions)
          if [[ "$ref" == *"/"* ]] || [[ "$ref" == *".md" ]] || [[ "$ref" == *".yaml" ]] || [[ "$ref" == *".yml" ]]; then
            # Normalize the path to a node id
            ref_basename=$(basename "$ref")
            ref_id="${ref_basename%%.*}"
            ref_id=$(echo "$ref_id" | tr '[:upper:]' '[:lower:]')

            output+="  - from: spec:${spec_id}"$'\n'
            output+="    to: \"doc:${ref_id}\""$'\n'
            output+="    rel: requires"$'\n'
          fi
          # Remove the match to find more
          line="${line#*"\`${ref}\`"}"
        done
      fi
    fi
  done < "$spec_file"
done

# ── Spec provides edges ───────────────────────────────────────────────

for spec_file in "${spec_files[@]}"; do
  filename=$(basename "$spec_file")
  spec_id="${filename%.spec.md}"

  # Look for Provides table and extract export references
  in_provides=false
  while IFS= read -r line; do
    if [[ "$line" =~ ^##[[:space:]]+Provides ]]; then
      in_provides=true
      continue
    fi
    if [ "$in_provides" = true ]; then
      # End of section at next ## heading (but not ### subheadings)
      if [[ "$line" =~ ^##[[:space:]] ]] && ! [[ "$line" =~ ^###[[:space:]] ]]; then
        in_provides=false
        continue
      fi
      # Parse table rows
      if [[ "$line" == "|"* ]]; then
        # Skip header and separator rows
        if [[ "$line" == *"Export"* ]] || [[ "$line" == *"---"* ]]; then
          continue
        fi
        # Extract Export (column 2) and Type (column 3)
        export_col=$(echo "$line" | awk -F'|' '{print $2}' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        type_col=$(echo "$line" | awk -F'|' '{print $3}' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

        [ -z "$export_col" ] && continue

        # If the export is a slash skill, link to the skill node
        if [[ "$type_col" == *"Slash skill"* ]] || [[ "$type_col" == *"slash skill"* ]]; then
          # Extract skill name from /skill-name pattern
          if [[ "$export_col" =~ /([a-zA-Z0-9_-]+) ]]; then
            target_skill="${BASH_REMATCH[1]}"
            output+="  - from: spec:${spec_id}"$'\n'
            output+="    to: skill:${target_skill}"$'\n'
            output+="    rel: provides"$'\n'
          fi
        fi
      fi
    fi
  done < "$spec_file"
done

# ── Belongs-to-stage edges ───────────────────────────────────────────

for skill_name in "${skill_names[@]}"; do
  skill_stage=$(get_stage "$skill_name")
  if [ "$skill_stage" != "unknown" ]; then
    output+="  - from: skill:${skill_name}"$'\n'
    output+="    to: stage:${skill_stage}"$'\n'
    output+="    rel: belongs-to-stage"$'\n'
  fi
done

# ── Output ───────────────────────────────────────────────────────────

if [ "$DRY_RUN" = true ]; then
  echo "$output"
else
  # Show diff if file already exists
  if [ -f "$OUTPUT_FILE" ]; then
    diff_output=$(diff "$OUTPUT_FILE" <(echo "$output") 2>/dev/null) || true
    if [ -n "$diff_output" ]; then
      echo "Changes to project-graph.yaml:"
      echo "$diff_output"
      echo ""
    else
      echo "No changes to project-graph.yaml."
      exit 0
    fi
  fi

  echo "$output" > "$OUTPUT_FILE"
  echo "Generated $OUTPUT_FILE."
fi
