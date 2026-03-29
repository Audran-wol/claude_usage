"""Usage predictions: messages remaining, time to empty, rate limit decay."""

from datetime import datetime, timezone


def estimate_messages_remaining(
    used_pct: float | None,
    in_tokens: int,
    out_tokens: int,
    duration_ms: int,
) -> int | None:
    """Estimate how many messages remain based on average tokens per message.

    Uses total tokens consumed and current usage % to project remaining capacity.
    """
    if used_pct is None or used_pct <= 0:
        return None
    total_tokens = in_tokens + out_tokens
    if total_tokens <= 0 or duration_ms <= 0:
        return None

    used = float(used_pct)
    remaining_pct = 100.0 - used
    if remaining_pct <= 0:
        return 0

    # Estimate: if used% consumed total_tokens, then remaining% can consume proportionally
    tokens_per_pct = total_tokens / used
    remaining_tokens = tokens_per_pct * remaining_pct

    # Rough estimate: ~4000 tokens per message (input+output combined average)
    avg_tokens_per_msg = max(1000, total_tokens / max(1, duration_ms / 30000))
    return max(0, int(remaining_tokens / avg_tokens_per_msg))


def estimate_time_to_empty(
    used_pct: float | None,
    duration_ms: int,
) -> float | None:
    """Estimate minutes until quota is exhausted based on current burn rate.

    Returns minutes remaining, or None if not enough data.
    """
    if used_pct is None or used_pct <= 0 or duration_ms <= 0:
        return None

    used = float(used_pct)
    remaining_pct = 100.0 - used
    if remaining_pct <= 0:
        return 0.0

    duration_min = duration_ms / 60000.0
    if duration_min < 0.5:
        return None  # Not enough data yet

    burn_rate = used / duration_min  # percent per minute
    if burn_rate <= 0:
        return None

    return remaining_pct / burn_rate


def estimate_decay_time(resets_at_iso: str | None) -> str | None:
    """Predict when usage will start dropping as the 5h rolling window advances.

    The 5h window is rolling, so the earliest usage in the window will drop off first.
    Returns a human-readable string like "drops in 45m" or None.
    """
    if not resets_at_iso:
        return None
    try:
        iso = resets_at_iso.replace("+00:00", "+0000").replace("Z", "+0000")
        if "." in iso:
            base, rest = iso.split(".", 1)
            tz_part = ""
            for sep in ["+", "-"]:
                if sep in rest:
                    idx = rest.index(sep)
                    tz_part = rest[idx:]
                    break
            iso = base + tz_part
        reset_dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.now(timezone.utc)
        diff_min = (reset_dt - now).total_seconds() / 60

        if diff_min <= 0:
            return "dropping now"
        if diff_min < 60:
            return f"drops in {int(diff_min)}m"
        if diff_min < 300:
            return f"drops in {int(diff_min // 60)}h{int(diff_min % 60)}m"
        return None
    except Exception:
        return None
