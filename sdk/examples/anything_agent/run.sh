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
        shift
        if [[ "$1" == "--goal" || "$1" == "-g" ]]; then
            shift
        fi
        goal="$*"
        if [[ -z "$goal" ]]; then
            echo "Usage: ./run.sh run \"goal\""
            exit 1
        fi
        .venv/bin/python -m anything_agent.main run --goal "$goal"
        ;;
    resume)
        shift
        if [[ "$1" == "--session" || "$1" == "-s" ]]; then
            shift
        fi
        session_id="$1"
        if [[ -z "$session_id" ]]; then
            echo "Usage: ./run.sh resume <session>"
            exit 1
        fi
        .venv/bin/python -m anything_agent.main resume --session "$session_id"
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
        goal="$*"
        if [[ -n "$goal" ]]; then
            .venv/bin/python -m anything_agent.main run --goal "$goal"
            exit 0
        fi
        echo "Usage: ./run.sh run \"goal\""
        echo "       ./run.sh \"goal\"        # shorthand"
        echo "       ./run.sh resume <session>"
        echo "       ./run.sh list | observe | status"
        ;;
esac
