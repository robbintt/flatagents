#!/usr/bin/env bash
# Run the RLM example
#
# Usage:
#   ./run.sh                    # Run demo
#   ./run.sh --interactive      # Interactive mode
#   ./run.sh --file doc.txt --task "What is X?"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
if ! python -c "import flatagents" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -e .
fi

# Set PYTHONPATH to include src
export PYTHONPATH="${SCRIPT_DIR}/src:${PYTHONPATH:-}"

# Run the example
if [ $# -eq 0 ]; then
    echo "Running RLM demo..."
    python -m rlm.main --demo
else
    python -m rlm.main "$@"
fi
