---
name: artillery-guns
description: Work with the Artillery plugin (OversizedSunCoreDev/ArtilleryEco, Unreal Engine) as an AI-native surface — manage ArtilleryGun lifecycle (define/create/register/fire/release), author new gun types, and read/write Artillery attributes, identities, vectors, and tags. Use whenever code touches UArtilleryDispatch, FArtilleryGun, UFireControlMachine, UStaticGunLoader, FAttributeMap, FGunKey, or Artillery attribute keys.
---

# Artillery Guns — AI-Native Operating Guide

Artillery is a deterministic, multithreaded gun/ability layer for UE. The core sim runs OFF the
game thread (`FArtilleryBusyWorker`, ~120hz); the game thread only applies outcomes. Almost
everything a model needs lives in `Artillery/Source/ArtilleryRuntime`.

## Operating procedure (non-negotiable)

1. **At the start of EVERY subturn, run `python scripts/pin.py emit`.** It replays
   GUARDRAILS.md (and anything else pinned) verbatim into recent context. Context attention
   is U-shaped — start and end survive, the middle rots — so a deterministic tool call beats
   a markdown reminder you'll forget. One-time setup: `python scripts/pin.py pin GUARDRAILS.md`.
   GUARDRAILS.md defines the scope fence (locomotion internals and the threaded executor are
   OUT), context discipline (grep-before-read, range reads), and behavioral rules. Optional
   fidelity self-check before finalizing claims: `python pin.py check --extract draft.txt`
   (exit 1 = a claim isn't backed by the pinned corpus; needs rapidfuzz).
2. Locomotion-shaped question? Consult [reference/locomotion-menu.md](reference/locomotion-menu.md).
   Never parse LocomoCore or the executor to answer one.
3. Stay inside the task's blast radius. If the answer lives behind the fence, stop and ask.

## Mental model (memorize this)

```
FGunDefinitionRow (DataTable)            YOU: hand-built FArtilleryGun subclass
        | IsCPP + LoadableCPP                     |
        v                                         v
UStaticGunLoader (Arsenal,           UFireControlMachine::RegisterGun()
 GameInstanceSubsystem)                       |
        | GetNewInstanceUninitialized()       v
        v                              UArtilleryDispatch::
UArtilleryDispatch::GetGun(defId,owner)  RegisterExistingGun()
        |  (UpdateProbableOwner, FGunKey minted,
        |   Initialize() -> ReadyToFire)
        +----------------+----------------+
                         v
              GunByKey[FGunKey] = gun        <-- gun EXISTS (usual path; Inventory can also own guns)
                         |
        UFireControlMachine::RegisterPattern(key, Intent, CanonPattern)
          -> PushGunToFireMapping -> Dispatch::RegisterReady(key, delegate)
                         v
        GunToFiringFunctionMapping[FGunKey]  <-- gun can FIRE
                         |
   busy worker pattern match -> triple buffer -> Tick() -> RunGuns()
     -> UArtilleryFireControl::FireGun -> gun->PreFireGun
     -> Prefire ability --(GunBinder)--> FireGun -> Fire ability --(GunBinder)--> PostFireGun
```

Two registries, two meanings — mostly. A gun normally **exists** by being in `GunByKey`, but
`UInventoryDispatch` can also own guns directly (`TriggerLinkedGuns` holds `FSimpleTriggerGun`
instances by value; `TriggerGuns_BusyWorkerOnly` maps item instances to `FGunKey`s). A gun
**fires** only when reachable from `GunToFiringFunctionMapping` (via FCM pattern binding or
`RegisterReady`) — generally; trigger guns fire through their own Precheck path. When in doubt,
trace ownership before assuming `GunByKey` is the whole truth.

## Golden rules — violate these and you get the chippershredder

1. **Guns are `USTRUCT`s, not UObjects.** Never `NewObject`/`SpawnActor` a gun. Instantiation
   goes through `UStaticGunLoader` (data-driven) or `MakeShared` + `installGun` macro (manual).
2. **Owner first.** `FArtilleryGun::Initialize` fails (returns false, `ReadyToFire` stays
   false) unless `MyProbableOwner`'s actor is already registered with `UTransformDispatch`.
3. **All gameplay state lives in attributes/tags keyed by `FSkeletonKey`.** Never store state
   on abilities or rely on UObject replication. *Only attributes replicate.*
4. **Abilities**: implement `K2_ActivateViaArtillery` ONLY; must call `CommitAbility` and
   `EndAbility`; `EndAbility` reports through `GunBinder` — but the mapping is INVERTED
   (`bWasCancelled=true` → `Fired`); pass `true` to continue the chain (see
   reference/gotchas.md §Firing). No timers, no async tasks, no latent nodes — they break
   rollback. Cosmetic phases are skipped automatically when `RerunDueToReconcile` is true.
5. **Thread discipline**: registration, pattern binding, and `GetGun` happen on the **game
   thread**. The busy worker only reads queues/buffers. `UFireControlMachine::pushPatternToRunner`
   is game-thread-only ("IF YOU DO NOT CALL THIS FROM THE GAMETHREAD, YOU WILL HAVE A BAD TIME").
6. **C++ only (for now)**: the gun loader ignores rows without `IsCPP`; BP guns are
   unimplemented (`//we don't handle bp stuff yet, sorry`).
7. **Validate keys**: `GetGun` returns `DefaultGunKey` ("M6D", instance 0) on failure. Always
   check `FGunKey::IsValidInstance()`.

## Core workflows

### A. Grant a gun by definition ID (the normal way)
```cpp
// From anywhere — routed through FRequestRouter onto the game thread.
// Binds the new gun's instance key into the requester's identity map under `Relationship`.
UArtilleryLibrary::RequestUnboundGun(
    Dispatch,                       // UArtilleryDispatch*
    E_IdentityAttrib::EquippedMainGun, // FARelatedBy
    RequesterKey,                   // FSkeletonKey of the entity receiving the gun
    FGunKey(TEXT("M6D")));          // definition ID, instance id irrelevant here
```
Or synchronously on the game thread:
```cpp
FGunKey Key = Dispatch->GetGun(TEXT("M6D"), OwnerSkeletonKey); // const, mutates registries
if (!Key.IsValidInstance()) { /* definition missing or owner not transform-registered */ }
```

### B. Hand-build and register a C++ gun
```cpp
installGun(Gun, FMyGun, FGunKey(TEXT("MyDef")), Dispatch); // TSharedPtr<FMyGun>
Gun->MaxAmmo = 12;      // set UPROPERTY stats BEFORE Initialize (they seed default attrs)
FCM->RegisterGun(Gun);             // sets owner+dispatch, Initialize(), RegisterExistingGun
FCM->RegisterPattern(Key, Intents::Intent::Fire, MyCanonPattern); // bind input -> fire mapping
```
(`installGun(Instance, Type, ...)` = `MakeShared<Type>(...)`. `FCM` = the owner's
`UFireControlMachine`; it must have run `CompleteRegistrationByActorParent` first.)

### C. Fire a gun programmatically
```cpp
UArtilleryLibrary::RequestGunFire(Dispatch, GunKey); // RequestRouter -> FireAGun on game thread
```

### D. Release / unequip
```cpp
Dispatch->ReleaseGun(Key);          // GunByKey -> PooledGuns (pool is write-only today)
FCM->UnregisterGun(Key);            // removes from GunByKey only
FCM->PopGunFromFireMapping(Key);    // removes fire delegate AND GunByKey entry (Deregister)
```

### E. Read/write attributes
```cpp
AttrPtr A = Dispatch->GetAttrib(OwnerKey, Arty::AttribKey::Ammo);
if (A) { A->SetCurrentValue(A->GetCurrentValue() - 1); }
Dispatch->AddAttrib(OwnerKey, Arty::AttribKey::Health, 100.f); // creates OR overwrites
Dispatch->GetAttribAndApplyIf(OwnerKey, Attr::Mana, [](AttrPtr M){ M->AddToCurrentValue(-10); return true; });
```
Details: [reference/attributes.md](reference/attributes.md).

## Authoring a new gun type — 30-second version

1. `USTRUCT(BlueprintType) struct YOURMODULE_API FMyGun : public FArtilleryGun { GENERATED_BODY() ... }`
   with constructor `FMyGun(const FGunKey& K, UArtilleryDispatch* D) : FArtilleryGun(K, D) {}`
   plus a default ctor, and `Initialize` overridden as `return ARTGUN_MACROAUTOINIT(MyCodeWillHandleKeys);`.
2. Add a row to the `GunDefinitions` DataTable: `GunDefinitionId`, `IsCPP=true`,
   `LoadableCPP=/Script/YourModule.MyGun` (struct name **without** the `F` prefix).
   The row's ability fields are decorative today (loader reads Id/IsCPP/LoadableCPP
   only) — inject custom abilities via `Initialize` params (see reference/authoring-guns.md).
3. Done — the loader picks it up at GameInstance init; grant it via workflow A.

Full recipe, ability-phase semantics, and the `FSimpleTriggerGun` trigger pattern:
[reference/authoring-guns.md](reference/authoring-guns.md). Scaffold generator:
`python scripts/new_gun.py --name MyGun --module-api YOURMODULE_API`.

## File map (read surgically — this codebase is dense)

Paths relative to `Artillery/Source/ArtilleryRuntime/`:

| Need | File |
|---|---|
| Dispatch: registries, GetGun, attrs, tags, RunGuns | `Public/Systems/ArtilleryDispatch.h`, `Private/ArtilleryDispatch.cpp` |
| Gun struct: phases, Initialize, attribute defaults | `Public/EssentialTypes/FArtilleryGun.h`, `Private/FArtilleryGun.cpp` |
| Gun identity | `Public/BasicTypes/FGunKey.h` |
| DataTable row schema | `Public/BasicTypes/FGunDefinitionRow.h` |
| Gun factory (Arsenal) | `Public/Systems/StaticAssetLoader.h`, `Private/StaticAssetLoader.cpp` |
| Fire control + pattern binding | `Public/Systems/UFireControlMachine.h`, `Public/EssentialTypes/ArtilleryControlComponent.h`, `Private/ArtilleryControlComponent.cpp` |
| Ability contract | `Public/EssentialTypes/UArtilleryAbilityMinimum.h` |
| Attribute enums + aliases | `Public/EssentialTypes/EAttributes.h` |
| Conserved attribute value type | `Public/BasicTypes/ConservedAttribute.h` |
| Attribute map helper | `Public/EssentialTypes/FAttributeMap.h` |
| Minimal gun example | `Public/TestTypes/FMockArtilleryGun.h` |
| Trigger-gun base + example | `Public/Systems/InventoryEssentialTypes.h` (line ~444), `Public/Systems/FQuestGun.h` |
| BP-facing API surface | `Public/Systems/ArtilleryBPLibs.h`, `Public/Systems/GunBPLibs.h` |

## References

- [reference/gun-lifecycle.md](reference/gun-lifecycle.md) — every lifecycle stage with exact signatures.
- [reference/authoring-guns.md](reference/authoring-guns.md) — expansion recipe, ability phases, trigger guns.
- [reference/attributes.md](reference/attributes.md) — attribute/identity/vector families and their APIs.
- [reference/gotchas.md](reference/gotchas.md) — known footguns, dead ends, and comment/code contradictions.
- [reference/locomotion-menu.md](reference/locomotion-menu.md) — the ONLY approved way to answer locomotion questions.
- `scripts/pin.py` — deterministic context pinning (emit/check). Adapted from the verbatim plugin's approach, generalized to a pin set.
- `scripts/new_gun.py` — gun USTRUCT scaffolder.
