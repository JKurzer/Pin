# Static adapter (any framework with an always-include file)

The zero-code port. If your framework supports an always-included context
file — `CLAUDE.md`, `AGENTS.md`, `.cursor/rules`, `.windsurfrules`, a system
prompt you control — render pins into it:

```
python scripts/pin.py emit --quiet > PINNED.md
```

Then include it:

- Claude Code: `@PINNED.md` inside `CLAUDE.md`
- Cursor: copy the file into `.cursor/rules/pinned.mdc` (or reference it)
- Codex / others: paste or `@`-include in `AGENTS.md`

## The catch (be honest about it)

Static inclusion is **primacy-only** and **stale the moment a pinned file
changes** — there is no hook to re-render. Mitigations:

- Re-render after every `pin`/`unpin` (make it one muscle-memory pair).
- Re-render at session start if you're diligent.
- Prefer this adapter only when the framework genuinely lacks hooks.
  Checksums in the rendered output at least make staleness *detectable* by
  eyeball (`sha256:` header vs `python scripts/pin.py list`).

For per-turn deterministic injection you want a real hook: see the
code-puppy or claude-code adapters and port the ~40 render lines to your
framework's equivalent of "before the model sees the prompt."
