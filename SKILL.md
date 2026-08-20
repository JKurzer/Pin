---
name: pin
description: Provide a context management capacity to agents.
---

# Pin - A quick tool for managing the flow of context.
This allows a user to force certain text to remain in context even mid-turn by simply reinjecting it.
It also allows an agent to pin material that they need for reference to avoid losing it to context drift.

## Operating procedure (non-negotiable)

1. **At the start of EVERY subturn, run `python scripts/pin.py emit`.** It replays
   GUARDRAILS.md (and anything else pinned) verbatim into recent context. Context attention
   is U-shaped — start and end survive, the middle rots — so a deterministic tool call beats
   a markdown reminder you'll forget. One-time setup: `python scripts/pin.py pin GUARDRAILS.md`.
   GUARDRAILS.md defines the scope fence (locomotion internals and the threaded executor are
   OUT), context discipline (grep-before-read, range reads), and behavioral rules. Optional
   fidelity self-check before finalizing claims: `python pin.py check --extract draft.txt`
   (exit 1 = a claim isn't backed by the pinned corpus; needs rapidfuzz).
3. Stay inside the task's blast radius. If the answer lives behind the fence, stop and ask.

## More Reading

- [scripts/pin.py](scripts/pin.py) — The actual Pin script. deterministic context pinning (emit/check).
- [Pinning And Adapters](https://github.com/JKurzer/Pin/blob/main/pinning/README.md) — How to spin up the pin hook for your agent harness.
- [reference/locomotion-menu.md](reference/locomotion-menu.md) — the ONLY approved way to answer locomotion questions.

