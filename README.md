# my-claude-monitor

Real-time Claude Code usage monitor — see your quota burn in the terminal.

A statusline plugin for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that shows your 5-hour and 7-day quota usage, context window consumption, token counts, burn rate predictions, and desktop notifications — all directly in your terminal. No API keys, no dependencies, no telemetry. Runs entirely on your machine using only the Python standard library.

## How it looks

The usage bar fills up as you consume context. Color shifts from teal to orange to magenta as usage climbs.

**Healthy session** — barely started, plenty of room:
```
███░░░░░░░░░░░  ·  5h 14% (4h)  ·  7d 30%  ·  ▸ Opus my-project/main
↑25k ↓8k  ·  10m0s
```

**Moderate session** — past the halfway mark:
```
████████░░░░░░  ·  5h 55% (2h)  ·  7d 60%  ·  ▸ Opus my-project/main
↑80k ↓25k  ·  25m0s
```

**Critical session** — approaching the limit:
```
████████████░░  ·  5h 92% (45m)  ·  7d 78%  ·  ▸ Opus my-project/main
↑160k ↓48k  ·  ~8msg left  ·  empty in 12m  ·  drops in 45m  ·  $2.10  ·  50m0s
```

<p align="center">
  <img src="./assets/demo-animated.gif" alt="my-claude-monitor demo">
</p>

## Install

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/Audran-wol/my-claude-monitor/main/install.ps1 | iex
```

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/Audran-wol/my-claude-monitor/main/install.sh | bash
```

**Manual install:**
```bash
git clone https://github.com/Audran-wol/my-claude-monitor.git
cd my-claude-monitor
python install.py
```

The installer copies files to `~/.claude/plugins/claude-usage-monitor/`, updates `~/.claude/settings.json` to register the statusline, and verifies the launcher works. Restart Claude Code after installing.

## What it shows

| Segment | Example | Description |
|---|---|---|
| Usage bar | `████████░░░░░░` | Context window consumed — filled = used, empty = remaining |
| 5h quota | `5h 42% (2h)` | 5-hour rolling window usage with reset countdown |
| 7d quota | `7d 58%` | 7-day rolling window usage |
| Model | `▸ Opus` | Active Claude model |
| Branch | `my-project/main` | Project name and git branch |
| Tokens | `↑95k ↓30k` | Input and output tokens this session |
| Messages left | `~120msg left` | Estimated messages remaining at current burn rate |
| Time to empty | `empty in 1h0m` | Projected time until quota runs out |
| Decay | `drops in 45m` | When 5h rolling window usage starts dropping |
| Cost | `$1.85` | Session cost in USD |
| Duration | `30m0s` | Session duration |
| Pace | `-19%` | Ahead/behind expected usage rate |

### Color coding

| Color | Meaning | When |
|---|---|---|
| Teal | Good | Under 50% (bar), under 70% (quota) |
| Orange | Warming up | 50–75% (bar), 70–90% (quota) |
| Magenta | Critical | Over 75% (bar), over 90% (quota) |

### Error states

When something goes wrong, the statusline shows what happened instead of a blank `--`:

| State | Meaning |
|---|---|
| `auth expired` | OAuth token invalid — re-authenticate Claude Code |
| `offline` | Cannot reach the Anthropic API |
| `rate limited` | Too many requests — retries automatically |
| `api error` | Unexpected API response |

## Configuration

Control every segment with environment variables. Set them in your shell profile or in `~/.claude/settings.json`:

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

| Variable | Default | Description |
|---|---|---|
| `CQB_TOKENS` | `1` | Show token counts (↑in ↓out) |
| `CQB_RESET` | `1` | Show reset countdowns |
| `CQB_DURATION` | `1` | Show session duration |
| `CQB_BRANCH` | `1` | Show git branch |
| `CQB_COST` | `0` | Show session cost in USD |
| `CQB_CONTEXT_SIZE` | `0` | Show context window size (e.g., "of 200K") |
| `CQB_PACE` | `0` | Show pace indicator (+/-% vs expected rate) |
| `CQB_REMAINING` | `0` | Show remaining% instead of used% for quotas |

### Predictions

| Variable | Default | Description |
|---|---|---|
| `CQB_MSGS_LEFT` | `0` | Estimate messages remaining based on token burn rate |
| `CQB_TIME_EMPTY` | `0` | Project time until quota is exhausted |
| `CQB_DECAY` | `0` | Show when 5h rolling window usage will start dropping |

### Notifications

| Variable | Default | Description |
|---|---|---|
| `CQB_NOTIFY` | `0` | Enable desktop notifications at quota thresholds |
| `CQB_NOTIFY_THRESHOLDS` | `80,90,95` | Comma-separated % thresholds to alert at |

Notifications use platform-native methods: Windows toast, macOS osascript, Linux notify-send. Each threshold fires once per 5-hour window.

### Historical tracking

| Variable | Default | Description |
|---|---|---|
| `CQB_TRACK` | `0` | Log usage snapshots to local SQLite database |

When enabled, every statusline refresh logs a snapshot to `~/.claude/plugins/claude-usage-monitor/usage_history.db` — timestamp, model, tokens in/out, cost, quota percentages, session duration, and project name.

## CLI commands

### Usage statistics

```bash
python statusline.py --stats           # Last 30 days
python statusline.py --stats --days 7  # Last 7 days
```

Shows active days, peak usage, top projects by cost, and daily breakdown.

### JSON export

```bash
python statusline.py --json                              # Last 30 days
python statusline.py --json --days 7                     # Last 7 days
python statusline.py --json | jq '.[] | select(.five_hour_pct > 80)'  # Filter
```

Raw snapshots as JSON for piping to other tools.

## Project structure

```
my-claude-monitor/
├── src/claude_usage_monitor/
│   ├── __init__.py          # Package version
│   ├── __main__.py          # python -m entry point
│   ├── cli.py               # --stats, --json commands
│   ├── colors.py            # 256-color ANSI scheme
│   ├── formatting.py        # Number/time formatting
│   ├── notifications.py     # Desktop notification system
│   ├── oauth.py             # OAuth token retrieval
│   ├── predictions.py       # Messages remaining, time to empty, decay
│   ├── quota.py             # API fetch with caching and error states
│   ├── statusline.py        # Main statusline renderer
│   └── data/
│       ├── __init__.py
│       └── tracker.py       # SQLite historical tracker
├── statusline.py            # Root launcher
├── statusline.sh            # Bash launcher
├── statusline.cmd           # Windows launcher
├── install.py               # Cross-platform installer
├── install.sh / install.ps1 # Install wrappers
├── pyproject.toml           # Package config
└── tests/smoke_test.py      # Tests
```

## Security and trust

**Reads:**
- Session JSON from Claude Code via `stdin`
- `~/.claude/.credentials.json` for the OAuth token (or `CLAUDE_CODE_OAUTH_TOKEN` env var)
- `git rev-parse --abbrev-ref HEAD` for the branch name

**Writes:**
- `claude-sl-usage.json` and `claude-sl-usage.lock` in your system temp directory (cache)
- `~/.claude/plugins/claude-usage-monitor/usage_history.db` (only if `CQB_TRACK=1`)

**Network:**
- One HTTPS call to `https://api.anthropic.com/api/oauth/usage`, cached for 5 minutes

No telemetry. No analytics. No data leaves your machine except the single quota API call to Anthropic.

## Uninstall

1. Delete `~/.claude/plugins/claude-usage-monitor/`
2. Remove the `statusLine` entry from `~/.claude/settings.json` (restore `.bak` if needed)
3. Restart Claude Code

## Requirements

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) with an active subscription
- Python 3.10+

## License

MIT
