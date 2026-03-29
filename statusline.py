#!/usr/bin/env python3
"""
Claude Code statusline — thin launcher that delegates to the package.

This file stays at the root so existing install paths continue to work.
It adds src/ to sys.path so the package can be found without pip install.
"""

import os
import sys

# Add src/ to path so the package is importable without installation
_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Check for CLI flags before running statusline
if len(sys.argv) > 1:
    from claude_usage_monitor.cli import main
    raise SystemExit(main())

from claude_usage_monitor.statusline import run
run()
