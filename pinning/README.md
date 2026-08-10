# Context pinning — portable nudge mechanism

Model attention over context is U-shaped: primacy and recency survive, the
middle decays. A markdown instruction like "re-read RULES.md every turn" is
itself middle-context and decays with everything else. Fleet testing
confirmed agents never invoke voluntary reminders organically.

The fix: **deterministic injection by the harness, not voluntary recall by
the model.** This directory is the framework-portable version of that idea.

## The portability contract

Two pieces, that's all:

1. **State schema** — a JSON array at a well-known location:
   `$CONTEXT_PINS` > `$ARTILLERY_GUNS_PINS` (legacy) > `~/.context-pins.json`
   > `~/.artillery-guns-pins.json` (legacy). First match wins.
   ```json
   [{"path": "C:/abs/path/GUARDRAILS.md", "sha256": "<hex-at-pin-time>", "bytes": 2401}]
   ```
2. **Render contract** — read state, read each live file, emit:
   a header line, then per file `### <abspath> (sha256:<first12> [CHANGED since pinned])`
   followed by verbatim content. Skip missing files. Cap total bytes
   (8 KB is sane). Hash drift flagging is the whole point — it makes stale
   pins visible instead of silently wrong.

**State is written only by the core** (`scripts/pin.py`: pin/unpin/clear —
stdlib-only, no framework deps). **Adapters only render.** Any framework
adapter is ~40 lines against this contract; if yours isn't, you're adding
features, not porting.

## Adapters

| Framework | Adapter | Injection point |
|---|---|---|
| code-puppy | `adapters/code-puppy/context_pins/` | `load_prompt` hook → system prompt every run; drift warning on `agent_run_end`; `pin_context` tool for recency bumps |
| Claude Code | `adapters/claude-code/` | `UserPromptSubmit` hook → `additionalContext` on every prompt |
| Anything with an always-include file | `adapters/static/` | `python pin.py emit --quiet > PINNED.md`, `@`-include it from CLAUDE.md / AGENTS.md / .cursor/rules |

## Core usage

```
python scripts/pin.py pin GUARDRAILS.md     # write state (only the core does this)
python scripts/pin.py emit                  # render (recency bump, manual)
python scripts/pin.py emit --quiet          # render for static includes (no summary line)
python scripts/pin.py check --extract f.md  # claim fidelity vs pinned corpus (needs rapidfuzz)
```

## Sizing

GUARDRAILS-scale pins (~2.4 KB) cost ~600 tokens per injection. Keep pins to
short hot-loop rule files. The mechanism exists to defeat drift on *rules*;
it is not a document-retrieval system.
