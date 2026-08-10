# Authoring New ArtilleryGuns

## The recipe (C++ gun)

1. **Declare the struct.** `USTRUCT(BlueprintType)`, inherit `FArtilleryGun`, `GENERATED_BODY()`.
2. **Constructors**: one default, one `(const FGunKey&, UArtilleryDispatch*)` forwarding to base.
3. **Override `Initialize`** and delegate to the macro:
   `return ARTGUN_MACROAUTOINIT(MyCodeWillHandleKeys);`
   (`#define ARTGUN_MACROAUTOINIT(X) Super::Initialize(KeyFromDispatch, X, PF, PFC, F, FC, PtF, PtFc, FFC)`)
4. **Override fire phases** only if you need custom behavior (`PreFireGun`/`FireGun`/`PostFireGun`).
   The base implementations already drive the 7-ability chain correctly.
5. **Add a DataTable row** (`FGunDefinitionRow`): `GunDefinitionId`, `IsCPP=true`,
   `LoadableCPP=/Script/<Module>.<StructNameWithoutF>`.
6. Grant with `RequestUnboundGun` / `GetGun`, or `FCM->RegisterGun`. Bind a pattern to fire from input.

## Minimal example — FMockArtilleryGun (Public/TestTypes/FMockArtilleryGun.h)

The canonical skeleton: constructor sets `MyGunKey`, all three fire phases overridden empty,
`Initialize` returns `ARTGUN_MACROAUTOINIT(MyCodeWillHandleKeys)`. Note the mock skips the
delegate chaining because it uses no abilities — a real gun keeps the base phase logic.

## Ability phases

Seven slots, assigned all-or-none; null slots become default `UArtilleryPerActorAbilityMinimum`:

| Slot | Role |
|---|---|
| `Prefire` | Mechanical gate. Its Commit/Cancel decision decides if the chain continues. |
| `PrefireCosmetic` | Visual/Audio lead-in. Skipped on reconcile reruns. |
| `Fire` | The effect itself (spawn projectile, trace, apply damage). |
| `FireCosmetic` | Muzzle flash, recoil anim, SFX. Skipped on reruns. |
| `PostFire` | Mechanical cleanup (chamber, heat, etc.). |
| `PostFireCosmetic` | Settle effects. Skipped on reruns. |
| `FailedFireCosmetic` | Click-whiff feedback when a phase reports non-`Fired`. |

Chain wiring (in `PreFireGun`): `Prefire->GunBinder.BindRaw(this, &FArtilleryGun::FireGun, ...)`,
`Fire->GunBinder.BindRaw(this, &FArtilleryGun::PostFireGun, ...)`. `GunBinder` is
`FArtilleryAbilityStateAlert(FArtilleryStates, int DallyFrames, const FGameplayAbilityActorInfo*, const FGameplayAbilityActivationInfo)`.

## Ability implementation contract — UArtilleryPerActorAbilityMinimum

(Public/EssentialTypes/UArtilleryAbilityMinimum.h)

- Implement **`K2_ActivateViaArtillery`** (BlueprintNativeEvent, `ArtilleryActivation`) — the ONLY
  entry point Artillery calls. Overrides of `ActivateAbility` are superseded.
- You **MUST** call `CommitAbility` and `EndAbility` appropriately or the chain stalls.
  Prefire uses commit/end vs cancel to signal whether the gun actually fires.
- Constructor fixes: `NetExecutionPolicy = LocalOnly`, `ReplicationPolicy = ReplicateNo`,
  `InstancingPolicy = InstancedPerActor`. (A comment claims NonInstanced — the constructor wins.)
- **No member state.** State lives in Artillery attributes/tags keyed by the gun's `FGunKey`
  (every ability gets `MyGunKey` via `SetGunKey`). Un-replicated state desyncs rollback.
- **No timers, no async tasks, no latent actions.** `EndAbility` does not clear them; they
  break on rollback. Use ticklites (`RequestAddTicklite`) for deferred work instead.
- Available dally frames: `AvailableDallyFrames` (latency hiding; "Dally frames don't work
  yet. But they will.").

`enum FArtilleryStates { Fired, Canceled, CanceledAfterCommit };` — abilities report outcomes
through `GunBinder` during `EndAbility`.

## Trigger guns — FSimpleTriggerGun (Public/Systems/InventoryEssentialTypes.h ~line 444)

For proc/trigger logic without the full ability chain:

```cpp
struct FSimpleTriggerGun : public FArtilleryGun
{
    FTriggerInstance MyTriggerInstance;
    virtual bool Precheck() { return true; }              // <-- override THIS
    virtual void PreFireGun(..., bool VerifiedFrame /*...*/) override
    {
        if (VerifiedFrame || Inventory_VERIFIEDFRAMETESTMODE)
            if (Precheck()) FireGun(Fired, 0, ActorInfo, ActivationInfo, false, TriggerEventData, Handle);
    }
    virtual void FireGun(...) override { FArtilleryGun::PostFireGun(...); } // skip straight through
    // + GetTypeHash / operator== on MyGunKey.GunInstanceID (required for ordered_set storage)
};
```
`FQuestTriggerGun` (Public/Systems/FQuestGun.h) shows the specialization: override
`PostFireGun` + `PostCheck()`. These are the guns `UInventoryDispatch::TriggerLinkedGuns`
owns by value — they must be hashable/comparable as shown.

## Wiring a projectile

`FGunDefinitionRow.ProjectileDefinitionID` links a projectile definition. Projectile spawn/
collision flows through `UArtilleryProjectileDispatch`; override
`FArtilleryGun::ProjectileCollided(const FSkeletonKey ProjectileKey, const FSkeletonKey HitEntity)`
for hit behavior. Base implementation: pulls owner transform as damage source and calls
`UArtilleryLibrary::ApplyDamage(MyDispatch, HitEntity, 100)`.

## Checklist before registering

- [ ] Struct is `USTRUCT(BlueprintType)` with `GENERATED_BODY()` (loader uses reflection).
- [ ] Module exposes it via `<MODULE>_API`.
- [ ] `LoadableCPP` path omits the `F` prefix (`/Script/MyModule.MyGun`).
- [ ] `MaxAmmo`/`Firerate`/`ReloadTime` set before `Initialize` (they seed default attributes).
- [ ] Owner actor already registered with `UTransformDispatch`.
- [ ] Owner has a `BeamFiringPoint` scene component if the gun needs a muzzle.
- [ ] Pattern registered (FCM) if the gun should fire from input.
