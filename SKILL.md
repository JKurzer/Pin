---
name: context-pins
description: Deterministic context pinning for agent runs via scripts/pin.py (pin/unpin/list/emit/check/wrap) — replays small pinned files (rules cards, one ground-truth source) verbatim so standing rules survive long sessions. Use when pinned context shows drift warnings, when instructions keep getting forgotten mid-session, or when managing ~/.context-pins.json state.
---

# Context Pins — pin.py

Model attention over context is U-shaped: primacy and recency survive, the middle
decays. A markdown instruction like "re-read RULES.md every turn" is itself
middle-context and decays with everything else. The fix: **deterministic replay by
tool, not voluntary recall by the model.**

## Commands

```
python scripts/pin.py pin RULES.md        # add file(s) to the pin list (writes state)
python scripts/pin.py unpin RULES.md      # remove file(s)
python scripts/pin.py list                # show pins with size/hash + token estimate
python scripts/pin.py clear               # remove all pins (the off switch)
python scripts/pin.py emit                # replay all pins verbatim (recency bump)
python scripts/pin.py emit --quiet        # render for static includes (no summary line)
python scripts/pin.py check --extract f.md  # claim fidelity vs pinned corpus (needs rapidfuzz; exit 1 on failure)
python scripts/pin.py wrap -- <command>   # pinned shell: replay pins, run command, keep exit code
```

No subcommand = `emit`.

## State & render contract (keep adapters in sync)

- State: a JSON array, resolved `$CONTEXT_PINS` > `$ARTILLERY_GUNS_PINS` (legacy) >
  `~/.context-pins.json` > `~/.artillery-guns-pins.json` (legacy). First match wins.
  ```json
  [{"path": "C:/abs/path/RULES.md", "sha256": "<hex-at-pin-time>", "bytes": 900}]
  ```
- **State is written only by pin.py** (pin/unpin/clear — stdlib-only). Adapters only render.
- Render: per pin, a header `path (size, sha256:first12 [CHANGED since pinned])` then
  verbatim content. Skip missing files; cap total bytes. The drift flag is the point —
  stale pins become visible instead of silently wrong.
- code-puppy adapter: installed at `~/.code_puppy/plugins/context_pins/`. Injects pins
  into the system prompt every run (primacy), warns on drift at run end, and registers
  the `pin_context` tool (voluntary recency bump mid-session). Empty state = no injection.

## Pin hygiene

- Pin only small hot-loop files: a rules card (<=20 lines, ~500 tokens; only rules that
  have bitten someone, one line each) plus at most ONE ground-truth source file.
  Hard caps: 16 KB/file, 16 pins, 64 KB/emit. This is a drift-killer, not a
  document-retrieval system.
- Floor + working set: the human seeds the floor; the agent may append subtask pins.
  The floor cannot be diluted, only appended to.
- After editing a pinned file, re-pin it (`pin.py pin <file>` won't double-pin; unpin
  then pin, or just re-pin — the hash refreshes on next pin call after unpin).
- `check` verifies claim-shaped passages in a draft actually appear in the pinned
  corpus (exact-substring fast path, then partial-ratio alignment + Damerau-Levenshtein
  within tolerance). Only subcommand needing a non-stdlib dep (rapidfuzz).

## Layout / install

This repo is the skill's canonical source. One command installs it:

```
python scripts/install.py                      # skill + code-puppy adapter
python scripts/install.py --vendor <proj-dir>  # vendor pin.py into a project
                                               # (tools/pin/scripts/pin.py)
```

Idempotent (byte-compared; safe to re-run). `--no-adapter` skips the adapter;
`--dest <dir>` targets a different agent home. What it does, if you'd rather
walk it by hand:

- **Skill**: this directory (`SKILL.md` + `scripts/pin.py`) →
  `~/.code_puppy/skills/context-pins/` (or your framework's skills path).
- **code-puppy adapter**: `pinning/adapters/code-puppy/context_pins/` →
  `~/.code_puppy/plugins/context_pins/` (system-prompt injection every run).
- **Project side**: seed a rules card at the repo root and pin it once
  (`python scripts/pin.py pin RULES.md`). The card's last line should tell
  agents how to re-pin it after edits — see `examples/`.
- **State**: one JSON array at `~/.context-pins.json` (see the contract above).

See `examples/` for real cards, and `pinning/README.md` for the adapter
portability contract.
