"""Quota API fetching and caching with error state tracking."""

import json
import os
import tempfile
import time
import threading
from datetime import datetime, timezone

from .oauth import get_oauth_token

CACHE_FILE = os.path.join(tempfile.gettempdir(), "claude-sl-usage.json")
CACHE_TTL = 300  # 5 minutes
LOCK_FILE = os.path.join(tempfile.gettempdir(), "claude-sl-usage.lock")

_fetch_thread: threading.Thread | None = None


def _parse_reset_minutes(iso_str: str | None) -> int | None:
    """Parse ISO timestamp to minutes from now."""
    if not iso_str:
        return None
    try:
        iso_str = iso_str.replace("+00:00", "+0000").replace("Z", "+0000")
        if "." in iso_str:
            base, rest = iso_str.split(".", 1)
            tz_part = ""
            for sep in ["+", "-"]:
                if sep in rest:
                    idx = rest.index(sep)
                    tz_part = rest[idx:]
                    break
            iso_str = base + tz_part
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S%z")
        now = datetime.now(timezone.utc)
        diff = (dt - now).total_seconds() / 60
        return max(0, int(diff))
    except Exception:
        return None


def fetch_usage_sync() -> None:
    """Call Anthropic usage API and write cache. Run in background thread."""
    try:
        token = get_oauth_token()
        if not token:
            _write_error_cache("auth_expired")
            return

        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                "anthropic-beta": "oauth-2025-04-20",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                _write_error_cache("auth_expired")
            elif e.code == 429:
                _write_error_cache("rate_limited")
            else:
                _write_error_cache("api_error")
            return
        except urllib.error.URLError:
            _write_error_cache("offline")
            return

        five_hour = data.get("five_hour", {})
        seven_day = data.get("seven_day", {})

        cache_data = {
            "five_hour_used": five_hour.get("utilization", 0),
            "seven_day_used": seven_day.get("utilization", 0),
            "five_hour_reset_min": _parse_reset_minutes(five_hour.get("resets_at")),
            "seven_day_reset_min": _parse_reset_minutes(seven_day.get("resets_at")),
            "five_hour_resets_at": five_hour.get("resets_at"),
            "extra_enabled": data.get("extra_usage", {}).get("is_enabled", False),
            "extra_used": data.get("extra_usage", {}).get("used_credits", 0),
            "extra_limit": data.get("extra_usage", {}).get("monthly_limit", 0),
            "fetched_at": time.time(),
            "error": None,
        }

        _write_cache(cache_data)

    except Exception:
        _write_error_cache("unknown_error")
    finally:
        try:
            os.unlink(LOCK_FILE)
        except OSError:
            pass


def _write_cache(data: dict) -> None:
    """Atomically write cache file."""
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, CACHE_FILE)


def _write_error_cache(error_type: str) -> None:
    """Write an error-only cache so the statusline can show the error state."""
    existing = _read_raw_cache()
    if existing:
        existing["error"] = error_type
        existing["fetched_at"] = time.time()
        _write_cache(existing)
    else:
        _write_cache({
            "error": error_type,
            "fetched_at": time.time(),
        })


def _read_raw_cache() -> dict | None:
    """Read raw cache file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def read_cached_usage() -> dict | None:
    """Read cached usage data, trigger background refresh if stale."""
    global _fetch_thread
    cache = _read_raw_cache()

    now = time.time()
    fetched_at = (cache or {}).get("fetched_at", 0)
    is_stale = (now - fetched_at) > CACHE_TTL

    if is_stale:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            t = threading.Thread(target=fetch_usage_sync)
            t.start()
            _fetch_thread = t
        except FileExistsError:
            try:
                lock_age = now - os.path.getmtime(LOCK_FILE)
                if lock_age > 30:
                    os.unlink(LOCK_FILE)
            except OSError:
                pass

    if cache:
        error = cache.get("error")
        elapsed_min = (now - cache.get("fetched_at", now)) / 60
        r5 = cache.get("five_hour_reset_min")
        r7 = cache.get("seven_day_reset_min")
        if r5 is not None:
            r5 = max(0, int(r5 - elapsed_min))
        if r7 is not None:
            r7 = max(0, int(r7 - elapsed_min))
        return {
            "u5": cache.get("five_hour_used"),
            "u7": cache.get("seven_day_used"),
            "r5": r5,
            "r7": r7,
            "five_hour_resets_at": cache.get("five_hour_resets_at"),
            "extra_enabled": cache.get("extra_enabled", False),
            "extra_used": cache.get("extra_used", 0),
            "extra_limit": cache.get("extra_limit", 0),
            "error": error,
        }

    return None


def join_fetch_thread(timeout: float = 8) -> None:
    """Wait for background fetch thread if active."""
    if _fetch_thread is not None:
        _fetch_thread.join(timeout=timeout)
