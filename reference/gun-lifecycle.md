# ArtilleryGun Lifecycle — Exact Stages

All paths relative to `Artillery/Source/ArtilleryRuntime/`. Signatures verbatim from source.

## 1. Definition — `FGunDefinitionRow` (Public/BasicTypes/FGunDefinitionRow.h)

DataTable row (`FTableRowBase`). Columns:

| Field | Purpose |
|---|---|
| `FString GunDefinitionId` | Human-searchable name, e.g. `"M6D"`. Key for grants. |
| `bool IsCPP` / `bool IsBP` | Loader only processes `IsCPP` rows. BP unimplemented. |
| `FString LoadableCPP` | Struct asset path, e.g. `/Script/Bristle54.GunWeeRocket` — **no `F` prefix**. |
| `FString LoadableBP` | Unused today. |
| `FString ProjectileDefinitionID` | Links to projectile definition table. |
| `PreFireAbility` … `FailureCosmeticAbility` | 7 ability class name slots (see authoring-guns.md). |
| `BaseDamage / BaseRange / BaseRateOfFire / BaseRecoil` | Base stats (int32). |
| `E_ArtilleryIntents IntendedRegistrationPattern` | Defaults `MenuIndex`. |

## 2. Load — `UStaticGunLoader` (Public/Systems/StaticAssetLoader.h)

`UGameInstanceSubsystem` ("Arsenal"). On `Initialize`, loads the first DataTable found at:
1. `DataTable'/Game/DataTables/GunDefinitions.GunDefinitions'` (`AssetTable()`)
2. `GamePath` (same as above)
3. `EcoPath`: `DataTable'/Artillery/DataTables/GunDefinitions.GunDefinitions'`

Per `IsCPP` row: resolves `LoadableCPP` → `UScriptStruct*` via `FindObject`, then:
- `ZardozMapping[structPath] = UScriptStruct*`
- `CommonNameToProperNameMapping[GunDefinitionId] = structPath`

```cpp
virtual TSharedPtr<FArtilleryGun> GetNewInstanceUninitialized(FString RequestedGunDefinitionID);
// FMemory::Malloc(StructMetadata->GetStructureSize()) + InitializeStruct + MakeShareable.
// NOT guaranteed to work for non-Blueprint-reflected types. Must be USTRUCT.
```

## 3. Instantiation — two doors

### Door A: `UArtilleryDispatch::GetGun` (data-driven, game thread)
```cpp
FGunKey GetGun(const FString& GunDefinitionID, const FSkeletonKey& ProbableOwner) const;
```
Sequence: Arsenal lookup → `GetNewInstanceUninitialized` → `UpdateProbableOwner(ProbableOwner)` →
`MyDispatch` set → mint key `FGunKey(defId, FRequestRouter::HashDownTo32(ProbableOwner + ++monotonkey))`
→ `Initialize(Key, false)` → if `ReadyToFire`, `GunByKey->Add(Key, gun)` and return Key.
Failure returns `DefaultGunKey` (definition `"M6D"`, instance 0) — **check `IsValidInstance()`**.
(TODO in source: rename to `ConjureGun`.)

### Door B: hand-build + `UFireControlMachine::RegisterGun` (Public/Systems/UFireControlMachine.h)
```cpp
FGunKey RegisterGun(TSharedPtr<FArtilleryGun> Gun) const;
// Gun->UpdateProbableOwner(ParentKey); Gun->MyDispatch = this->MyDispatch;
// Gun->Initialize(Gun->MyGunKey, false);  -> MyDispatch->RegisterExistingGun(Gun, ParentKey)
```
Gun must already carry its `MyGunKey` (set via constructor). FCM must be registered
(`CompleteRegistrationByActorParent(IsLocalPlayerCharacter, ParentActorKey, Attributes)`).

Lower-level: `Dispatch->RegisterExistingGun(TSharedPtr<FArtilleryGun>, const ActorKey&)` just
adds to `GunByKey` — no Initialize. You own initialization ordering if you call this directly.

## 4. Initialization — `FArtilleryGun::Initialize` (Private/FArtilleryGun.cpp)

```cpp
virtual bool Initialize(const FGunKey& KeyFromDispatch, const bool MyCodeWillSetGunKey,
    UArtilleryPerActorAbilityMinimum* PF = nullptr,  * PFC = nullptr, * F = nullptr,
    * FC = nullptr, * PtF = nullptr, * PtFc = nullptr, * FFC = nullptr);
```
Does, in order:
1. Seeds **default gun attributes** (registered under the gun's own skeleton key):
   `AMMO`, `MAX_AMMO` (from `MaxAmmo`), `COOLDOWN` (from `Firerate`), `COOLDOWN_REMAINING`,
   `RELOAD` (from `ReloadTime`), `RELOAD_REMAINING`, `TICKS_SINCE_GUN_LAST_FIRED`,
   `LastFiredTimestamp`, `TRIGGER_PULLED`. → set `MaxAmmo/Firerate/ReloadTime` BEFORE init.
2. Resolves owner actor via `MyTransformDispatch->GetAActorByObjectKey(MyProbableOwner)`.
   **If the actor isn't valid, returns false.** Owner must be transform-registered first.
   Grabs `UCameraComponent` if owner is the local player.
3. Finds `BeamFiringPoint` default subobject → `FiringPointComponent`, registers it as a
   shadow transform (`MAKE_BONEKEY` + `RegisterSceneCompToShadowTransform`).
4. Creates any null ability slots as default `UArtilleryPerActorAbilityMinimum`, `AddToRoot`s
   all seven (all-or-none assignment assumption).
5. `SetGunKey` propagates the key to all 7 abilities (unless `MyCodeWillSetGunKey`).
6. `REGISTER_GUN_FINAL_TICK_RESOLVER(MyGunKey, this)` — cleanup ticklite.
7. `ReadyToFire = ReadyToFire || !MyCodeWillSetGunKey`.

## 5. Fire binding — `UFireControlMachine`

```cpp
void RegisterPattern(FGunKey GunKey, Intents::Intent BindIntent, IPM::CanonPattern Pattern);
// builds FActionBitMask from intent; pushPatternToRunner(pattern, APlayer::CABLE, mask, key)
// + PushGunToFireMapping(key)  [GAME THREAD ONLY]
```
`PushGunToFireMapping` (Private/ArtilleryControlComponent.cpp):
```cpp
Arty::FArtilleryFireGunFromDispatch Inbound;
Inbound.BindUObject(this, &UArtilleryFireControl::FireGun);
MyDispatch->RegisterReady(ToFire, Inbound);   // -> GunToFiringFunctionMapping
MyGuns.Add(ToFire);
```

## 6. Firing — two triggers

**Input-driven**: busy worker pattern match writes `EventBufferInfo` (with `GunKey`) to
`RequestorQueue_Abilities_TripleBuffer` → game thread `UArtilleryDispatch::Tick` → `RunGuns()`
→ executes delegate from `GunToFiringFunctionMapping` → `UArtilleryFireControl::FireGun`:
builds `FGameplayAbilitySpec` from `Gun->Prefire`'s class, calls `Gun->PreFireGun(...)`.

**Programmatic**: `UArtilleryLibrary::RequestGunFire(Dispatch, GunKey)` →
`RequestRouter->GunFired(key, GetShadowNow())` → `ProcessRequestRouterGameThread` case
`ArtilleryRequestType::FireAGun` → same delegate path. (`Dispatch->QueueFire` exists but is
"unused atm".)

**Ability chain** (Private/FArtilleryGun.cpp): `PreFireGun` binds `GunBinder` delegates —
`Prefire → FireGun`, `Fire → PostFireGun` — then activates `Prefire`. Each ability's
`EndAbility` reports an `FArtilleryStates` outcome; `Fired` continues the chain, anything else
runs `FailedFireCosmetic`. Cosmetic phases activate only when `!RerunDueToReconcile`.

## 7. Attribute storage during life

`FAttributeMap(FSkeletonKey parentKey, UArtilleryDispatch*, TMap<AttribKey,double> defaults)`
registers itself via `RegisterOrAddAttributes` (merges into an existing map if present);
its destructor calls `DeregisterAttributes`. Guns get one in `Initialize`; entities get one in
`UFireControlMachine::CompleteRegistrationByActorParent`.

## 8. Death — pick precisely

| Call | GunByKey | Fire mapping | Pool | Notes |
|---|---|---|---|---|
| `Dispatch->ReleaseGun(Key)` | removed | **kept** | added to `PooledGuns` | Returns false if already released. Pool is never drained (TODO). |
| `Dispatch->UnregisterExistingGun(Key)` | removed | kept | — | Inline; no lifecycle checks. |
| `Dispatch->Deregister(Key)` | removed | removed | — | Also called by `PopGunFromFireMapping`. |
| `~FArtilleryGun` | calls `Deregister` if `IsGunLive(MyGunKey)` | — | — | Also `RemoveFromRoot`s the 7 abilities, resets `MyAttributes`. |
| `UArtilleryFireControl::OnComponentDestroyed` | emergency `Deregister` for all `MyGuns` | — | — | Safety net. |

Mismatched pairs leak: releasing from `GunByKey` without popping the fire mapping leaves a
dangling delegate that `RunGuns` will still execute (it `FindRef`s the gun — null gun +
bound delegate logs an error and skips in the RequestRouter path; the triple-buffer path
executes the delegate with a null `TSharedPtr<FArtilleryGun>`).
