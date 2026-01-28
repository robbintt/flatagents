#!/bin/bash
set -e

# --- Configuration ---
VENV_PATH=".venv"

# --- Parse Arguments ---
LOCAL_INSTALL=true  # Default to local for integration tests
while [[ $# -gt 0 ]]; do
    case $1 in
        --pypi)
            LOCAL_INSTALL=false
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# --- Script Logic ---
echo "--- FlatAgents Distributed Backends Integration Tests ---"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 0. Ensure uv is installed
if ! command -v uv &> /dev/null; then
    echo "📥 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 1. Create Virtual Environment
echo "🔧 Ensuring virtual environment..."
if [ ! -d "$VENV_PATH" ]; then
    uv venv "$VENV_PATH"
else
    echo "✅ Virtual environment already exists."
fi

# 2. Install Dependencies
echo "📦 Installing dependencies..."
if [ "$LOCAL_INSTALL" = true ]; then
    echo "  - Installing flatagents from local source..."
    # Go up to sdk/python level
    uv pip install --python "$VENV_PATH/bin/python" -e "$SCRIPT_DIR/../../..[litellm]"
else
    echo "  - Installing flatagents from PyPI..."
    uv pip install --python "$VENV_PATH/bin/python" "flatagents[litellm]"
fi

echo "  - Installing test dependencies..."
uv pip install --python "$VENV_PATH/bin/python" pytest pytest-asyncio

# 3. Run the Tests
echo "🧪 Running distributed backends integration tests..."
echo "---"
"$VENV_PATH/bin/python" -m pytest test_*.py -v
echo "---"

echo "✅ Distributed backends tests complete!"
