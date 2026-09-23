# Example cards

Real cards from daily use — the patterns, not templates we'd never run.
Card anatomy and how to adopt them lives in [../pinning/README.md](../pinning/README.md)
("Rules cards (human notes)").

## The two card types

**Floor cards** (human-seeded, the involuntary base): a distilled <=20-line
list of the rules agents *actually violate* in this repo (~500 tokens).
One line per rule; only rules that have bitten someone; full docs by
reference, never by copy.

- [`rules-card--performance.md`](rules-card--performance.md) — the most
  portable card we own. Pure process ("measure, never guess"), works
  verbatim in any repo doing performance work.
- [`rules-card--research.md`](rules-card--research.md) — an ML research
  floor (immutable raw data, evals-or-it-didn't-ship, leakage discipline).
  Its footer shows the **global-skill re-pin path**.
- [`rules-card--adversarial-fleet.md`](rules-card--adversarial-fleet.md) —
  the same floor shape for an adversarial fleet, plus the "Pin is control,
  not security" line every card touching agents should steal. Its footer
  shows the **vendored `tools/pin/scripts/pin.py` re-pin path**.

**Working-set cards** (agent-owned, session memory): the agent appends
these mid-task so a 12-hour autonomous run survives context compaction —
decisions locked with the human, invariants, and a live checklist.
[`working-set-card--template.md`](working-set-card--template.md) is the
skeleton. Re-pin after every edit; the CHANGED-since-pinned drift flag is
how you notice you forgot.

## The footer convention

The last line of a floor card tells the agent how to re-pin the card after
editing it. That's not decoration — it's what makes cards self-maintaining
in an agent's hands. Use one of the two forms shown in the examples above
(global skill path, or vendored `tools/pin/scripts/pin.py`).
