#!/bin/bash
set -e

PROJECT_NAME="character_card"
VENV_PATH="$HOME/virtualenvs/$PROJECT_NAME"

echo "--- Character Card Chat Demo Runner ---"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create venv
mkdir -p "$(dirname "$VENV_PATH")"
if [ ! -d "$VENV_PATH" ]; then
    uv venv "$VENV_PATH"
fi

# Install
uv pip install --python "$VENV_PATH/bin/python" -e "$SCRIPT_DIR/../..[litellm]"
uv pip install --python "$VENV_PATH/bin/python" -e "$SCRIPT_DIR"

# Run with all args passed through
# Usage: ./run.sh path/to/card.png [--user NAME] [--no-system-prompt]
"$VENV_PATH/bin/python" -m character_card.main "$@"
