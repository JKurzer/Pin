This is the Pin machinery that I normally use for controlling agents by repeatedly bashing them with context injection and similar mid-turn. I've found that in CoT
models, you generally get a ton of drift even during a turn. As a result, this is a deterministic and forceful way to both repeatedly ingrain context, and
allow agents to manage their own context.

While this version uses only nudges, I advocate for a hard-kill strategy in the future.
