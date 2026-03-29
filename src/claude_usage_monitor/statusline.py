#!/usr/bin/env python3
"""
Claude Code statusline with 5h/7d quota tracking, predictions, and historical logging.

Custom statusline with 256-color scheme, usage bar, and prediction engine.
"""

import json
import os
import subprocess
import sys

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from .colors import CYAN, TEAL, ORANGE, MAGENTA, SLATE, PEACH, WHITE, B, D, N, color_pct
from .formatting import (
    compact, format_duration, format_reset, format_time_remaining,
    used_pct_str, pace_indicator,
)
from .quota import read_cached_usage, join_fetch_thread
from .notifications import check_and_notify
from .predictions import estimate_messages_remaining, estimate_time_to_empty, estimate_decay_time
from .data import UsageTracker

# ── Configuration (env vars) ─────────────────────────────────────
SHOW_CONTEXT_SIZE = os.environ.get("CQB_CONTEXT_SIZE", "0") == "1"
SHOW_TOKENS = os.environ.get("CQB_TOKENS", "1") == "1"
SHOW_PACE = os.environ.get("CQB_PACE", "0") == "1"
SHOW_RESET = os.environ.get("CQB_RESET", "1") == "1"
SHOW_DURATION = os.environ.get("CQB_DURATION", "1") == "1"
SHOW_BRANCH = os.environ.get("CQB_BRANCH", "1") == "1"
SHOW_COST = os.environ.get("CQB_COST", "0") == "1"
SHOW_REMAINING = os.environ.get("CQB_REMAINING", "0") == "1"
SHOW_MSGS_LEFT = os.environ.get("CQB_MSGS_LEFT", "0") == "1"
SHOW_TIME_EMPTY = os.environ.get("CQB_TIME_EMPTY", "0") == "1"
SHOW_DECAY = os.environ.get("CQB_DECAY", "0") == "1"
ENABLE_TRACKING = os.environ.get("CQB_TRACK", "0") == "1"

# ── Visual identity ──────────────────────────────────────────────
SEP = f"  {SLATE}\u00b7{N}  "      # spaced middle dot:  ·
ICON = "\u25b8"                      # ▸ right-pointing triangle
GAUGE_FILL = "\u2588"               # █ full block
GAUGE_EMPTY = "\u2591"              # ░ light shade

# ── Error state labels ────────────────────────────────────────────
ERROR_LABELS = {
    "auth_expired": f"{MAGENTA}auth expired{N}",
    "offline": f"{ORANGE}offline{N}",
    "rate_limited": f"{ORANGE}rate limited{N}",
    "api_error": f"{MAGENTA}api error{N}",
    "unknown_error": f"{MAGENTA}error{N}",
}


def _build_gauge(used_pct: int, width: int = 14) -> str:
    """Build a usage bar: filled = consumed, empty = remaining.

    Color of filled portion: teal <50%, orange 50-75%, magenta >75%.
    """
    clamped = min(100, max(0, used_pct))
    filled = round(clamped / 100.0 * width)
    if clamped >= 75:
        color = MAGENTA
    elif clamped >= 50:
        color = ORANGE
    else:
        color = TEAL
    return f"{color}{GAUGE_FILL * filled}{SLATE}{GAUGE_EMPTY * (width - filled)}{N}"


def run() -> None:
    """Main statusline entry point."""
    raw = sys.stdin.read().strip()
    if not raw:
        print("Claude")
        sys.exit(0)

    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        print("Claude")
        sys.exit(0)

    # ── Parse session data ──────────────────────────────────────
    model = "Opus"
    try:
        model = d["model"]["display_name"]
    except (KeyError, TypeError):
        pass

    ctx_pct_used = 0
    ctx_size = 0
    try:
        ctx_pct_used = int(d["context_window"]["used_percentage"] or 0)
        ctx_size = int(d["context_window"]["context_window_size"] or 0)
    except (KeyError, TypeError, ValueError):
        pass

    in_tok = 0
    out_tok = 0
    try:
        in_tok = d["context_window"]["total_input_tokens"] or 0
    except (KeyError, TypeError):
        pass
    try:
        out_tok = d["context_window"]["total_output_tokens"] or 0
    except (KeyError, TypeError):
        pass

    cost_usd = 0.0
    duration_ms = 0
    try:
        cost_usd = float(d["cost"]["total_cost_usd"] or 0)
    except (KeyError, TypeError, ValueError):
        pass
    try:
        duration_ms = int(d["cost"]["total_duration_ms"] or 0)
    except (KeyError, TypeError, ValueError):
        pass

    proj_dir = ""
    proj_name = ""
    try:
        proj_dir = d["workspace"]["project_dir"] or ""
        proj_name = os.path.basename(proj_dir)
    except (KeyError, TypeError):
        pass

    # ── Git branch ──────────────────────────────────────────────
    branch = ""
    cwd = os.getcwd()
    candidate_dirs = []
    if proj_dir:
        candidate_dirs.append(proj_dir)
    if cwd and cwd not in candidate_dirs:
        candidate_dirs.append(cwd)

    for try_dir in candidate_dirs:
        if not try_dir:
            continue
        try:
            r = subprocess.run(
                ["git", "-C", try_dir, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=2,
            )
            if r.returncode == 0:
                branch = r.stdout.strip()
                if not proj_name:
                    proj_name = os.path.basename(try_dir)
                break
        except Exception:
            pass

    # ── Context size label ──────────────────────────────────────
    if ctx_size >= 1_000_000:
        ctx_label = f"{ctx_size // 1_000_000}M"
    else:
        ctx_label = f"{ctx_size // 1000}K"

    ctx_remaining = 100 - ctx_pct_used

    # ── Fetch quota ─────────────────────────────────────────────
    usage = read_cached_usage()
    u5_val = None
    u7_val = None

    # ── LINE 1: Bar leads, then quota numbers, then model/branch ──
    line1_parts = []

    # Context usage bar (the visual anchor — shows USED, not remaining)
    gauge = _build_gauge(ctx_pct_used)
    line1_parts.append(gauge)

    # Quota numbers
    if usage:
        error = usage.get("error")
        u5 = usage["u5"]
        u7 = usage["u7"]
        u5_val = u5
        u7_val = u7
        r5 = usage["r5"]
        r7 = usage["r7"]

        if error and u5 is None:
            error_label = ERROR_LABELS.get(error, f"{MAGENTA}error{N}")
            line1_parts.append(f"{B}5h{N} {error_label}")
            line1_parts.append(f"{B}7d{N} {error_label}")
        else:
            pace5 = pace_indicator(u5, r5, 300) if SHOW_PACE else ""
            pace7 = pace_indicator(u7, r7, 10080) if SHOW_PACE else ""
            reset5 = format_reset(r5) if SHOW_RESET else ""
            reset7 = format_reset(r7) if (SHOW_RESET and u7 is not None and int(u7) >= 70) else ""

            line1_parts.append(f"{B}5h{N} {used_pct_str(u5, SHOW_REMAINING)}{pace5}{reset5}")
            line1_parts.append(f"{B}7d{N} {used_pct_str(u7, SHOW_REMAINING)}{pace7}{reset7}")

            # Extra usage
            if usage["extra_enabled"] and u5 is not None and int(u5) >= 80:
                eu = int(usage["extra_used"])
                el = int(usage["extra_limit"])
                line1_parts.append(f"{PEACH}${eu / 100:.2f}/{el / 100:.2f}{N}")

        check_and_notify(u5_val, u7_val)
    else:
        line1_parts.append(f"{B}5h{N} {SLATE}--{N}")
        line1_parts.append(f"{B}7d{N} {SLATE}--{N}")

    # Model + project (end of line)
    model_str = f"{CYAN}{ICON} {model}{N}"
    if proj_name:
        loc = f"{proj_name}/{branch}" if (branch and SHOW_BRANCH) else proj_name
        if len(loc) > 30:
            loc = loc[:29] + "\u2026"
        model_str += f" {SLATE}{loc}{N}"
    line1_parts.append(model_str)

    line1 = SEP.join(line1_parts)

    # ── LINE 2: Tokens, predictions, cost, duration ─────────────
    line2_parts = []

    # Token counts
    if SHOW_TOKENS and (in_tok or out_tok):
        line2_parts.append(f"{PEACH}\u2191{N}{compact(in_tok)} {CYAN}\u2193{N}{compact(out_tok)}")

    # Prediction segments
    if usage and not (usage.get("error") and u5_val is None):
        if SHOW_MSGS_LEFT and u5_val is not None:
            msgs = estimate_messages_remaining(u5_val, in_tok, out_tok, duration_ms)
            if msgs is not None:
                line2_parts.append(f"{SLATE}~{msgs}msg left{N}")

        if SHOW_TIME_EMPTY and u5_val is not None:
            tte = estimate_time_to_empty(u5_val, duration_ms)
            if tte is not None:
                line2_parts.append(f"{SLATE}empty in {format_time_remaining(tte)}{N}")

        if SHOW_DECAY:
            decay = estimate_decay_time(usage.get("five_hour_resets_at"))
            if decay:
                line2_parts.append(f"{TEAL}{decay}{N}")

        # Error badge (small, alongside valid data)
        error = usage.get("error")
        if error:
            error_label = ERROR_LABELS.get(error, f"{MAGENTA}!{N}")
            line2_parts.append(error_label)

    # Cost
    if SHOW_COST and cost_usd > 0:
        line2_parts.append(f"{ORANGE}${cost_usd:.2f}{N}")

    # Duration
    if SHOW_DURATION:
        line2_parts.append(f"{SLATE}{format_duration(duration_ms)}{N}")

    line2 = SEP.join(line2_parts)

    print(line1)
    if line2:
        print(line2)

    # ── Historical tracking ─────────────────────────────────────
    if ENABLE_TRACKING:
        try:
            tracker = UsageTracker()
            tracker.log_snapshot(
                model=model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=cost_usd,
                five_hour_pct=u5_val,
                seven_day_pct=u7_val,
                session_duration_ms=duration_ms,
                project_name=proj_name,
                project_dir=proj_dir,
                context_used_pct=ctx_pct_used,
                context_window_size=ctx_size,
            )
            tracker.close()
        except Exception:
            pass

    # Wait for background fetch to finish so cache gets written
    join_fetch_thread()
