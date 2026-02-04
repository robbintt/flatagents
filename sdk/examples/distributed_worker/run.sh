#!/bin/bash
set -e

# --- Configuration ---
VENV_PATH=".venv"

# --- Parse Arguments ---
LOCAL_INSTALL=false
DEMO_MODE="seed"  # seed, checker, worker, reaper, all
JOB_COUNT=5
MAX_WORKERS=3

while [[ $# -gt 0 ]]; do
    case $1 in
        --local|-l)
            LOCAL_INSTALL=true
            shift
            ;;
        --seed)
            DEMO_MODE="seed"
            shift
            ;;
        --checker)
            DEMO_MODE="checker"
            shift
            ;;
        --worker)
            DEMO_MODE="worker"
            shift
            ;;
        --reaper)
            DEMO_MODE="reaper"
            shift
            ;;
        --all)
            DEMO_MODE="all"
            shift
            ;;
        --count|-n)
            JOB_COUNT="$2"
            shift 2
            ;;
        --max-workers|-m)
            MAX_WORKERS="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# --- Script Logic ---
echo "--- Distributed Worker Demo Runner ---"

# Get the directory the script is located in
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Establish project root by walking up to find .git
find_project_root() {
    local dir="$1"
    while [[ "$dir" != "/" ]]; do
        if [[ -e "$dir/.git" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    echo "Error: Could not find project root (no .git found)" >&2
    return 1
}

PROJECT_ROOT="$(find_project_root "$SCRIPT_DIR")"
FLATAGENTS_SDK_PATH="$PROJECT_ROOT/sdk/python/flatagents"
FLATMACHINES_SDK_PATH="$PROJECT_ROOT/sdk/python/flatmachines"
PYTHON_DIR="$SCRIPT_DIR/python"

echo "📁 Project root: $PROJECT_ROOT"
echo "📁 FlatAgents SDK: $FLATAGENTS_SDK_PATH"
echo "📁 FlatMachines SDK: $FLATMACHINES_SDK_PATH"

# Change to the python directory
cd "$PYTHON_DIR"

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
    echo "  - Installing flatmachines from local source..."
    uv pip install --python "$VENV_PATH/bin/python" -e "$FLATMACHINES_SDK_PATH[flatagents]"
    echo "  - Installing flatagents from local source..."
    uv pip install --python "$VENV_PATH/bin/python" -e "$FLATAGENTS_SDK_PATH"
else
    echo "  - Installing flatmachines from PyPI..."
    uv pip install --python "$VENV_PATH/bin/python" "flatmachines[flatagents]"
    echo "  - Installing flatagents from PyPI..."
    uv pip install --python "$VENV_PATH/bin/python" "flatagents"
fi

# 3. Ensure data directory exists
mkdir -p "$SCRIPT_DIR/data"

# 4. Run the Demo
echo "🚀 Running demo (mode: $DEMO_MODE)..."
echo "---"

case $DEMO_MODE in
    seed)
        "$VENV_PATH/bin/python" seed_jobs.py --count "$JOB_COUNT"
        ;;
    checker)
        "$VENV_PATH/bin/python" run_checker.py --max-workers "$MAX_WORKERS"
        ;;
    worker)
        "$VENV_PATH/bin/python" run_worker.py
        ;;
    reaper)
        "$VENV_PATH/bin/python" run_reaper.py
        ;;
    all)
        echo "📋 Step 1: Seeding $JOB_COUNT jobs..."
        "$VENV_PATH/bin/python" seed_jobs.py --count "$JOB_COUNT"
        echo ""
        echo "📋 Step 2: Running checker (max $MAX_WORKERS workers)..."
        "$VENV_PATH/bin/python" run_checker.py --max-workers "$MAX_WORKERS"
        echo ""
        echo "📋 Step 3: Running a single worker..."
        "$VENV_PATH/bin/python" run_worker.py
        echo ""
        echo "📋 Step 4: Running reaper..."
        "$VENV_PATH/bin/python" run_reaper.py
        ;;
esac

echo "---"
echo "✅ Demo complete!"
