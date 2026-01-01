#!/bin/bash
set -e

cd "$(dirname "$0")"
REPO_ROOT="$(cd ../.. && pwd)"
ASSETS_DIR="$PWD/flatagents/assets"

# Generate spec assets from root specs
echo "Generating spec assets..."
"$REPO_ROOT/scripts/generate-spec-assets.sh" "$ASSETS_DIR"
echo ""

# Verify generated assets match root specs
echo "Verifying spec assets..."
FAILED=0

for file in flatagent.d.ts flatmachine.d.ts; do
    if [ ! -f "$ASSETS_DIR/$file" ]; then
        echo "  ✗ $file (missing)"
        FAILED=1
    elif ! diff -q "$REPO_ROOT/$file" "$ASSETS_DIR/$file" > /dev/null 2>&1; then
        echo "  ✗ $file (does not match root)"
        FAILED=1
    else
        echo "  ✓ $file"
    fi
done

for file in flatagent.slim.d.ts flatmachine.slim.d.ts \
            flatagent.schema.json flatmachine.schema.json; do
    if [ ! -f "$ASSETS_DIR/$file" ]; then
        echo "  ✗ $file (missing)"
        FAILED=1
    else
        echo "  ✓ $file"
    fi
done

if [ "$FAILED" -eq 1 ]; then
    echo ""
    echo "RELEASE ABORTED: Spec asset generation failed."
    exit 1
fi
echo "All spec assets verified."
echo ""

# Setup virtualenv with build tools
if [ ! -d ~/virtualenvs/twine ]; then
    python -m venv ~/virtualenvs/twine
    ~/virtualenvs/twine/bin/pip install --upgrade build twine
fi
source ~/virtualenvs/twine/bin/activate

# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build
python -m build

# Upload to PyPI
twine upload dist/*

echo "Released $(ls dist/*.whl | head -1 | xargs basename)"
