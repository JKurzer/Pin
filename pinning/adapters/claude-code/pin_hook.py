#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook: inject pinned files as additionalContext.

Claude Code adapter for the portable context-pinning mechanism — see
pinning/README.md for the state/render contract this implements. This script
is the RENDER path only; state is managed by pin.py.

Silent (no output) when no pins exist. Hash drift is flagged inline so stale
pins are visible rather than silently wrong.

Install: merge hooks.json (this dir) into ~/.claude/settings.json, fixing the
command path to wherever this script lives.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

MAX_BYTES = 8192
MAX_PINS = 16


def state_path() -> Path:
    for env in ("CONTEXT_PINS", "ARTILLERY_GUNS_PINS"):
        override = os.environ.get(env)
        if override:
            return Path(override)
    for name in (".context-pins.json", ".artillery-guns-pins.json"):
        candidate = Path.home() / name
        if candidate.exists():
            return candidate
    return Path.home() / ".context-pins.json"


def collect() -> list:
    try:
        p = state_path()
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
        pins = [d for d in data if isinstance(d, dict) and "path" in d][:MAX_PINS]
    except Exception:
        return []
    out = []
    for pin in pins:
        try:
            path = Path(pin["path"])
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            current = hashlib.sha256(path.read_bytes()).hexdigest()
            out.append((path, len(content.encode("utf-8")), current,
                        current != pin.get("sha256"), content))
        except Exception:
            continue
    return out


def main() -> int:
    try:
        sys.stdin.read()  # consume the hook payload; contents not needed
    except Exception:
        pass
    entries = collect()
    if not entries:
        return 0
    parts = ["## Pinned context (auto-injected every prompt; treat as standing rules)"]
    total = 0
    for path, size, sha, drift, content in entries:
        if total + size > MAX_BYTES:
            parts.append(f"- SKIPPED (budget {MAX_BYTES} B): {path}")
            continue
        flag = " [CHANGED since pinned]" if drift else ""
        parts.append(f"### {path} (sha256:{sha[:12]}{flag})\n{content}")
        total += size
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n\n".join(parts),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
