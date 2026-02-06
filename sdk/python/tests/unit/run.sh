#!/bin/bash
set -e

# --- Configuration ---
VENV_PATH=".venv"

# --- Parse Arguments ---
# Filter out --local flag (unit tests always use local install)
PYTEST_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --local|-l)
            # Already using local install, just skip this arg
            shift
            ;;
        *)
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

# --- Script Logic ---
echo "--- FlatAgents Unit Tests ---"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 0. Ensure uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
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

# 2. Install Dependencies
echo "Installing dependencies..."
echo "  - Installing flatmachines from local source..."
uv pip install --python "$VENV_PATH/bin/python" -e "$SCRIPT_DIR/../../flatmachines[flatagents]"

echo "  - Installing flatagents from local source..."
uv pip install --python "$VENV_PATH/bin/python" -e "$SCRIPT_DIR/../../flatagents[litellm]"

echo "  - Installing test dependencies..."
uv pip install --python "$VENV_PATH/bin/python" pytest pytest-asyncio

# 3. Run the Tests
echo "Running unit tests..."
echo "---"
# Run tests in current directory and subdirectories
"$VENV_PATH/bin/python" -m pytest . -v "${PYTEST_ARGS[@]}"
echo "---"

echo "Unit tests complete!"
