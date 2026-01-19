#!/usr/bin/env bash
# Run the RLM example
#
# Usage:
#   ./run.sh                    # Run demo
#   ./run.sh --local            # Run demo with local SDK
#   ./run.sh --interactive      # Interactive mode
#   ./run.sh --file doc.txt --task "What is X?"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$SCRIPT_DIR"

# Check for --local flag
USE_LOCAL_SDK=false
ARGS=()
for arg in "$@"; do
    if [ "$arg" == "--local" ]; then
        USE_LOCAL_SDK=true
    else
        ARGS+=("$arg")
    fi
done

# Check for virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
if $USE_LOCAL_SDK; then
    echo "Installing local SDK from $SDK_DIR..."
    pip install -e "$SDK_DIR" -q
    pip install -e . -q
elif ! python -c "import flatagents" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -e .
fi

# Set PYTHONPATH to include src
export PYTHONPATH="${SCRIPT_DIR}/src:${PYTHONPATH:-}"

# Run the example
if [ ${#ARGS[@]} -eq 0 ]; then
    echo "Running RLM demo..."
    python -m rlm.main --demo
else
    python -m rlm.main "${ARGS[@]}"
fi
