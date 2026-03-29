"""Desktop notifications at configurable thresholds using platform-native methods."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


# Notification state file to avoid spamming
_NOTIF_STATE_FILE = os.path.join(tempfile.gettempdir(), "claude-sl-notif-state.json")

# Default thresholds (configurable via env)
def _get_thresholds() -> list[int]:
    raw = os.environ.get("CQB_NOTIFY_THRESHOLDS", "80,90,95")
    try:
        return sorted(int(x.strip()) for x in raw.split(",") if x.strip())
    except ValueError:
        return [80, 90, 95]


def _load_notif_state() -> dict:
    try:
        if os.path.exists(_NOTIF_STATE_FILE):
            with open(_NOTIF_STATE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_notif_state(state: dict) -> None:
    try:
        with open(_NOTIF_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def _send_notification(title: str, message: str) -> None:
    """Send a desktop notification using platform-native methods."""
    try:
        if sys.platform == "darwin":
            subprocess.run(
                ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
                capture_output=True, timeout=5,
            )
        elif sys.platform == "win32":
            # Use PowerShell toast notification
            ps_script = (
                f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, '
                f'ContentType = WindowsRuntime] > $null; '
                f'$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent('
                f'[Windows.UI.Notifications.ToastTemplateType]::ToastText02); '
                f'$textNodes = $template.GetElementsByTagName("text"); '
                f'$textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null; '
                f'$textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null; '
                f'$toast = [Windows.UI.Notifications.ToastNotification]::new($template); '
                f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Claude Code").Show($toast)'
            )
            subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                capture_output=True, timeout=10,
            )
        else:
            # Linux: try notify-send
            subprocess.run(
                ["notify-send", title, message, "--icon=dialog-warning", "--urgency=normal"],
                capture_output=True, timeout=5,
            )
    except Exception:
        pass


def check_and_notify(u5: float | None, u7: float | None) -> None:
    """Check usage against thresholds and send notifications if needed.

    Notifications are sent once per threshold crossing per 5-hour window.
    """
    enabled = os.environ.get("CQB_NOTIFY", "0") == "1"
    if not enabled:
        return

    thresholds = _get_thresholds()
    state = _load_notif_state()
    now = time.time()
    changed = False

    # Reset state if it's been more than 5 hours since last notification
    last_reset = state.get("last_reset", 0)
    if now - last_reset > 18000:  # 5 hours
        state = {"last_reset": now}
        changed = True

    for label, used_pct, window_name in [("5h", u5, "5-hour"), ("7d", u7, "7-day")]:
        if used_pct is None:
            continue
        used = int(used_pct)
        notified_key = f"notified_{label}"
        already_notified = state.get(notified_key, [])

        for threshold in thresholds:
            if used >= threshold and threshold not in already_notified:
                severity = "Warning" if threshold < 90 else "Critical" if threshold < 95 else "LIMIT"
                _send_notification(
                    f"Claude {severity}: {window_name} at {used}%",
                    f"Your {window_name} quota is at {used}% usage. "
                    f"{'Consider slowing down.' if threshold < 95 else 'You may hit the rate limit soon.'}"
                )
                already_notified.append(threshold)
                state[notified_key] = already_notified
                changed = True

    if changed:
        _save_notif_state(state)
