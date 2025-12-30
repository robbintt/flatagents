#!/bin/bash
set -e

# --- Configuration ---
PROJECT_NAME="mcp_exa"
VENV_PATH="$HOME/virtualenvs/$PROJECT_NAME"

# --- Script Logic ---
echo "--- MCP Exa Demo Runner ---"

# Get the directory the script is located in
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script's directory
cd "$SCRIPT_DIR"

# 1. Check for API Keys
if [ -z "$EXA_MCP_API_KEY" ]; then
    echo "ERROR: EXA_MCP_API_KEY not set."
    echo "   Get an API key at https://exa.ai"
    echo "   export EXA_MCP_API_KEY='your-key-here'"
    exit 1
fi

if [ -z "$CEREBRAS_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: No LLM API key found."
    echo "   Please set CEREBRAS_API_KEY or OPENAI_API_KEY:"
    echo "   export CEREBRAS_API_KEY='your-key-here'"
    exit 1
fi

# 2. Create Virtual Environment
echo "Ensuring virtual environment at $VENV_PATH..."
mkdir -p "$(dirname "$VENV_PATH")"
if [ ! -d "$VENV_PATH" ]; then
    uv venv "$VENV_PATH"
else
    echo "Virtual environment already exists."
fi

# 3. Install Dependencies
echo "Installing dependencies..."
echo "  - Installing flatagents..."
uv pip install --python "$VENV_PATH/bin/python" -e "$SCRIPT_DIR/../..[litellm]"

echo "  - Installing aisuite with MCP support..."
uv pip install --python "$VENV_PATH/bin/python" "aisuite[mcp]"

echo "  - Installing mcp_exa package..."
uv pip install --python "$VENV_PATH/bin/python" -e "$SCRIPT_DIR"

# 4. Run the Demo
echo "Running demo..."
echo "---"
"$VENV_PATH/bin/python" -m mcp_exa.main
echo "---"

echo "Demo complete!"
