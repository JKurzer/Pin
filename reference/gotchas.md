# Gotchas & Dead Ends

Sourced from code, comments, and TODOs. Trust the code over the comments; both are cited.

## Registry truths

- **`GunByKey` is not the only place guns live.** `UInventoryDispatch` owns
  `TriggerLinkedGuns` (an `seq::ordered_set<FSimpleTriggerGun>` — by value) and
  `TriggerGuns_BusyWorkerOnly`. Firing *generally* requires `GunToFiringFunctionMapping`
  membership, but trigger guns have their own Precheck-driven path. Trace ownership; don't assume.
- **A gun in `GunByKey` without a fire-mapping entry will never fire** from input. Conversely,
  popping the fire mapping without removing the gun leaves a live gun that can't fire. Match
  your pairs: `RegisterGun`+`RegisterPattern`, `UnregisterGun`+`UnregisterPattern` (or use
  `RegisterGunPatternPair` / `UnregisterGunPatternPair`).

## Instantiation traps

- `UStaticGunLoader` uses UE reflection: gun structs **must** be `USTRUCT`s and the
  `LoadableCPP` path must name the struct **without** the `F` prefix
  (`/Script/Bristle54.GunWeeRocket` loads `FGunWeeRocket`).
- Loader warning, verbatim: *"THIS IS NOT GUARANTEED TO WORK FOR NON-BLUEPRINT TYPES. IN FACT,
  IT PROBABLY WILL FUCKING EXPLODE."* — keep structs BlueprintType-reflected.
- BP guns: unimplemented (`//we don't handle bp stuff yet, sorry`). Hybrid route = BP class
  inheriting the C++ gun, and mind BlueprintNativeEvent vs BlueprintImplementableEvent.
- `FArtilleryGun` instances are raw-`Malloc`+`InitializeStruct` wrapped in `TSharedPtr` —
  construction/initialization is split. **Uninitialized guns are live landmines**; `GetGun`
  handles the dance, `RegisterExistingGun` does NOT (it assumes you initialized).
- `GetGun` mints instance IDs via `HashDownTo32(ProbableOwner + ++monotonkey)` — flagged in
  TODOs as not truly deterministic. Don't build logic that depends on instance ID ordering
  across peers.
- `GetGun` failure returns `FGunKey()` = definition `"M6D"`, instance 0. `DefaultGunKey` is
  also `"M6D"`. If you don't check `IsValidInstance()`, you will debug a phantom pistol.
- `FGunDefinitionRow`'s seven ability-string fields are **dead**: the loader consumes only
  `GunDefinitionId`/`IsCPP`/`LoadableCPP` (`StaticAssetLoader.cpp:30-60`) and `GetGun` passes
  no abilities (`ArtilleryDispatch.cpp:508-519`). Inject custom abilities via `Initialize`
  params. *Slated to change — re-verify against `StaticAssetLoader.cpp` (added 2026-08).*
  (`ProjectileDefinitionID` is likewise unconsumed in ArtilleryRuntime.)

## Initialize() ordering

- Owner actor must be in `UTransformDispatch` **before** `Initialize`, or it returns false and
  the gun never becomes `ReadyToFire`.
- `MaxAmmo`/`Firerate`/`ReloadTime` seed default attributes at init; changing them later does
  NOT update attributes — write the attributes instead.
- `BeamFiringPoint` is looked up by literal name via `GetDefaultSubobjectByName`. Rename the
  muzzle component and `FiringPointComponent` silently ends up null-ish.
- Ability injection is **per-slot defaulted but gated on the `Prefire` member**: `Initialize`
  fills each null slot (`Param ? Param : NewObject`, `FArtilleryGun.cpp:134-148`) only when
  `Prefire == nullptr` at entry. Pre-assign the `Prefire` member directly and the other six
  stay null → `SetGunKey` null-derefs them (:163-171) and the dtor `RemoveFromRoot`s
  null/garbage siblings (:16-24; comment admits "this might change"). Inject via the
  `Initialize` params, never by member assignment. `GetGun` calls `Initialize(Key, false)`
  (`ArtilleryDispatch.cpp:519`), so the data-driven path ends `ReadyToFire=true`
  (:160) with keys set.

## Firing & abilities

- `UFireControlMachine::pushPatternToRunner` / `popPatternFromRunner`: **game thread only**.
- `RunGuns()` executes fire delegates on the **game thread** inside `UArtilleryDispatch::Tick`,
  not the busy worker. Attribute *writes* inside fire logic are thread-safe (cohered reads);
  UObject work is only safe because it happens here.
- Abilities: only `K2_ActivateViaArtillery` runs. No timers/async/latent nodes — `EndAbility`
  doesn't clear them and rollback will break them. Deferred work = ticklites
  (`Dispatch->RequestAddTicklite`).
- **`EndAbility` outcome mapping is inverted vs the enum names**: `bWasCancelled ? Fired :
  Canceled` (`UArtilleryAbilityMinimum.cpp:87`). The chain continues only on `Fired`
  (`FArtilleryGun.cpp:51`), so textbook `CommitAbility` + `EndAbility(bWasCancelled=false)`
  HALTS the gun; pass `true` to continue. The null-event-data warning branches
  (:57-66) rely on this — they end with `bWasCancelled=true` → `Fired` → chain continues.
  `CanceledAfterCommit` is never emitted. `CancelAbility` is a bare `Super::` forward that
  never fires `GunBinder`.
- **Default abilities never call `EndAbility`** (`K2_ActivateViaArtillery_Implementation` is
  empty, `UArtilleryAbilityMinimum.h:162-164`). The chain advances only because every current
  path passes null `TriggerEventData`, routing `ActivateAbility` into the warning branch that
  ends the ability itself. No `FGameplayEventData` is constructed anywhere in the plugin
  (`ArtilleryControlComponent.cpp:24-28` passes `BufferInfo` only) — so no ability body ever
  executes in this snapshot, and if event data is ever plumbed, unmodified default abilities
  stall the chain at Prefire.
- **Unbound-`GunBinder` landmine**: base `PreFireGun` binds only 2 of 7 binders
  (`FArtilleryGun.cpp:36-37`) and `EndAbility` uses `.Execute`, not `ExecuteIfBound`
  (`UArtilleryAbilityMinimum.cpp:88`). PostFire/cosmetic/FailedFire abilities ending
  = unbound-delegate assert. `FQuestTriggerGun` overrides `PostFireGun` WITHOUT calling
  base — that is the workaround pattern.
- Comment/code contradiction: a comment says instancing is "ALWAYS NonInstanced" but the
  constructor sets `InstancedPerActor`. Constructor wins.
- `QueueFire` / `ActionsToOrder` — "unused atm". `RunGunFireTimers`, `CheckFutures`,
  `RERunGuns`, `RERunLocomotions` are stubs. Don't build on them.
- `RequestGunFire` goes through the RequestRouter and runs on the game thread — it is not
  immediate; don't expect same-call effects.

## Trigger guns

- `TriggerLinkedGuns` (the by-value `seq::ordered_set`) is **dead in this snapshot**
  (`InventoryDispatch.h:88` is its only mention). The live path is `CreateOnVerTick` →
  `GetGun(defId, itemKey)` → `GunByKey` + `TriggerGuns_BusyWorkerOnly`
  (`InventoryDispatch.cpp:129-130`): polymorphic `TSharedPtr`, no slicing, DataTable-loaded
  like any gun. Keep the GetTypeHash/operator==/std::hash trio anyway — it is the
  FQuestGun idiom for any by-value storage.
- `#define Inventory_VERIFIEDFRAMETESTMODE true` (`InventoryEssentialTypes.h:15`) — the
  verified-frame gate in `FSimpleTriggerGun::PreFireGun` is compiled OPEN; `Precheck`
  runs on every activation in this snapshot.

## Lifecycle leaks

- `PooledGuns` is **write-only**: `ReleaseGun` adds, nothing ever reads. Pooling is aspirational;
  every `GetGun` allocates fresh. Don't rely on pooling for perf.
- `LoadGunData()` is a dummy that only builds a path string. The real load is
  `UStaticGunLoader::Initialize`.
- `RegisterControllite` has no removal path ("for now, you can't remove these").
- `GetAttribRequired` is marked DEPRECATED and `checkf`s on miss — a missing attribute is a
  crash, not an error. Prefer `GetAttrib` + null check, or `GetAttribAndApplyIf`.
- Ammo economy is NOT manual: a per-gun `GunFinalTickResolver` ticklite decrements
  `COOLDOWN_REMAINING` and auto-reloads on empty (`FTGunFinalTickResolver.h:41-87`),
  gated on `MAX_AMMO > 0`. (An earlier eval note claimed cooldown was never decremented -
  falsified 2026-08 by direct read.) Unverified: the post-shot arming site of
  `COOLDOWN_REMAINING`/`TRIGGER_PULLED`.
- Gun stats: assign the base members (`MaxAmmo`/`Firerate`/`ReloadTime`) at the top of
  your `Initialize` override, before the macro seeds attributes from them
  (`FArtilleryGun.cpp:107-118`). Two traps: ctor bodies never run when the DataTable
  loader default-constructs, and redeclaring the members in your struct SHADOWS the
  base ones - the shadow value never reaches seeding (and duplicate UPROPERTY names
  in a hierarchy are UHT-hostile).
- `~FArtilleryGun` calls `Deregister` only `if (MyDispatch && MyDispatch->IsGunLive(MyGunKey))`
  — guns owned elsewhere (inventory) or never registered won't be deregistered by the dtor.

## Determinism & threading

- Sim runs at ~120hz on `FArtilleryBusyWorker`; time is *still* during a tick (`GetShadowNow`
  updates only at tick start). Don't wall-clock anything in sim code.
- `ProcessRequestRouterGameThread` ordering is non-deterministic across thread accumulator
  maps (acknowledged TODO) — don't depend on cross-request ordering within a frame.
- `SetupNewPlayer` is a stub (per-player networking not yet ported — see
  `PatchSalvage/rollback_integration.patch`).
- `GetVectorSetShadowByObjectKey` uses `FindChecked` — missing key = assert. Others return
  nullptr. Inconsistent by design; check the map first.
