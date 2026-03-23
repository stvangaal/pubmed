#!/usr/bin/env bash
# bootstrap-project.sh — Initialize a new spec-driven project
#
# Usage:
#   ./bootstrap-project.sh <target-directory> [project-name]
#
# Creates the full directory structure, copies templates, installs hooks,
# and produces a ready-to-use project skeleton. If project-name is omitted,
# the directory name is used.
#
# This script is idempotent — it will not overwrite existing files.

set -euo pipefail

# ── Args ─────────────────────────────────────────────────────────────

usage() {
  echo "Usage: $0 [--layer N] <target-directory> [project-name]"
  echo ""
  echo "Creates a spec-driven project structure in the target directory."
  echo "If project-name is omitted, the directory basename is used."
  echo ""
  echo "Options:"
  echo "  --layer N   Only copy skills with layer <= N (default: 99, copies all)"
  exit 1
}

# Parse options
MAX_LAYER=99
while [ $# -gt 0 ]; do
  case "$1" in
    --layer)
      [ $# -lt 2 ] && usage
      MAX_LAYER="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      break
      ;;
  esac
done

if [ $# -lt 1 ]; then
  usage
fi

TARGET_DIR="$(realpath "$1")"
PROJECT_NAME="${2:-$(basename "$TARGET_DIR")}"

# Find the script's own directory to locate templates
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Templates are at ../docs/templates/ relative to this script
TEMPLATES_DIR="$(realpath "$SCRIPT_DIR/../docs/templates")"
# Workflow file is at ../SPEC-WORKFLOW.md
WORKFLOW_FILE="$(realpath "$SCRIPT_DIR/../SPEC-WORKFLOW.md")"
# README is at ../docs/SPEC-WORKFLOW-README.md
README_FILE="$(realpath "$SCRIPT_DIR/../docs/SPEC-WORKFLOW-README.md")"
# Hooks are at ../.claude/
HOOKS_DIR="$(realpath "$SCRIPT_DIR/../.claude")"
# Git hooks are at ../.githooks/
GITHOOKS_DIR="$(realpath "$SCRIPT_DIR/../.githooks")"
# Skills are at ../.claude/skills/
SKILLS_DIR="$(realpath "$SCRIPT_DIR/../.claude/skills")"

# Verify source files exist
for f in "$TEMPLATES_DIR/spec-full.md" "$WORKFLOW_FILE" "$README_FILE"; do
  if [ ! -f "$f" ]; then
    echo "Error: source file not found: $f"
    echo "Run this script from the spec-workflow project directory."
    exit 1
  fi
done

# ── Helper ───────────────────────────────────────────────────────────

copy_if_missing() {
  local src="$1"
  local dst="$2"
  if [ -f "$dst" ]; then
    echo "  exists: $(basename "$dst")"
  else
    cp "$src" "$dst"
    echo "  created: $(basename "$dst")"
  fi
}

mkdir_if_missing() {
  local dir="$1"
  if [ -d "$dir" ]; then
    echo "  exists: $dir"
  else
    mkdir -p "$dir"
    echo "  created: $dir"
  fi
}

# ── Create directory structure ───────────────────────────────────────

echo "Bootstrapping spec-driven project: $PROJECT_NAME"
echo "Target: $TARGET_DIR"
echo ""

echo "Creating directory structure..."
mkdir_if_missing "$TARGET_DIR"
mkdir_if_missing "$TARGET_DIR/docs"
mkdir_if_missing "$TARGET_DIR/docs/definitions"
mkdir_if_missing "$TARGET_DIR/docs/specs"
mkdir_if_missing "$TARGET_DIR/docs/reference"
mkdir_if_missing "$TARGET_DIR/docs/plans"
mkdir_if_missing "$TARGET_DIR/docs/templates"
mkdir_if_missing "$TARGET_DIR/.claude"
mkdir_if_missing "$TARGET_DIR/.claude/hooks"

# ── Copy workflow files ──────────────────────────────────────────────

echo ""
echo "Copying workflow files..."
copy_if_missing "$WORKFLOW_FILE" "$TARGET_DIR/SPEC-WORKFLOW.md"
copy_if_missing "$README_FILE" "$TARGET_DIR/docs/SPEC-WORKFLOW-README.md"

# ── Copy templates ───────────────────────────────────────────────────

echo ""
echo "Copying templates..."
for tmpl in "$TEMPLATES_DIR"/*; do
  basename_tmpl="$(basename "$tmpl")"
  copy_if_missing "$tmpl" "$TARGET_DIR/docs/templates/$basename_tmpl"
done

# ── Copy reserved spec templates into docs/specs/ ────────────────────

echo ""
echo "Copying reserved specs..."
for reserved in test-infrastructure.spec.md project-infrastructure.spec.md; do
  if [ -f "$TEMPLATES_DIR/$reserved" ]; then
    copy_if_missing "$TEMPLATES_DIR/$reserved" "$TARGET_DIR/docs/specs/$reserved"
  fi
done

# ── Copy hooks ───────────────────────────────────────────────────────

echo ""
echo "Copying hooks..."
copy_if_missing "$HOOKS_DIR/settings.json" "$TARGET_DIR/.claude/settings.json"
for hook in "$HOOKS_DIR/hooks"/*; do
  basename_hook="$(basename "$hook")"
  copy_if_missing "$hook" "$TARGET_DIR/.claude/hooks/$basename_hook"
done
chmod +x "$TARGET_DIR/.claude/hooks"/*.sh 2>/dev/null || true

# ── Copy git hooks ────────────────────────────────────────────────────

echo ""
echo "Copying git hooks..."
mkdir_if_missing "$TARGET_DIR/.githooks"
for hook in "$GITHOOKS_DIR"/*; do
  basename_hook="$(basename "$hook")"
  copy_if_missing "$hook" "$TARGET_DIR/.githooks/$basename_hook"
done
chmod +x "$TARGET_DIR/.githooks"/* 2>/dev/null || true

# ── Copy skills ──────────────────────────────────────────────────────

echo ""
echo "Copying skills..."
if [ -d "$SKILLS_DIR" ]; then
  for skill_dir in "$SKILLS_DIR"/*/; do
    [ ! -d "$skill_dir" ] && continue
    skill_name="$(basename "$skill_dir")"
    # Skip dev-prefixed skills (project-internal, not distributed)
    if [[ "$skill_name" == dev-* ]]; then
      echo "  skipped (dev): $skill_name"
      continue
    fi
    # Only copy if SKILL.md exists
    if [ -f "$skill_dir/SKILL.md" ]; then
      # Extract layer from SKILL.md frontmatter
      skill_layer=$(sed -n '/^---$/,/^---$/{ s/^layer:[[:space:]]*\([0-9]\).*/\1/p; }' "$skill_dir/SKILL.md")
      skill_layer="${skill_layer:-0}"
      if [ "$skill_layer" -gt "$MAX_LAYER" ]; then
        echo "  skipped (layer $skill_layer > $MAX_LAYER): $skill_name"
        continue
      fi
      mkdir_if_missing "$TARGET_DIR/.claude/skills/$skill_name"
      copy_if_missing "$skill_dir/SKILL.md" "$TARGET_DIR/.claude/skills/$skill_name/SKILL.md"
    fi
  done
else
  echo "  no skills directory found — skipping"
fi

# ── Create CLAUDE.md from template ───────────────────────────────────

echo ""
echo "Creating CLAUDE.md..."
if [ -f "$TARGET_DIR/CLAUDE.md" ]; then
  echo "  exists: CLAUDE.md"
else
  sed "s/# CLAUDE.md/# CLAUDE.md — $PROJECT_NAME/" \
    "$TEMPLATES_DIR/CLAUDE.md" > "$TARGET_DIR/CLAUDE.md"
  echo "  created: CLAUDE.md"
fi

# ── Create empty contracts.yaml ──────────────────────────────────────

echo ""
echo "Creating contracts.yaml..."
copy_if_missing "$TEMPLATES_DIR/contracts.yaml" "$TARGET_DIR/contracts.yaml"

# ── Create .arboretum.yml ──────────────────────────────────────────────

echo ""
echo "Creating .arboretum.yml..."
if [ -f "$TARGET_DIR/.arboretum.yml" ]; then
  echo "  exists: .arboretum.yml"
else
  cat > "$TARGET_DIR/.arboretum.yml" << 'ARBORETUM'
# Arboretum project configuration
# layer: 0 = foundation, 1 = structure, 2 = governance
layer: 0
ARBORETUM
  echo "  created: .arboretum.yml"
fi

# ── Initialize git if needed ─────────────────────────────────────────

echo ""
if [ -d "$TARGET_DIR/.git" ]; then
  echo "Git repo already exists."
else
  echo "Initializing git repository..."
  (cd "$TARGET_DIR" && git init -q)
  echo "  initialized."
fi

# Configure git to use .githooks directory
echo ""
echo "Configuring git hooks path..."
current_hooks_path=$(cd "$TARGET_DIR" && git config core.hooksPath 2>/dev/null || true)
if [ "$current_hooks_path" = ".githooks" ]; then
  echo "  already set: core.hooksPath = .githooks"
else
  (cd "$TARGET_DIR" && git config core.hooksPath .githooks)
  echo "  configured: core.hooksPath = .githooks"
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo "Done. Project structure:"
echo ""
echo "  $TARGET_DIR/"
echo "  ├── CLAUDE.md                    # AI entry point"
echo "  ├── SPEC-WORKFLOW.md             # Full workflow rules"
echo "  ├── contracts.yaml               # Version pins (empty)"
echo "  ├── .githooks/"
echo "  │   ├── pre-commit               # Secrets scanning"
echo "  │   └── post-commit              # Cross-ref validation on doc changes"
echo "  ├── .claude/"
echo "  │   ├── settings.json            # Hook configuration"
echo "  │   ├── hooks/                   # 4 automation hooks"
echo "  │   └── skills/                  # Framework skills (/pr, /security-review, etc.)"
echo "  └── docs/"
echo "      ├── SPEC-WORKFLOW-README.md  # Workflow overview"
echo "      ├── templates/               # Starter templates"
echo "      ├── definitions/             # (empty — create from architecture)"
echo "      ├── specs/                   # Reserved specs (Phase 0 templates)"
echo "      ├── reference/               # (empty — add domain knowledge)"
echo "      └── plans/                   # (empty — add during implementation)"
echo ""
echo "Next steps:"
echo "  1. Edit CLAUDE.md with your project overview"
echo "  2. Write docs/ARCHITECTURE.md (use docs/templates/architecture.md)"
echo "  3. Extract shared definitions into docs/definitions/"
echo "  4. Fill in the reserved specs in docs/specs/ (test + project infrastructure)"
echo "  5. Write feature specs into docs/specs/"
echo "  6. Build docs/REGISTER.md (use docs/templates/register.md)"
echo "  7. Populate contracts.yaml from spec version pins"
echo "  8. Implement in phase + dependency order"
