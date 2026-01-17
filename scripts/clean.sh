#!/bin/bash
# Clean node_modules and .venv directories (skips nested)
# Usage: ./scripts/clean [--yes]
set -e

echo "Finding directories to clean..."
find . -type d \( -name "node_modules" -o -name ".venv" \) -prune -not -path "./.git/*" | while read -r dir; do
    echo "  $dir ($(du -sh "$dir" 2>/dev/null | cut -f1))"
done

if [ "$1" = "--yes" ]; then
    find . -type d \( -name "node_modules" -o -name ".venv" \) -prune -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
    echo "Done."
else
    echo ""
    echo "Dry run. Use --yes to delete."
fi
