#!/usr/bin/env bash
# Launcher for Claude usage monitor
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
  PYTHONIOENCODING=utf-8 python3 "$SCRIPT_DIR/statusline.py"
elif command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
  PYTHONIOENCODING=utf-8 python "$SCRIPT_DIR/statusline.py"
elif command -v py >/dev/null 2>&1 && py -3 -c "import sys" >/dev/null 2>&1; then
  PYTHONIOENCODING=utf-8 py -3 "$SCRIPT_DIR/statusline.py"
else
  echo "Claude"
  exit 0
fi
