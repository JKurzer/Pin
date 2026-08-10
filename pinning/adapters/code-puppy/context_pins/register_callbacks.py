"""context_pins: inject pinned files into the system prompt on every run.

code-puppy adapter for the portable context-pinning mechanism — see
pinning/README.md for the state/render contract this implements. This file
is the RENDER path only; state is managed by scripts/pin.py.

Pinned content is injected via load_prompt at every agent run — primacy
position, zero model cooperation required. The pin_context tool remains for
voluntary recency bumps mid-session. No state file / empty pins -> no
injection. That is the off switch.

Install: copy this directory to ~/.code_puppy/plugins/context_pins/
"""
import hashlib
import json
import os
from pathlib import Path

from code_puppy.callbacks import register_callback
from code_puppy.messaging import emit_warning

MAX_PROMPT_BYTES = 8192  # total injection budget per run; tune to taste
MAX_PINS = 16


def _state_path() -> Path:
    for env in ("CONTEXT_PINS", "ARTILLERY_GUNS_PINS"):
        override = os.environ.get(env)
        if override:
            return Path(override)
    for name in (".context-pins.json", ".artillery-guns-pins.json"):
        candidate = Path.home() / name
        if candidate.exists():
            return candidate
    return Path.home() / ".context-pins.json"


def _load_pins() -> list:
    try:
        p = _state_path()
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
        return [d for d in data if isinstance(d, dict) and "path" in d][:MAX_PINS]
    except Exception:
        return []


def _collect() -> list:
    """Resolve pins to dicts with live content/hash; skip unreadable files."""
    out = []
    for pin in _load_pins():
        try:
            path = Path(pin["path"])
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            current = hashlib.sha256(path.read_bytes()).hexdigest()
            out.append({
                "path": path,
                "bytes": len(content.encode("utf-8")),
                "sha256": current,
                "drift": current != pin.get("sha256"),
                "content": content,
            })
        except Exception:
            continue
    return out


def _on_load_prompt():
    """load_prompt hook: pinned files as a system-prompt fragment."""
    try:
        entries = _collect()
        if not entries:
            return None
        parts = ["## Pinned context (auto-injected every run; treat as standing rules)"]
        total = 0
        for e in entries:
            if total + e["bytes"] > MAX_PROMPT_BYTES:
                parts.append(f"- SKIPPED (budget {MAX_PROMPT_BYTES} B): {e['path']}")
                continue
            flag = " [CHANGED since pinned]" if e["drift"] else ""
            parts.append(f"### {e['path']} (sha256:{e['sha256'][:12]}{flag})\n"
                         f"{e['content']}")
            total += e["bytes"]
        return "\n\n".join(parts)
    except Exception:
        return None


def _on_agent_run_end(*args, **kwargs):
    """agent_run_end hook: warn when a pinned file changed since pinning."""
    try:
        for e in _collect():
            if e["drift"]:
                emit_warning(
                    f"Pinned file changed since pinned: {e['path']} — re-pin to refresh."
                )
    except Exception:
        pass
    return None


def _register_pin_context_tool(agent):
    @agent.tool
    def pin_context() -> str:
        """Replay all pinned files verbatim into recent context (recency bump).

        The system prompt already carries pins at primacy; call this when a
        long session has buried them and you want them at the recency end."""
        entries = _collect()
        if not entries:
            return f"No pins (state: {_state_path()})."
        chunks = []
        for i, e in enumerate(entries, 1):
            flag = " [CHANGED since pinned]" if e["drift"] else ""
            chunks.append(
                f"=== PINNED {i}/{len(entries)}: {e['path']} "
                f"({e['bytes']} B, sha256:{e['sha256'][:12]}{flag}) ===\n"
                f"{e['content']}"
            )
        return "\n\n".join(chunks)


def _register_tools():
    return [{"name": "pin_context", "register_func": _register_pin_context_tool}]


def _advertise_pin_context(agent_name=None):
    return ["pin_context"]


register_callback("load_prompt", _on_load_prompt)
register_callback("agent_run_end", _on_agent_run_end)
register_callback("register_tools", _register_tools)
register_callback("register_agent_tools", _advertise_pin_context)
