#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Find project root
find_project_root() {
    local dir="$1"
    while [[ "$dir" != "/" ]]; do
        if [[ -e "$dir/.git" ]]; then echo "$dir"; return 0; fi
        dir="$(dirname "$dir")"
    done
    return 1
}
PROJECT_ROOT="$(find_project_root "$SCRIPT_DIR")"
PYTHON_SDK_PATH="$PROJECT_ROOT/sdk/python"

# Ensure venv
if [ ! -d ".venv" ]; then
    uv venv .venv
fi

# Install deps
uv pip install --python .venv/bin/python -e "$PYTHON_SDK_PATH[litellm]" -e . prompt-toolkit tiktoken

case ${1:-observe} in
    run)
        .venv/bin/python -m anything_agent.main run --goal "$2"
        ;;
    resume)
        .venv/bin/python -m anything_agent.main resume --session "$2"
        ;;
    list)
        .venv/bin/python -m anything_agent.main list
        ;;
    observe)
        .venv/bin/python -m anything_agent.main observe
        ;;
    status)
        echo "=== Sessions ===" && sqlite3 -header -column ./anything_agent.db \
            "SELECT substr(session_id,1,8) as id, status, substr(goal,1,40) as goal FROM sessions ORDER BY created_at DESC LIMIT 5" 2>/dev/null || echo "No database yet"
        ;;
    *)
        echo "Usage: ./run.sh [run 'goal'|resume <session>|list|observe|status]"
        ;;
esac
