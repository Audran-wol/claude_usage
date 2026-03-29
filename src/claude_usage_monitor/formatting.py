"""Formatting helpers for the statusline."""

from .colors import D, N, G, R, color_pct


def compact(n: float) -> str:
    """Compact number: 1234 -> 1.2k, 1234567 -> 1.2m."""
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m".replace(".0m", "m")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(int(n))


def format_duration(ms: int) -> str:
    """Format milliseconds to human-readable duration."""
    if ms >= 3_600_000:
        return f"{ms // 3_600_000}h{(ms // 60_000) % 60}m"
    if ms >= 60_000:
        return f"{ms // 60_000}m{(ms // 1000) % 60}s"
    return f"{ms // 1000}s"


def format_reset(minutes: int | None) -> str:
    """Format reset countdown."""
    if minutes is None:
        return ""
    m = int(minutes)
    if m >= 1440:
        return f" {D}({m // 1440}d){N}"
    if m >= 60:
        return f" {D}({m // 60}h){N}"
    return f" {D}({m}m){N}"


def format_time_remaining(minutes: float | None) -> str:
    """Format projected time remaining to a readable string."""
    if minutes is None or minutes < 0:
        return "??"
    m = int(minutes)
    if m >= 1440:
        return f"{m // 1440}d{(m % 1440) // 60}h"
    if m >= 60:
        return f"{m // 60}h{m % 60}m"
    return f"{m}m"


def used_pct_str(used_pct, show_remaining: bool = False) -> str:
    """Format used or remaining % with color."""
    if used_pct is None or used_pct == "--":
        return "--"
    used = int(used_pct)
    c = color_pct(used)
    val = 100 - used if show_remaining else used
    return f"{c}{val}%{N}"


def pace_indicator(used_pct, remain_min, window_min: int) -> str:
    """Show pace: positive = ahead (green), negative = over pace (red). Suppress within +/-10%."""
    if used_pct is None or remain_min is None:
        return ""
    try:
        used = int(used_pct)
        rmin = int(remain_min)
    except (ValueError, TypeError):
        return ""
    if rmin > window_min:
        return ""
    elapsed = window_min - rmin
    if elapsed <= 0:
        return ""
    expected = (elapsed * 100) // window_min
    delta = expected - used
    if delta > 10:
        return f" {G}+{delta}%{N}"
    if delta < -10:
        return f" {R}{delta}%{N}"
    return ""
