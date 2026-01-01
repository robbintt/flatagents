#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default target is assets/ at repo root
TARGET_DIR="${1:-$REPO_ROOT/assets}"

echo "Generating spec assets to: $TARGET_DIR"
echo ""

# Install deps if needed
if [ ! -d "$SCRIPT_DIR/node_modules" ]; then
    echo "Installing dependencies..."
    (cd "$SCRIPT_DIR" && npm install --silent)
fi

# Run the TypeScript generator
(cd "$SCRIPT_DIR" && npx tsx generate-spec-assets.ts "$TARGET_DIR")
