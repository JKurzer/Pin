# GUARDRAILS — replayed at the START of every subturn via `python scripts/pin.py emit`.

If you're reading this in tool output, the pin mechanism works. You will drift anyway.
This file is short on purpose. Replaying it is cheap. Not replaying it is expensive.
(Not pinned yet? `python scripts/pin.py pin GUARDRAILS.md` — once — then emit every subturn.)

## Scope fence

IN SCOPE: ArtilleryGun lifecycle, gun authoring, attributes/identities/vectors/tags,
fire-control wiring, DataTable definitions, the BP library surface.

OUT OF SCOPE — do NOT parse, unfold, or "just peek" at these. They eat context whole:
- `Private/FArtilleryBusyWorker.cpp` / the threaded executor internals
- `Public/Systems/Threads/` (FArtilleryTicklitesThread, FArtilleryStateTreesThread, FRollbackArtilleryWorker)
- `CanonicalInputStreamECS` (input pattern matcher internals)
- `ABarragePlayerController`, `BarragePlayerAgent`, `BarrageEnemyHitboxConcepts` (locomo meat)
- `InputRollback`, `NetworkDebugger`, `Systems/ArtilleryGame.cpp`
- The **LocomoCore plugin** (repo root, deliberately NOT cloned)
- Anything under `PhysicsTypes/` beyond a signature you already have

If a task genuinely requires those: STOP. Tell the user what's needed and ask how to proceed.
Use `reference/locomotion-menu.md` for locomotion-shaped questions instead of source.

## Context discipline (this codebase is dense; agents die here)

1. Grep before read. Never read what a grep answers.
2. Headers before cpps. Signatures before bodies. Bodies only by line range.
3. Never full-read a file >300 lines. Range-read around grep hits.
4. One concept per read. If you can't name what you're looking for, don't open the file.
5. Don't re-read what this skill already states. Trust the skill; verify only on contradiction.
6. Cite file:line when reporting. "Somewhere in dispatch" is not a location.

## Behavioral rules

- Guns are USTRUCTs. Never NewObject them. (See SKILL.md golden rules — all apply here.)
- Match your registry pairs: register+pattern, unregister+unpattern.
- Game thread for registration/binding; busy worker is read-only-for-you.
- Only attributes replicate. State goes in attributes or it doesn't go anywhere.
- Small diffs. This codebase rewards surgical edits and punishes rewrites.
- When a comment and the code disagree, the code wins — and say so in your report.
