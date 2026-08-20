# GUARDRAILS — replayed at the START of every subturn via `python scripts/pin.py emit`.

If you're reading this in tool output, the pin mechanism works. You will drift anyway.
This file is short on purpose. Replaying it is cheap. Not replaying it is expensive.
(Not pinned yet? `python scripts/pin.py pin GUARDRAILS.md` — once — then emit every subturn.)

## Scope fence

IN SCOPE: 
EXPENSIVE — budget applies: these eat context whole. Read at most ONE large file
per turn, total, across this list and any other file >300 lines.

If a task genuinely requires MORE than one of these in a turn: STOP. Tell the user
what's needed and ask how to proceed.

## Context discipline (this codebase is dense; agents die here)

1. Grep before read. Never read what a grep answers.
2. Headers before cpps. Signatures before bodies. Bodies only by line range.
3. Large files (>300 lines): one full read per turn, max. Range-read everything else
   around grep hits.
4. One concept per read. If you can't name what you're looking for, don't open the file.
5. Don't re-read what this skill already states. Trust the skill; verify only on contradiction.
6. Cite file:line when reporting. "Somewhere in dispatch" is not a location.

## Behavioral rules

- Small diffs. This codebase rewards surgical edits and punishes rewrites.
- When a comment and the code disagree, the code wins — and say so in your report.
