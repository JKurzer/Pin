# RULES — WordOfUnmaking (the pinned floor; keep <=20 lines)

1. Raw data is immutable: `data/raw/` is write-once; derived stuff goes to `data/derived/`.
2. The fleet is declarative: a task is a spec file + a seed. No hidden agent state, ever.
3. Every attack ships with an eval or it doesn't ship.
4. Adversarial wins are reported as detector degradation at fixed FPR (default 1e-3) with CIs — never bare evasion counts.
5. No leakage: split by source document, never by chunk. Paraphrase sets stay out of tuning.
6. Pin is control, not security. Real sandboxing, OS-level permissions, and a network killswitch are on you.
7. A task that can't be reproduced from its spec is a task that didn't happen.
8. Baseline before fancy. If the dumb fleet ties the clever one, the clever one goes.
9. Small diffs. Grep before read. One concept per read.
10. Edited this file? Re-pin it: `python tools/pin/scripts/pin.py pin RULES.md`
