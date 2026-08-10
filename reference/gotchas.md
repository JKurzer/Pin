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
- `FGunDefinitionRow`'s seven ability-string fields are **dead**: the loader reads only
  `LoadableCPP` (`StaticAssetLoader.cpp:30,60`) and `GetGun` passes no abilities
  (`ArtilleryDispatch.cpp:508-519`). Inject custom abilities via `Initialize` params.
  *Slated to change — re-verify against `StaticAssetLoader.cpp` (added 2026-08).*

## Initialize() ordering

- Owner actor must be in `UTransformDispatch` **before** `Initialize`, or it returns false and
  the gun never becomes `ReadyToFire`.
- `MaxAmmo`/`Firerate`/`ReloadTime` seed default attributes at init; changing them later does
  NOT update attributes — write the attributes instead.
- `BeamFiringPoint` is looked up by literal name via `GetDefaultSubobjectByName`. Rename the
  muzzle component and `FiringPointComponent` silently ends up null-ish.
- Ability UObjects are `AddToRoot`ed in Initialize and `RemoveFromRoot`ed in the destructor,
  assuming all-or-none assignment. Assign exactly one slot manually and the dtor may touch
  null/garbage siblings.

## Firing & abilities

- `UFireControlMachine::pushPatternToRunner` / `popPatternFromRunner`: **game thread only**.
- `RunGuns()` executes fire delegates on the **game thread** inside `UArtilleryDispatch::Tick`,
  not the busy worker. Attribute *writes* inside fire logic are thread-safe (cohered reads);
  UObject work is only safe because it happens here.
- Abilities: only `K2_ActivateViaArtillery` runs. No timers/async/latent nodes — `EndAbility`
  doesn't clear them and rollback will break them. Deferred work = ticklites
  (`Dispatch->RequestAddTicklite`).
- Comment/code contradiction: a comment says instancing is "ALWAYS NonInstanced" but the
  constructor sets `InstancedPerActor`. Constructor wins.
- `QueueFire` / `ActionsToOrder` — "unused atm". `RunGunFireTimers`, `CheckFutures`,
  `RERunGuns`, `RERunLocomotions` are stubs. Don't build on them.
- `RequestGunFire` goes through the RequestRouter and runs on the game thread — it is not
  immediate; don't expect same-call effects.

## Lifecycle leaks

- `PooledGuns` is **write-only**: `ReleaseGun` adds, nothing ever reads. Pooling is aspirational;
  every `GetGun` allocates fresh. Don't rely on pooling for perf.
- `LoadGunData()` is a dummy that only builds a path string. The real load is
  `UStaticGunLoader::Initialize`.
- `RegisterControllite` has no removal path ("for now, you can't remove these").
- `GetAttribRequired` is marked DEPRECATED and `checkf`s on miss — a missing attribute is a
  crash, not an error. Prefer `GetAttrib` + null check, or `GetAttribAndApplyIf`.
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
