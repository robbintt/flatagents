#!/bin/bash
# Clean node_modules and .venv directories (skips nested)
# Usage: ./scripts/clean [--yes]
set -e

echo "Finding directories to clean..."
find . -path "./.git" -prune -o -type d \( -name "node_modules" -o -name ".venv" \) -print | while read -r dir; do
    echo "  $dir ($(du -sh "$dir" 2>/dev/null | cut -f1))"
done

if [ "$1" = "--yes" ]; then
    find . -path "./.git" -prune -o -type d \( -name "node_modules" -o -name ".venv" \) -print -exec rm -rf {} +
    echo "Done."
else
    echo ""
    echo "Dry run. Use --yes to delete."
fi
