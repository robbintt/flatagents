#!/bin/bash
# Lint spec_version references against flatagent.d.ts source of truth
# Usage: lint-spec-versions.sh [repo-root]
# Exit: 0 if all versions match, 1 if mismatches found

set -e

# Get the repo root - script can be run from anywhere
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-.}"

# If relative path, make it relative to script location
if [[ ! "$REPO_ROOT" = /* ]]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)/$REPO_ROOT"
fi

SPEC_FILE="$REPO_ROOT/flatagent.d.ts"

if [[ ! -f "$SPEC_FILE" ]]; then
    echo "Error: flatagent.d.ts not found at $SPEC_FILE"
    exit 1
fi

# Extract the spec version from flatagent.d.ts (source of truth)
# Pattern: * FlatAgents Configuration Schema v0.6.0
SPEC_VERSION=$(grep -m 1 "FlatAgents Configuration Schema v" "$SPEC_FILE" | grep -oE "v[0-9]+\.[0-9]+\.[0-9]+" | sed 's/^v//')

if [[ -z "$SPEC_VERSION" ]]; then
    echo "Error: Could not extract spec_version from $SPEC_FILE"
    exit 1
fi

echo "Source of truth: flatagent.d.ts specifies version $SPEC_VERSION"
echo ""

# Find all YAML/JSON files with spec_version that don't match
cd "$REPO_ROOT"

MISMATCHES=()

while IFS= read -r file; do
    # Extract spec_version from the file
    VERSION=$(rg 'spec_version.*([0-9]+\.[0-9]+\.[0-9]+)' "$file" -o -r '$1' --no-heading | head -1)

    if [[ -z "$VERSION" ]]; then
        continue
    fi

    if [[ "$VERSION" != "$SPEC_VERSION" ]]; then
        MISMATCHES+=("$file: $VERSION (should be $SPEC_VERSION)")
    fi
done < <(rg 'spec_version' --type yaml --type json -l)

if [[ ${#MISMATCHES[@]} -gt 0 ]]; then
    echo "❌ Found $(echo "${#MISMATCHES[@]}") file(s) with mismatched spec_version:"
    echo ""
    for mismatch in "${MISMATCHES[@]}"; do
        echo "  - $mismatch"
    done
    echo ""
    exit 1
else
    echo "✓ All spec_version references match v$SPEC_VERSION"
    exit 0
fi
