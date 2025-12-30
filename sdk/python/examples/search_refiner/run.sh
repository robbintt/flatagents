#!/bin/bash
set -e

# --- Configuration ---
PROJECT_NAME="flatagent_search_refiner"
VENV_PATH="$HOME/virtualenvs/$PROJECT_NAME"

# --- Script Logic ---
echo "--- FlatAgent Search Refiner Demo Runner ---"

# Get the directory the script is located in
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script's directory so `uv` can find pyproject.toml
cd "$SCRIPT_DIR"

# 1. Check for API Keys
if [ -z "$CEREBRAS_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ ERROR: No LLM API key found."
    echo "   Please set CEREBRAS_API_KEY or OPENAI_API_KEY:"
    echo "   export CEREBRAS_API_KEY='your-key-here'"
    exit 1
fi

if [ -z "$EXA_API_KEY" ]; then
    echo "❌ ERROR: EXA_API_KEY not found."
    echo "   Please set EXA_API_KEY for web search:"
    echo "   export EXA_API_KEY='your-key-here'"
    echo "   Get one at https://exa.ai"
    exit 1
fi

# 2. Create Virtual Environment
echo "🔧 Ensuring virtual environment at $VENV_PATH..."
mkdir -p "$(dirname "$VENV_PATH")"
if [ ! -d "$VENV_PATH" ]; then
    uv venv "$VENV_PATH"
else
    echo "✅ Virtual environment already exists."
fi

# 3. Install Dependencies
echo "📦 Installing dependencies..."

# Install local flatagents SDK first (not PyPI - local version is newer)
FLATAGENTS_SDK="$SCRIPT_DIR/../../"
echo "  - Installing flatagents[aisuite] from local SDK..."
uv pip install --python "$VENV_PATH/bin/python" -e "$FLATAGENTS_SDK[aisuite]"

# Install search_refiner package (pulls in aisuite[mcp] from pyproject.toml)
echo "  - Installing search_refiner package..."
uv pip install --python "$VENV_PATH/bin/python" -e "$SCRIPT_DIR"

# 4. Run the Demo
QUERY="${*:-latest developments in AI agents}"
echo "🚀 Running search refiner..."
echo "---"
"$VENV_PATH/bin/python" -m search_refiner.main "$QUERY"
echo "---"

echo "✅ Done!"
