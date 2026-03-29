#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALL_PY = ROOT / "install.py"
INSTALL_SH = ROOT / "install.sh"
INSTALL_PS1 = ROOT / "install.ps1"
STATUSLINE_PY = ROOT / "statusline.py"
STATUSLINE_SH = ROOT / "statusline.sh"
STATUSLINE_CMD = ROOT / "statusline.cmd"


def run(command, stdin_text=""):
    env = os.environ.copy()
    env["CQB_TOKENS"] = "0"
    env["CQB_RESET"] = "0"
    env["CQB_DURATION"] = "0"
    env["CQB_BRANCH"] = "0"
    env["CQB_TRACK"] = "0"
    env["CQB_NOTIFY"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    proc = subprocess.run(
        command,
        input=stdin_text,
        capture_output=True,
        cwd=ROOT,
        env=env,
        timeout=20,
        encoding="utf-8",
        errors="replace",
    )
    return proc


def assert_ok(proc, label):
    if proc.returncode != 0:
        raise AssertionError(
            f"{label} failed\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def assert_contains(text, expected, label):
    if expected not in text:
        raise AssertionError(f"{label} missing {expected!r}\noutput:\n{text}")


def smoke_statusline_py():
    payload = {
        "model": {"display_name": "Opus"},
        "context_window": {
            "used_percentage": 25,
            "context_window_size": 200000,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        },
        "cost": {"total_cost_usd": 0, "total_duration_ms": 0},
        "workspace": {"project_dir": str(ROOT)},
    }
    proc = run([sys.executable, str(STATUSLINE_PY)], json.dumps(payload))
    assert_ok(proc, "statusline.py")
    assert_contains(proc.stdout, "Opus", "statusline.py")
    # Gauge renders filled/empty blocks — check for block chars (█ and ░)
    has_gauge = ("\u2588" in proc.stdout or "\u2591" in proc.stdout
                 or "█" in proc.stdout or "░" in proc.stdout)
    if not has_gauge:
        raise AssertionError(f"statusline.py missing gauge blocks\noutput:\n{proc.stdout}")


def smoke_empty_stdin():
    proc = run([sys.executable, str(STATUSLINE_PY)], "")
    assert_ok(proc, "statusline.py empty stdin")
    if proc.stdout.strip() != "Claude":
        raise AssertionError(f"unexpected empty-stdin output:\n{proc.stdout}")


def smoke_unix_launcher():
    if os.name == "nt":
        return
    bash = shutil_which("bash")
    if not bash:
        raise AssertionError("bash not found")
    proc = run([bash, str(STATUSLINE_SH)], "")
    assert_ok(proc, "statusline.sh")
    if proc.stdout.strip() != "Claude":
        raise AssertionError(f"unexpected statusline.sh output:\n{proc.stdout}")


def smoke_windows_launcher():
    if os.name != "nt":
        return
    proc = run(["cmd", "/c", str(STATUSLINE_CMD)], "")
    assert_ok(proc, "statusline.cmd")
    if proc.stdout.strip() != "Claude":
        raise AssertionError(f"unexpected statusline.cmd output:\n{proc.stdout}")


def shutil_which(name):
    paths = os.environ.get("PATH", "").split(os.pathsep)
    exts = [""]
    if os.name == "nt":
        exts = os.environ.get("PATHEXT", ".EXE").split(os.pathsep)
    for directory in paths:
        if not directory:
            continue
        for ext in exts:
            candidate = pathlib.Path(directory) / f"{name}{ext}"
            if candidate.exists():
                return str(candidate)
    return None


def smoke_installer():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        install_dir = tmp_path / "install-target"
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps({"theme": "dark", "statusLine": {"command": "old-command"}}, indent=2)
            + "\n",
            encoding="utf-8",
        )

        proc = subprocess.run(
            [
                sys.executable,
                str(INSTALL_PY),
                "--source-dir",
                str(ROOT),
                "--install-dir",
                str(install_dir),
                "--settings-path",
                str(settings_path),
            ],
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=30,
        )
        assert_ok(proc, "install.py")

        for filename in ("statusline.py", "statusline.sh", "statusline.cmd"):
            if not (install_dir / filename).exists():
                raise AssertionError(f"install.py did not copy {filename}")

        # Check that src/ package was copied
        if not (install_dir / "src" / "claude_usage_monitor" / "__init__.py").exists():
            raise AssertionError("install.py did not copy src/ package")

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        if settings.get("theme") != "dark":
            raise AssertionError("install.py did not preserve existing settings")

        command = settings.get("statusLine", {}).get("command", "")
        expected_fragment = "statusline.cmd" if os.name == "nt" else "statusline.sh"
        if expected_fragment not in command:
            raise AssertionError(f"unexpected installed command: {command}")

        backup_path = settings_path.with_suffix(".json.bak")
        if not backup_path.exists():
            raise AssertionError("install.py did not create a settings backup")


def smoke_tracker():
    """Test the SQLite tracker module."""
    sys.path.insert(0, str(ROOT / "src"))
    from claude_usage_monitor.data.tracker import UsageTracker

    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test.db"
        tracker = UsageTracker(db_path)

        tracker.log_snapshot(
            model="Opus",
            input_tokens=5000,
            output_tokens=2000,
            cost_usd=0.15,
            five_hour_pct=42.0,
            seven_day_pct=12.0,
            session_duration_ms=300000,
            project_name="test-project",
            project_dir="/tmp/test",
        )

        stats = tracker.get_session_stats(7)
        if stats.get("total_snapshots", 0) != 1:
            raise AssertionError(f"expected 1 snapshot, got {stats}")

        daily = tracker.get_daily_summary(7)
        if len(daily) != 1:
            raise AssertionError(f"expected 1 daily entry, got {len(daily)}")

        snapshots = tracker.get_all_snapshots_json(7)
        if len(snapshots) != 1:
            raise AssertionError(f"expected 1 snapshot in JSON, got {len(snapshots)}")
        if snapshots[0]["model"] != "Opus":
            raise AssertionError(f"unexpected model: {snapshots[0]['model']}")

        tracker.close()


def smoke_predictions():
    """Test prediction functions."""
    sys.path.insert(0, str(ROOT / "src"))
    from claude_usage_monitor.predictions import (
        estimate_messages_remaining,
        estimate_time_to_empty,
        estimate_decay_time,
    )

    msgs = estimate_messages_remaining(50.0, 10000, 5000, 600000)
    if msgs is None or msgs <= 0:
        raise AssertionError(f"expected positive messages remaining, got {msgs}")

    tte = estimate_time_to_empty(50.0, 600000)
    if tte is None or tte <= 0:
        raise AssertionError(f"expected positive time to empty, got {tte}")

    # Decay with no input
    decay = estimate_decay_time(None)
    if decay is not None:
        raise AssertionError(f"expected None for no input, got {decay}")


def smoke_unix_install_wrapper():
    if os.name == "nt":
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        install_dir = tmp_path / "install-target"
        settings_path = tmp_path / "settings.json"
        proc = subprocess.run(
            [
                "bash",
                str(INSTALL_SH),
                "--skip-verify",
                "--install-dir",
                str(install_dir),
                "--settings-path",
                str(settings_path),
            ],
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=30,
        )
        assert_ok(proc, "install.sh")

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        command = settings.get("statusLine", {}).get("command", "")
        if "statusline.sh" not in command:
            raise AssertionError(f"unexpected install.sh command: {command}")


def smoke_windows_install_wrapper():
    if os.name != "nt":
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        install_dir = tmp_path / "install-target"
        settings_path = tmp_path / "settings.json"
        proc = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(INSTALL_PS1),
                "-SkipVerify",
                "-InstallDir",
                str(install_dir),
                "-SettingsPath",
                str(settings_path),
            ],
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=30,
        )
        assert_ok(proc, "install.ps1")

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        command = settings.get("statusLine", {}).get("command", "")
        if "statusline.cmd" not in command:
            raise AssertionError(f"unexpected install.ps1 command: {command}")


def smoke_cli_stats():
    """Test --stats with empty database."""
    env = os.environ.copy()
    env["CQB_TRACK"] = "0"
    proc = subprocess.run(
        [sys.executable, str(STATUSLINE_PY), "--stats", "--days", "1"],
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=env,
        timeout=20,
    )
    assert_ok(proc, "--stats")
    assert_contains(proc.stdout, "Statistics", "--stats output")


def main():
    smoke_statusline_py()
    smoke_empty_stdin()
    smoke_unix_launcher()
    smoke_windows_launcher()
    smoke_predictions()
    smoke_tracker()
    smoke_installer()
    smoke_cli_stats()
    smoke_unix_install_wrapper()
    smoke_windows_install_wrapper()
    print("smoke tests passed")


if __name__ == "__main__":
    main()
