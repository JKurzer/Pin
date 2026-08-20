# RULES CARD — replayed per command. Obey. (Full docs: SKILL.md, reference/)

1. Guns are USTRUCTs. Never NewObject/SpawnActor them. Loader or MakeShared+installGun only.
2. Owner actor must be in UTransformDispatch BEFORE Initialize or Initialize silently returns false.
3. All gameplay state lives in attributes/tags keyed by FSkeletonKey. Only attributes replicate. NO state on abilities.
4. Abilities: override K2_ActivateViaArtillery_Implementation only. Commit + EndAbility(bWasCancelled=TRUE) to continue the chain — the outcome mapping is INVERTED (true → Fired). No timers/async/latent nodes.
5. Default abilities never end themselves; the stock chain ASSERTS on unbound GunBinder in PostFire slots. Bind before activating, or override PostFireGun WITHOUT calling base (FQuestGun pattern).
6. Nothing in the plugin ever constructs FGameplayEventData — K2 ability bodies do not run on stock fire paths.
7. Inject abilities via Initialize PARAMS only; never pre-assign the Prefire member (six nulls → SetGunKey crash). Gun stats: assign base members at the top of your Initialize override, before the macro — never redeclare (shadowing) and never in ctor bodies (default-construct paths skip them).
8. Trigger guns: live path is CreateOnVerTick→GetGun, polymorphic, no slicing. VERIFIEDFRAMETESTMODE is compiled open — Precheck runs every activation.
9. Register/bind on the GAME THREAD only; the busy worker is read-only-for-you. Match pairs: register+pattern, unregister+unpattern.
10. Grep before read. One large file (>300 lines) per turn, max. Cite file:line or it didn't happen.
11. When a comment and the code disagree, the code wins — and say so in your report.
