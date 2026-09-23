# SESSION — <project/task> (working-set card; agent-owned, re-pin on every update)

## What this card is
A WORKING-SET card: the agent's session memory, not the human's floor.
The floor (rules card) is seeded by the human and never diluted; this card
is appended by the agent mid-task and re-pinned after EVERY edit
(`pin.py pin <file>` — same call re-pins; stale-hash flags are the point).

## Decisions (locked with the human, timestamp)
1. <Decision that would be expensive to re-litigate, e.g. "sleep default-ON">
2. <Decision, e.g. "harness lives OUTSIDE both repos">
3. <Constraint, e.g. "push to main as I go; API must not break">

## Invariants (tripwires for THIS task)
- <Gate that must stay green, e.g. "tests + typecheck before every commit">
- <Scope fence, e.g. "vendored files stay byte-identical">

## Checklist (update + re-pin at each chunk)
- [x] done thing (commit abc1234, numbers if perf)
- [>] in-flight thing (where to resume)
- [ ] next thing
