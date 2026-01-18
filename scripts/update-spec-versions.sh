#!/bin/bash
# Update spec_version across source-of-truth files in lockstep
# Usage: update-spec-versions.sh <new-version> [options]
#
# By default, only updates root .d.ts specs and markdown docs.
# Use SDK flags to also update SDK-specific files.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Parse arguments
NEW_VERSION=""
DRY_RUN=true
UPDATE_PYTHON=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --apply)
            DRY_RUN=false
            shift
            ;;
        --python)
            UPDATE_PYTHON=true
            shift
            ;;
        --*)
            echo "Error: Unknown flag: $1"
            exit 1
            ;;
        *)
            if [[ -z "$NEW_VERSION" ]]; then
                # Validate semver immediately
                if ! [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                    echo "Error: Version must be semver format (e.g., 0.8.0), got: $1"
                    exit 1
                fi
                NEW_VERSION="$1"
            else
                echo "Error: Unexpected argument: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$NEW_VERSION" ]]; then
    echo "Usage: update-spec-versions.sh <new-version> [options]"
    echo ""
    echo "Options:"
    echo "  --apply    Actually apply changes (default is dry-run)"
    echo "  --python   Also update Python SDK and examples"
    echo ""
    echo "What gets updated:"
    echo "  Always:    Root .d.ts specs, README.md, MACHINES.md"
    echo "  --python:  sdk/python/pyproject.toml, sdk/python/flatagents/__init__.py,"
    echo "             sdk/python/examples/**/config/*.yml,"
    echo "             sdk/examples/*/python/config/*.yml"
    echo ""
    echo "NOT updated (generated from sources):"
    echo "  - assets/*.d.ts (run scripts/generate-spec-assets.sh)"
    echo "  - sdk/python/flatagents/assets/*.d.ts (run sdk/python/release.sh)"
    echo ""
    echo "Examples:"
    echo "  update-spec-versions.sh 0.8.0              # dry-run, specs only"
    echo "  update-spec-versions.sh 0.8.0 --apply      # apply specs only"
    echo "  update-spec-versions.sh 0.8.0 --python --apply"
    exit 1
fi

# Banner
if [[ "$DRY_RUN" == true ]]; then
    echo "════════════════════════════════════════════════════════════"
    echo "  DRY RUN MODE (no changes will be made)"
    echo "  Run with --apply to actually update files"
    echo "════════════════════════════════════════════════════════════"
    echo ""
fi

echo "Target version: $NEW_VERSION"
echo "Update Python SDK: $UPDATE_PYTHON"
echo ""

cd "$REPO_ROOT"

# Counters
UPDATED=0
WOULD_UPDATE=0

# Helper function
update_file() {
    local file="$1"
    local pattern="$2"
    local replacement="$3"

    if [[ ! -f "$file" ]]; then
        return
    fi

    if [[ "$DRY_RUN" == true ]]; then
        echo "  Would update: $file"
        ((WOULD_UPDATE++))
    else
        sed -i '' -E "s/$pattern/$replacement/" "$file"
        echo "  Updated: $file"
        ((UPDATED++))
    fi
}

# =============================================================================
# 1. ROOT .d.ts SPECS (source of truth)
# =============================================================================
echo "Root .d.ts specs:"
for file in flatagent.d.ts flatmachine.d.ts profiles.d.ts; do
    update_file "$file" "(SPEC_VERSION = \")[0-9]+\.[0-9]+\.[0-9]+(\")" "\1$NEW_VERSION\2"
done
echo ""

# =============================================================================
# 2. MARKDOWN DOCS (inline examples)
# =============================================================================
echo "Markdown docs:"
for file in README.md MACHINES.md; do
    update_file "$file" "(spec_version:[[:space:]]*[\"'])[0-9]+\.[0-9]+\.[0-9]+([\"'])" "\1$NEW_VERSION\2"
done
echo ""

# =============================================================================
# 3. PYTHON SDK (if --python)
# =============================================================================
if [[ "$UPDATE_PYTHON" == true ]]; then
    echo "Python SDK:"

    # pyproject.toml
    update_file "sdk/python/pyproject.toml" "(^version = \")[0-9]+\.[0-9]+\.[0-9]+(\")" "\1$NEW_VERSION\2"

    # __init__.py __version__
    update_file "sdk/python/flatagents/__init__.py" "(__version__ = \")[0-9]+\.[0-9]+\.[0-9]+(\")" "\1$NEW_VERSION\2"
    echo ""

    # Python SDK examples
    echo "Python SDK examples (sdk/python/examples/**/config/*.yml):"
    while IFS= read -r file; do
        # Skip .venv
        if [[ "$file" == *".venv"* ]]; then
            continue
        fi
        update_file "$file" "(spec_version:[[:space:]]*[\"']?)[0-9]+\.[0-9]+\.[0-9]+([\"']?)" "\1$NEW_VERSION\2"
    done < <(find sdk/python/examples -path "*/config/*.yml" -type f 2>/dev/null || true)
    echo ""

    # Shared examples (Python)
    echo "Shared examples - Python (sdk/examples/*/python/config/*.yml):"
    while IFS= read -r file; do
        update_file "$file" "(spec_version:[[:space:]]*[\"']?)[0-9]+\.[0-9]+\.[0-9]+([\"']?)" "\1$NEW_VERSION\2"
    done < <(find sdk/examples -path "*/python/config/*.yml" -type f 2>/dev/null || true)
    echo ""
fi

# =============================================================================
# SUMMARY
# =============================================================================
echo "════════════════════════════════════════════════════════════"
if [[ "$DRY_RUN" == true ]]; then
    echo "Would update $WOULD_UPDATE file(s)"
    echo ""
    echo "Run with --apply to make changes."
else
    echo "Updated $UPDATED file(s)"
    echo ""
    echo "Next steps:"
    echo "  1. Run 'scripts/generate-spec-assets.sh' to regenerate assets"
    echo "  2. Run 'scripts/lint-spec-versions.sh' to verify"
    if [[ "$UPDATE_PYTHON" == true ]]; then
        echo "  3. Run 'sdk/python/release.sh' to build & verify Python SDK"
    fi
fi
echo "════════════════════════════════════════════════════════════"
