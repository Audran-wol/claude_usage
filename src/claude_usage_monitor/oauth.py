"""OAuth token retrieval for Claude Code."""

import json
import os
from pathlib import Path


def get_oauth_token() -> str | None:
    """Read OAuth token from Claude Code's credential store."""
    tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if tok:
        return tok
    cred_path = Path.home() / ".claude" / ".credentials.json"
    if cred_path.exists():
        try:
            creds = json.loads(cred_path.read_text(encoding="utf-8"))
            return creds.get("claudeAiOauth", {}).get("accessToken")
        except Exception:
            pass
    return None
