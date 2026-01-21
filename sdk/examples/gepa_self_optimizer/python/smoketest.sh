#!/bin/bash
# Smoketest for GEPA Self-Optimizer
# Runs with minimal settings to verify everything works end-to-end

set -e

# --- Configuration ---
VENV_PATH=".venv"

# --- Parse Arguments ---
LOCAL_INSTALL=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --local|-l)
            LOCAL_INSTALL=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Establish project root by walking up to find .git directory
# This ensures paths work regardless of where the script is invoked from
find_project_root() {
    local dir="$1"
    while [[ "$dir" != "/" ]]; do
        if [[ -d "$dir/.git" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    echo "Error: Could not find project root (no .git directory found)" >&2
    return 1
}

PROJECT_ROOT="$(find_project_root "$SCRIPT_DIR")"
PYTHON_SDK_PATH="$PROJECT_ROOT/sdk/python"

echo "=============================================="
echo "GEPA Self-Optimizer Smoketest"
echo "=============================================="
echo "Example root: $EXAMPLE_ROOT"
echo ""

# Change to python directory
cd "$SCRIPT_DIR"

# 0. Ensure uv is installed
if ! command -v uv &> /dev/null; then
    echo "📥 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 1. Create Virtual Environment
echo "Ensuring virtual environment..."
if [ ! -d "$VENV_PATH" ]; then
    uv venv "$VENV_PATH"
else
    echo "Virtual environment already exists."
fi

# 3. Install Dependencies
echo "Installing dependencies..."
if [ "$LOCAL_INSTALL" = true ]; then
    echo "  - Installing flatagents from local source..."
    uv pip install --python "$VENV_PATH/bin/python" -e "$PYTHON_SDK_PATH[litellm]"
else
    echo "  - Installing flatagents from PyPI..."
    uv pip install --python "$VENV_PATH/bin/python" "flatagents[litellm]"
fi

# Clean up any previous test data
echo ""
echo "Cleaning up previous test data..."
rm -f "$EXAMPLE_ROOT/data/evaluation_set.json"
rm -rf "$EXAMPLE_ROOT/output/"

echo ""
echo "Step 1: Generate minimal evaluation data"
echo "----------------------------------------------"
"$VENV_PATH/bin/python" main.py generate-data --num-examples 10

echo ""
echo "Step 2: Evaluate baseline judge"
echo "----------------------------------------------"
"$VENV_PATH/bin/python" main.py evaluate

echo ""
echo "Step 3: Run GEPA optimization (minimal settings)"
echo "----------------------------------------------"
"$VENV_PATH/bin/python" main.py run \
    --num-examples 10 \
    --budget 3 \
    --pareto-size 5 \
    --minibatch-size 2 \
    --force-regenerate

echo ""
echo "=============================================="
echo "Smoketest Complete!"
echo "=============================================="
echo ""
echo "Output files:"
ls -la "$EXAMPLE_ROOT/output/" 2>/dev/null || echo "  (no output directory)"
echo ""
echo "To run a full optimization:"
echo "  cd $SCRIPT_DIR && .venv/bin/python main.py run --num-examples 100 --budget 50"
