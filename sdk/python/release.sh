#!/bin/bash
set -e

cd "$(dirname "$0")"
SDK_DIR="$(pwd)"
REPO_ROOT="$SDK_DIR/../.."
FLATAGENTS_DIR="$SDK_DIR/flatagents"
FLATMACHINES_DIR="$SDK_DIR/flatmachines"
FLATAGENTS_ASSETS="$FLATAGENTS_DIR/flatagents/assets"
FLATMACHINES_ASSETS="$FLATMACHINES_DIR/flatmachines/assets"

# Parse arguments
DRY_RUN=true  # Safe by default, note that dry run DOES change local assets.
while [[ $# -gt 0 ]]; do
    case $1 in
        --apply)
            DRY_RUN=false
            shift
            ;;
        *)
            echo "Unknown flag: $1"
            echo "Usage: $0 [--apply]"
            echo ""
            echo "Options:"
            echo "  --apply    Actually upload to PyPI (default is dry-run)"
            exit 1
            ;;
    esac
done

echo "=== Python SDK Release ==="
if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  DRY RUN MODE (will not upload to PyPI)"
    echo "  Run with --apply to actually release"
    echo "════════════════════════════════════════════════════════════"
fi
echo ""

extract_version() {
    local pyproject_path="$1"
    python - <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text().splitlines()
in_project = False
version = ""
for line in text:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        in_project = stripped == "[project]"
        continue
    if not in_project:
        continue
    match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
    if match:
        version = match.group(1)
        break
print(version)
PY
}

FLATAGENTS_VERSION=$(extract_version "$FLATAGENTS_DIR/pyproject.toml")
FLATMACHINES_VERSION=$(extract_version "$FLATMACHINES_DIR/pyproject.toml")

if [[ -z "$FLATAGENTS_VERSION" || -z "$FLATMACHINES_VERSION" ]]; then
    echo "RELEASE ABORTED: Could not read [project] version from pyproject.toml."
    exit 1
fi

if [[ "$FLATAGENTS_VERSION" != "$FLATMACHINES_VERSION" ]]; then
    echo "RELEASE ABORTED: flatagents ($FLATAGENTS_VERSION) and flatmachines ($FLATMACHINES_VERSION) versions differ."
    exit 1
fi

SDK_VERSION="$FLATAGENTS_VERSION"
export SDK_VERSION

sync_init_version() {
    local init_path="$1"
    local pkg_name="$2"

    CURRENT_INIT_VERSION=$(python - <<'PY'
import pathlib
import re
import sys

text = pathlib.Path(sys.argv[1]).read_text()
match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
print(match.group(1) if match else "")
PY
"$init_path")

    if [[ -z "$CURRENT_INIT_VERSION" ]]; then
        echo "RELEASE ABORTED: __version__ not found in $pkg_name/__init__.py."
        exit 1
    fi

    if [[ "$CURRENT_INIT_VERSION" != "$SDK_VERSION" ]]; then
        echo "Updating $pkg_name/__init__.py __version__ to $SDK_VERSION"
        python - <<'PY'
import os
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text()
version = os.environ["SDK_VERSION"]
updated, count = re.subn(
    r'^__version__\s*=\s*"[^"]+"',
    f'__version__ = "{version}"',
    text,
    flags=re.M,
)
if count != 1:
    raise SystemExit("RELEASE ABORTED: __version__ not found or ambiguous")
path.write_text(updated)
PY
"$init_path"
    fi
}

sync_init_version "$FLATAGENTS_DIR/flatagents/__init__.py" "flatagents"
sync_init_version "$FLATMACHINES_DIR/flatmachines/__init__.py" "flatmachines"

# Ensure package README/MACHINES exist (kept package-specific)
if [ ! -f "$FLATAGENTS_DIR/README.md" ]; then
    echo "RELEASE ABORTED: flatagents/README.md missing."
    exit 1
fi
if [ ! -f "$FLATMACHINES_DIR/README.md" ]; then
    echo "RELEASE ABORTED: flatmachines/README.md missing."
    exit 1
fi
if [ ! -f "$FLATMACHINES_DIR/MACHINES.md" ]; then
    echo "RELEASE ABORTED: flatmachines/MACHINES.md missing."
    exit 1
fi

# Copy root TypeScript specs to sdk assets
cp "$REPO_ROOT/flatagent.d.ts" "$REPO_ROOT/flatmachine.d.ts" "$REPO_ROOT/profiles.d.ts" "$FLATAGENTS_ASSETS/"
cp "$REPO_ROOT/flatagent.d.ts" "$REPO_ROOT/flatmachine.d.ts" "$REPO_ROOT/profiles.d.ts" "$FLATMACHINES_ASSETS/"

# Extract versions from root TypeScript specs
echo "Extracting spec versions from TypeScript files..."
if [ ! -d "$REPO_ROOT/scripts/node_modules" ]; then
    echo "Installing script dependencies..."
    (cd "$REPO_ROOT/scripts" && npm install --silent)
fi
FLATAGENT_VERSION=$(cd "$REPO_ROOT/scripts" && npx tsx generate-spec-assets.ts --extract-version "$REPO_ROOT/flatagent.d.ts")
FLATMACHINE_VERSION=$(cd "$REPO_ROOT/scripts" && npx tsx generate-spec-assets.ts --extract-version "$REPO_ROOT/flatmachine.d.ts")
PROFILES_VERSION=$(cd "$REPO_ROOT/scripts" && npx tsx generate-spec-assets.ts --extract-version "$REPO_ROOT/profiles.d.ts")
RUNTIME_VERSION=$(cd "$REPO_ROOT/scripts" && npx tsx generate-spec-assets.ts --extract-version "$REPO_ROOT/flatagents-runtime.d.ts")

echo "TypeScript spec versions:"
echo "  flatagent.d.ts:          $FLATAGENT_VERSION"
echo "  flatmachine.d.ts:        $FLATMACHINE_VERSION"
echo "  profiles.d.ts:           $PROFILES_VERSION"
echo "  flatagents-runtime.d.ts: $RUNTIME_VERSION"
echo ""

# Validate SDK __version__ matches spec versions (all specs unified to same version)
FAILED=0

if [[ "$SDK_VERSION" != "$FLATAGENT_VERSION" ]]; then
    echo "  ✗ SDK version ($SDK_VERSION) != flatagent.d.ts ($FLATAGENT_VERSION)"
    FAILED=1
else
    echo "  ✓ SDK version matches flatagent.d.ts ($FLATAGENT_VERSION)"
fi

if [[ "$SDK_VERSION" != "$FLATMACHINE_VERSION" ]]; then
    echo "  ✗ SDK version ($SDK_VERSION) != flatmachine.d.ts ($FLATMACHINE_VERSION)"
    FAILED=1
else
    echo "  ✓ SDK version matches flatmachine.d.ts ($FLATMACHINE_VERSION)"
fi

if [[ "$SDK_VERSION" != "$PROFILES_VERSION" ]]; then
    echo "  ✗ SDK version ($SDK_VERSION) != profiles.d.ts ($PROFILES_VERSION)"
    FAILED=1
else
    echo "  ✓ SDK version matches profiles.d.ts ($PROFILES_VERSION)"
fi

if [[ "$SDK_VERSION" != "$RUNTIME_VERSION" ]]; then
    echo "  ✗ SDK version ($SDK_VERSION) != flatagents-runtime.d.ts ($RUNTIME_VERSION)"
    FAILED=1
else
    echo "  ✓ SDK version matches flatagents-runtime.d.ts ($RUNTIME_VERSION)"
fi

if [[ "$FAILED" -eq 1 ]]; then
    echo ""
    echo "RELEASE ABORTED: SDK version mismatch with TypeScript specs."
    echo "Update version in pyproject.toml to match spec versions."
    exit 1
fi

echo ""

# Generate spec assets from root specs for both packages
"$REPO_ROOT/scripts/generate-spec-assets.sh" "$FLATAGENTS_ASSETS"
"$REPO_ROOT/scripts/generate-spec-assets.sh" "$FLATMACHINES_ASSETS"

echo ""

verify_assets() {
    local assets_dir="$1"
    echo "Verifying spec assets in $assets_dir..."
    FAILED=0

    for file in flatagent.d.ts flatmachine.d.ts profiles.d.ts flatagents-runtime.d.ts; do
        if [ ! -f "$assets_dir/$file" ]; then
            echo "  ✗ $file (missing)"
            FAILED=1
        elif ! diff -q "$REPO_ROOT/$file" "$assets_dir/$file" > /dev/null 2>&1; then
            echo "  ✗ $file (does not match root)"
            FAILED=1
        else
            echo "  ✓ $file"
        fi
    done

    for file in flatagent.slim.d.ts flatmachine.slim.d.ts profiles.slim.d.ts flatagents-runtime.slim.d.ts \
                flatagent.schema.json flatmachine.schema.json profiles.schema.json flatagents-runtime.schema.json; do
        if [ ! -f "$assets_dir/$file" ]; then
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
}

verify_assets "$FLATAGENTS_ASSETS"
verify_assets "$FLATMACHINES_ASSETS"

echo "All spec assets verified."
echo ""

# Setup virtualenv with build tools
if [ ! -d ~/virtualenvs/twine ]; then
    python -m venv ~/virtualenvs/twine
    ~/virtualenvs/twine/bin/pip install --upgrade build twine
fi
source ~/virtualenvs/twine/bin/activate

build_and_upload() {
    local pkg_dir="$1"
    local pkg_name="$2"

    echo "Building $pkg_name..."
    (cd "$pkg_dir" && rm -rf dist/ build/ *.egg-info)
    (cd "$pkg_dir" && python -m build)

    if [ "$DRY_RUN" = true ]; then
        echo ""
        echo "DRY RUN: Skipping PyPI upload for $pkg_name."
        (cd "$pkg_dir" && ls dist/*.whl | head -1 | xargs basename)
    else
        (cd "$pkg_dir" && twine upload dist/*)
        echo "Released $pkg_name: $(cd "$pkg_dir" && ls dist/*.whl | head -1 | xargs basename)"
    fi
    echo ""
}

build_and_upload "$FLATAGENTS_DIR" "flatagents"
build_and_upload "$FLATMACHINES_DIR" "flatmachines"
