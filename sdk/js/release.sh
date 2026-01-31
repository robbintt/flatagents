#!/bin/bash
set -e

cd "$(dirname "$0")"
SDK_DIR="$(pwd)"
REPO_ROOT="$SDK_DIR/../.."

# Parse arguments
DRY_RUN=true
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
            echo "  --apply    Actually publish to npm (default is dry-run)"
            exit 1
            ;;
    esac
done

echo "=== JavaScript SDK Release ==="
if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  DRY RUN MODE (will not publish to npm)"
    echo "  Run with --apply to actually release"
    echo "════════════════════════════════════════════════════════════"
fi
echo ""

# Copy MACHINES.md and create symlinks for AGENTS.md/CLAUDE.md
cp "$REPO_ROOT/MACHINES.md" "$SDK_DIR/MACHINES.md"
ln -sf MACHINES.md "$SDK_DIR/AGENTS.md"
ln -sf MACHINES.md "$SDK_DIR/CLAUDE.md"
echo "✓ MACHINES.md synced from root (with AGENTS.md, CLAUDE.md symlinks)"

# Extract version from package.json
PACKAGE_VERSION=$(node -p "require('./package.json').version")

if [[ -z "$PACKAGE_VERSION" ]]; then
    echo "RELEASE ABORTED: Could not read version from package.json."
    exit 1
fi

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

# Validate SDK version matches spec versions
echo "Checking JavaScript SDK version..."
echo "  package.json: $PACKAGE_VERSION"

FAILED=0

if [[ "$PACKAGE_VERSION" != "$FLATAGENT_VERSION" ]]; then
    echo "  ✗ SDK version ($PACKAGE_VERSION) != flatagent.d.ts ($FLATAGENT_VERSION)"
    FAILED=1
else
    echo "  ✓ SDK version matches flatagent.d.ts ($FLATAGENT_VERSION)"
fi

if [[ "$PACKAGE_VERSION" != "$FLATMACHINE_VERSION" ]]; then
    echo "  ✗ SDK version ($PACKAGE_VERSION) != flatmachine.d.ts ($FLATMACHINE_VERSION)"
    FAILED=1
else
    echo "  ✓ SDK version matches flatmachine.d.ts ($FLATMACHINE_VERSION)"
fi

if [[ "$PACKAGE_VERSION" != "$PROFILES_VERSION" ]]; then
    echo "  ✗ SDK version ($PACKAGE_VERSION) != profiles.d.ts ($PROFILES_VERSION)"
    FAILED=1
else
    echo "  ✓ SDK version matches profiles.d.ts ($PROFILES_VERSION)"
fi

if [[ "$PACKAGE_VERSION" != "$RUNTIME_VERSION" ]]; then
    echo "  ✗ SDK version ($PACKAGE_VERSION) != flatagents-runtime.d.ts ($RUNTIME_VERSION)"
    FAILED=1
else
    echo "  ✓ SDK version matches flatagents-runtime.d.ts ($RUNTIME_VERSION)"
fi

if [[ "$FAILED" -eq 1 ]]; then
    echo ""
    echo "RELEASE ABORTED: SDK version mismatch with TypeScript specs."
    echo "Run: scripts/update-spec-versions.sh <version> --js --apply"
    exit 1
fi

echo ""

# Validate schemas/ folder versions match package version
echo "Checking schemas/ folder versions..."
SCHEMA_SPECS=("flatagent" "flatmachine" "profiles" "flatagents-runtime")
SCHEMA_FAILED=0

for spec in "${SCHEMA_SPECS[@]}"; do
    SCHEMA_FILE="schemas/${spec}.d.ts"
    if [[ ! -f "$SCHEMA_FILE" ]]; then
        echo "  ✗ $SCHEMA_FILE not found"
        SCHEMA_FAILED=1
        continue
    fi
    
    SCHEMA_VERSION=$(cd "$REPO_ROOT/scripts" && npx tsx generate-spec-assets.ts --extract-version "$SDK_DIR/$SCHEMA_FILE")
    if [[ "$SCHEMA_VERSION" != "$PACKAGE_VERSION" ]]; then
        echo "  ✗ $SCHEMA_FILE version ($SCHEMA_VERSION) != package.json ($PACKAGE_VERSION)"
        SCHEMA_FAILED=1
    else
        echo "  ✓ $SCHEMA_FILE ($SCHEMA_VERSION)"
    fi
done

if [[ "$SCHEMA_FAILED" -eq 1 ]]; then
    echo ""
    echo "RELEASE ABORTED: schemas/ folder out of sync."
    echo "Run: npx tsx scripts/generate-spec-assets.ts"
    exit 1
fi

echo ""

# Install dependencies
echo "Installing dependencies..."
npm install --silent
echo ""

# Build
echo "Building..."
npm run build

# Verify build output exists
if [ ! -f "dist/index.js" ] || [ ! -f "dist/index.d.ts" ]; then
    echo "RELEASE ABORTED: Build failed - dist/index.js or dist/index.d.ts not found."
    exit 1
fi
echo "  Build output verified."
echo ""

# Run tests
echo "Running tests..."
npm test
echo ""

# Publish to npm
if [ "$DRY_RUN" = true ]; then
    echo "DRY RUN: Running npm publish --dry-run..."
    npm publish --dry-run
    echo ""
    echo "DRY RUN complete. Run with --apply to publish to npm."
else
    if [ -z "$NPMJS_TOKEN_MEMGRAFTER" ]; then
        echo "RELEASE ABORTED: NPMJS_TOKEN_MEMGRAFTER is not set."
        echo "Set NPMJS_TOKEN_MEMGRAFTER to an npm automation token before publishing."
        exit 1
    fi

    echo "Publishing to npm..."
    NPMRC_TMP="$(mktemp)"
    trap 'rm -f "$NPMRC_TMP"' EXIT
    echo "//registry.npmjs.org/:_authToken=${NPMJS_TOKEN_MEMGRAFTER}" > "$NPMRC_TMP"
    NPM_CONFIG_USERCONFIG="$NPMRC_TMP" npm publish
    echo ""
    echo "Released flatagents@$PACKAGE_VERSION to npm"
fi
