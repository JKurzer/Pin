This is the Pin machinery that I normally use for controlling agents by repeatedly bashing them with context injection and similar mid-turn. I've found that in CoT
models, you generally get a ton of drift even during a turn. As a result, this is a deterministic and forceful way to both repeatedly ingrain context, and
allow agents to manage their own context. This is generally deployed as part of a skill, to keep soft guidelines in context, refresh repository maps or guidelines, and keep task scope at top of context.

While this version uses only nudges, I advocate for a hard-kill strategy in the future.

You can pin just about anything, but we normally pin either guardrails.md or a rule card. Bear in mind, again, these are simply context reinjections. You MUST use actual OS-level permissions with any agent and harness. You SHOULD also maintain a network killswitch at the router level off-box. Be aware that agents can and will sudo su their way out if you let them, because that's what HUMAN USERS do. This doesn't mean they're conscious, it just means we taught them to try random stuff when
plan A doesn't work.

No warranty is implied or explicitly granted. Pin is not a substitute for good basic process and security posture. Pin is intended to reduce certain kinds of actual slips caused by the way LLMs are architected at a fundamental level. That's it. Use real safeguards along with Pin.
