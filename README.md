# my-claude-monitor

> Real-time Claude Code usage monitor — see your quota burn in the terminal.

```
██░░░░░░░░░░░░  ·  5h 14% (4h)  ·  7d 30%  ·  ▸ Opus my-project/main
↑12k ↓4k  ·  ~380msg left  ·  10m0s
```
```
████████░░░░░░  ·  5h 55% (2h)  ·  7d 60%  ·  ▸ Opus my-project/main
↑80k ↓25k  ·  ~120msg left  ·  empty in 2h  ·  25m0s
```
```
████████████░░  ·  5h 92% (28m)  ·  7d 78%  ·  ▸ Opus my-project/main
↑160k ↓48k  ·  ~15msg left  ·  empty in 12m  ·  resets 28m  ·  50m0s
```

The bar fills as you burn context. Teal when you're fine. Orange past halfway. Magenta when it's time to slow down.

No API keys. No dependencies. No telemetry. Reads your existing Claude Code session and shows what matters.

---

## Install

**PowerShell:**
```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Audran-wol/claude_usage/main/install.ps1)))
```

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/Audran-wol/claude_usage/main/install.sh | bash
```

**Manual:**
```bash
git clone https://github.com/Audran-wol/claude_usage.git
cd claude_usage
python install.py
```

Restart Claude Code after installing. The installer registers the statusline automatically.

---

## Segments

| Segment | Example | What it means |
|---|---|---|
| Usage bar | `████████░░░░░░` | Context consumed — filled = used, empty = remaining |
| 5h quota | `5h 42% (2h)` | 5-hour rolling window with reset countdown |
| 7d quota | `7d 58%` | 7-day rolling window |
| Model | `▸ Opus` | Active model |
| Branch | `project/main` | Git branch |
| Tokens | `↑95k ↓30k` | Input/output this session |
| Messages left | `~120msg left` | Estimated messages at current burn rate |
| Time to empty | `empty in 1h` | When quota runs out at this pace |
| Decay | `drops in 45m` | When the 5h window starts freeing up |
| Cost | `$1.85` | Session cost |
| Duration | `30m0s` | Session length |
| Pace | `-19%` | Over/under expected rate |

Colors: **teal** = under 50% bar / 70% quota. **Orange** = 50-75% bar / 70-90% quota. **Magenta** = over 75% bar / 90% quota.

Error states show `auth expired`, `offline`, or `rate limited` instead of blank dashes.

---

<details>
<summary><strong>Configuration</strong></summary>

Set in your shell profile or `~/.claude/settings.json`:

```json
{
  "env": {
    "CQB_MSGS_LEFT": "1",
    "CQB_TIME_EMPTY": "1",
    "CQB_DECAY": "1",
    "CQB_COST": "1",
    "CQB_TRACK": "1"
  }
}
```

### Display

| Variable | Default | What it does |
|---|---|---|
| `CQB_TOKENS` | `1` | Token counts |
| `CQB_RESET` | `1` | Reset countdowns |
| `CQB_DURATION` | `1` | Session duration |
| `CQB_BRANCH` | `1` | Git branch |
| `CQB_COST` | `0` | Session cost |
| `CQB_CONTEXT_SIZE` | `0` | Context size label |
| `CQB_PACE` | `0` | Pace indicator |
| `CQB_REMAINING` | `0` | Show remaining% instead of used% |

### Predictions

| Variable | Default | What it does |
|---|---|---|
| `CQB_MSGS_LEFT` | `0` | Estimated messages remaining |
| `CQB_TIME_EMPTY` | `0` | Time until quota empty |
| `CQB_DECAY` | `0` | When usage starts dropping |

### Notifications

| Variable | Default | What it does |
|---|---|---|
| `CQB_NOTIFY` | `0` | Desktop alerts at quota thresholds |
| `CQB_NOTIFY_THRESHOLDS` | `80,90,95` | Alert thresholds (comma-separated) |

Platform-native: Windows toast, macOS osascript, Linux notify-send. Fires once per threshold per 5h window.

### Tracking

| Variable | Default | What it does |
|---|---|---|
| `CQB_TRACK` | `0` | Log snapshots to SQLite |

Logs to `~/.claude/plugins/my-claude-monitor/usage_history.db`.

</details>

<details>
<summary><strong>CLI commands</strong></summary>

### Stats

```bash
python statusline.py --stats           # Last 30 days
python statusline.py --stats --days 7  # Last week
```

Active days, peak usage, top projects by cost, daily breakdown.

### JSON export

```bash
python statusline.py --json --days 7
python statusline.py --json | jq '.[] | select(.five_hour_pct > 80)'
```

Raw snapshots for piping to other tools.

</details>

<details>
<summary><strong>Security</strong></summary>

**Reads:** stdin from Claude Code, `~/.claude/.credentials.json` for OAuth, `git rev-parse` for branch.

**Writes:** cache files in system temp dir, SQLite db only if `CQB_TRACK=1`.

**Network:** one HTTPS call to `api.anthropic.com/api/oauth/usage`, cached 5 minutes.

Nothing else. No telemetry. No analytics.

</details>

<details>
<summary><strong>Project structure</strong></summary>

```
claude_usage/
├── src/claude_usage_monitor/
│   ├── cli.py               # --stats, --json
│   ├── colors.py            # 256-color ANSI
│   ├── formatting.py        # Number/time helpers
│   ├── notifications.py     # Desktop alerts
│   ├── oauth.py             # Token retrieval
│   ├── predictions.py       # Burn rate projections
│   ├── quota.py             # API fetch + cache
│   ├── statusline.py        # Main renderer
│   └── data/tracker.py      # SQLite logger
├── statusline.py            # Root launcher
├── statusline.sh / .cmd     # Platform launchers
├── install.py / .sh / .ps1  # Installers
├── pyproject.toml           # Package config
└── tests/smoke_test.py
```

</details>

---

## Uninstall

1. Delete `~/.claude/plugins/my-claude-monitor/`
2. Remove `statusLine` from `~/.claude/settings.json`
3. Restart Claude Code

## Requirements

Python 3.10+ and [Claude Code](https://docs.anthropic.com/en/docs/claude-code) with an active subscription.

## License

MIT
