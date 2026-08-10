# Claude Code adapter

`pin_hook.py` is a `UserPromptSubmit` hook: every user prompt gets the pinned
files injected as `additionalContext`. No pins -> zero output, zero tokens.

## Install

Merge `hooks.json` into `~/.claude/settings.json` (or project
`.claude/settings.json`), fixing the command path to this script's real
location. Windows: use `python` with forward slashes, as shown.

## Manage pins

From the repo root (the core is shared across all adapters):

```
python scripts/pin.py pin path\to\RULES.md
python scripts/pin.py list
```

## Notes

- Hash drift renders inline as `[CHANGED since pinned]` — if you see it,
  re-pin: `python scripts/pin.py unpin <f> && python scripts/pin.py pin <f>`.
- Injection budget is 8 KB across all pins (`MAX_BYTES` in the script).
- Pattern lifted from the verbatim plugin's hooks (claude-plugins/verbatim).
