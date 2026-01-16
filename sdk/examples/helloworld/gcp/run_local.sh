#!/bin/bash
# Run the Cloud Function locally without Docker
#
# Prerequisites:
#   - Python 3.11+ with venv
#   - gcloud CLI (for Firestore auth) OR Firestore emulator
#
# Usage:
#   export LLM_API_KEY=your-key
#   ./run_local.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Check for required env vars
if [ -z "$LLM_API_KEY" ]; then
    echo "Error: LLM_API_KEY environment variable is required"
    echo "Export your OpenAI/Cerebras/etc API key:"
    echo "  export LLM_API_KEY=your-key"
    exit 1
fi

# Create venv if it doesn't exist
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/.venv"
fi

# Activate venv
source "$SCRIPT_DIR/.venv/bin/activate"

# Install dependencies
echo "Installing dependencies..."
pip install -q -e "$PROJECT_ROOT/sdk/python"  # flatagents from source
pip install -q -r "$SCRIPT_DIR/requirements.txt"

# Check if using emulator
if [ -n "$FIRESTORE_EMULATOR_HOST" ]; then
    echo "Using Firestore emulator at $FIRESTORE_EMULATOR_HOST"
else
    echo "Using real Firestore (requires gcloud auth)"
    echo "Tip: Run 'firebase emulators:start --only firestore' for offline testing"
fi

echo ""
echo "Starting local server on http://localhost:8080"
echo "Test with:"
echo '  curl -X POST http://localhost:8080 -H "Content-Type: application/json" -d '"'"'{"target":"Hi"}'"'"
echo ""

# Run locally
cd "$SCRIPT_DIR"
functions-framework --target=helloworld --port=8080 --debug
