"""ANSI 256-color scheme and helpers."""

# 256-color codes for a cyan/orange/magenta identity
CYAN = "\033[38;5;81m"      # bright sky blue
ORANGE = "\033[38;5;208m"   # vivid orange (warning)
MAGENTA = "\033[38;5;170m"  # soft magenta (critical)
TEAL = "\033[38;5;73m"      # muted teal (good)
SLATE = "\033[38;5;245m"    # gray for dim/secondary
PEACH = "\033[38;5;216m"    # peach accent
WHITE = "\033[38;5;255m"    # bright white
B = "\033[1m"               # bold
D = "\033[2m"               # dim
N = "\033[0m"               # reset

# Legacy aliases used by formatting.py
G = TEAL      # good
Y = ORANGE    # warning
R = MAGENTA   # critical
C = CYAN      # accent


def color_pct(used_pct: float) -> str:
    """Color based on how much quota is USED (high = bad)."""
    if used_pct >= 90:
        return MAGENTA
    if used_pct >= 70:
        return ORANGE
    return TEAL
