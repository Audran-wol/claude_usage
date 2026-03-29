"""CLI entry point with --stats and --json support."""

import argparse
import json
import sys

from .data import UsageTracker
from .formatting import compact, format_duration
from .colors import C, G, Y, R, D, B, N


def print_stats(days: int = 30) -> None:
    """Print a usage summary to stdout."""
    tracker = UsageTracker()

    print(f"\n{B}{C}Claude Usage Monitor — Statistics{N}")
    print(f"{D}{'─' * 50}{N}\n")

    # Overall stats
    stats = tracker.get_session_stats(days)
    if not stats.get("total_snapshots"):
        print(f"  {Y}No data yet.{N} Enable tracking with CQB_TRACK=1")
        print(f"  in your shell profile or Claude Code settings.\n")
        tracker.close()
        return

    print(f"  {B}Overall ({days}d){N}")
    print(f"  Active days:    {stats.get('active_days', 0)}")
    print(f"  Projects:       {stats.get('total_projects', 0)}")
    print(f"  Peak 5h usage:  {_color_val(stats.get('peak_5h_pct'))}")
    print(f"  Peak 7d usage:  {_color_val(stats.get('peak_7d_pct'))}")
    print(f"  Times over 80%: {stats.get('times_over_80', 0)}")
    avg_dur = stats.get("avg_duration_ms")
    if avg_dur:
        print(f"  Avg session:    {format_duration(int(avg_dur))}")
    print()

    # Daily summary
    daily = tracker.get_daily_summary(min(days, 14))
    if daily:
        print(f"  {B}Daily Summary{N}")
        print(f"  {'Date':<12} {'5h Peak':>8} {'7d Peak':>8} {'Projects':>9}")
        print(f"  {'─' * 12} {'─' * 8} {'─' * 8} {'─' * 9}")
        for row in daily[:10]:
            day = row.get("day", "?")
            p5 = _color_val(row.get("peak_5h_pct"))
            p7 = _color_val(row.get("peak_7d_pct"))
            projs = row.get("projects_count", 0)
            print(f"  {day:<12} {p5:>18} {p7:>18} {projs:>9}")
        print()

    # Project stats
    projects = tracker.get_project_stats(days)
    if projects:
        print(f"  {B}Top Projects (by cost){N}")
        print(f"  {'Project':<25} {'Cost':>8} {'Peak 5h':>8} {'Avg Session':>12}")
        print(f"  {'─' * 25} {'─' * 8} {'─' * 8} {'─' * 12}")
        for row in projects[:10]:
            name = row.get("project_name", "?")
            if len(name) > 24:
                name = name[:23] + "…"
            cost = f"${row.get('max_cost_usd', 0):.2f}"
            p5 = _color_val(row.get("peak_5h_pct"))
            avg_d = format_duration(int(row.get("avg_duration_ms", 0)))
            print(f"  {name:<25} {cost:>8} {p5:>18} {avg_d:>12}")
        print()

    tracker.close()


def print_json(days: int = 7) -> None:
    """Print raw snapshots as JSON."""
    tracker = UsageTracker()
    snapshots = tracker.get_all_snapshots_json(days)
    tracker.close()
    json.dump(snapshots, sys.stdout, indent=2)
    print()


def _color_val(pct) -> str:
    """Color a percentage value."""
    if pct is None:
        return f"{D}--{N}"
    p = int(pct)
    if p >= 90:
        return f"{R}{p}%{N}"
    if p >= 70:
        return f"{Y}{p}%{N}"
    return f"{G}{p}%{N}"


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="my-claude-monitor",
        description="Claude Code usage monitor with historical tracking.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print usage summary (daily/weekly, top projects, session averages).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Export raw usage snapshots as JSON.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to include in stats/json output (default: 30).",
    )

    args = parser.parse_args()

    if args.stats:
        print_stats(args.days)
        return 0

    if args.json:
        print_json(args.days)
        return 0

    # Default: run statusline (reads from stdin)
    from .statusline import run
    run()
    return 0
