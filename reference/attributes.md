# Artillery Attributes, Identities, Vectors, Tags

Everything gameplay-mutable is one of four kinds, keyed by `FSkeletonKey`, stored in
dispatch-owned registries. *Only attributes replicate.* Member state on guns/abilities does not.

## The three attribute families (Public/EssentialTypes/EAttributes.h)

```cpp
using AttribKey = E_AttribKey;  using Attr = AttribKey;   // scalars (double)
using Ident     = E_IdentityAttrib;                       // keys (relationships)
using Attr3     = E_VectorAttrib;                         // FVector
```

**`E_AttribKey`** — entity: `Speed, Health, MaxHealth, HealthRechargePerTick, Shields,
MaxShields, ShieldsRechargePerTick, Mana, MaxMana, ManaRechargePerTick, TicksTilJumpAvailable,
JumpsAvailable, JumpHeight, ProposedDamage, StunDuration, PingedDuration, PerHitPingedDuration,
IsLockedOn, IsActive, IFrames`. Gun: `Ammo, MaxAmmo, FireCooldown, FireCooldownRemaining,
ReloadTime, ReloadTimeRemaining, Range, TicksSinceLastFired, LastFiredTimestamp, TriggerPulled`.
Handy constants exist: `Arty::AMMO, MAX_AMMO, COOLDOWN, COOLDOWN_REMAINING, RELOAD,
RELOAD_REMAINING, TICKS_SINCE_GUN_LAST_FIRED, TRIGGER_PULLED, HEALTH, MAXHEALTH, MANA
(= DASH_CURRENCY), MAXMANA, PROPOSED_DAMAGE`.

**`E_IdentityAttrib`** (alias `FARelatedBy`) — `Target, EquippedMainGun, EquippedSecondaryGun,
EquippedMoveAbility, EquippedDefAbility, EquippedDashAbility, CurrentCharacter,
CurrentController, MainGunModel, Squad, Self`. Values are `FConservedAttributeKey` — this is
how "which gun does this entity have equipped" is stored.

**`E_VectorAttrib`** — `AimVector, ChaosControlVector, ArtInputDeltaUnitVector, TrueLookVector,
UControllerOnlyLookVector, FacingVector, Velocity, Forces, InitialPositionVec,
InitialRotationVec, Destination, Location, TargetLocation`.
`Location` is **at least one tick old** — use the estimator with it.

## Value semantics — FConservedAttributeData (Public/BasicTypes/ConservedAttribute.h)

```cpp
void   SetCurrentValue(double);   double GetCurrentValue();   void AddToCurrentValue(double);
void   SetBaseValue(double|float); double GetBaseValue();
double GetPriorValue();           // previous current value
```
Records its last ~128 changes in circular history buffers (debug + future granular rollback).
Current value writes go through a time-cohered read head — safe to write from the busy worker,
read from the game thread. Pointer types: `AttrPtr`, `IdentPtr`, `Attr3Ptr` (TSharedPtr).

## Dispatch APIs (UArtilleryDispatch)

Scalars — storage is a `seq::concurrent_map` cuckoo hash:
```cpp
AttrMapPtr GetAttribMap(FSkeletonKey Owner) const;                  // whole map, one lookup
AttrPtr    AddAttrib(FSkeletonKey Owner, AttribKey, float Value=0); // creates OR overwrites
AttrPtr    GetAttrib(FSkeletonKey Owner, AttribKey) const;          // nullptr if missing
AttrPtr    GetAttribRequired(const FSkeletonKey&, AttribKey) const; // checkf if missing. DEPRECATED.
bool       GetAttribAndApplyIf(FSkeletonKey, AttribKey, const auto& lambda); // lambda(AttrPtr)->bool
void       RegisterOrAddAttributes(FSkeletonKey, AttrMapPtr);       // MERGES into existing map
void       DeregisterAttributes(FSkeletonKey);
```
Prefer `GetAttribMap` when touching several attributes of one key (single map fetch).

Identities:
```cpp
IdentPtr GetIdent(FSkeletonKey, Ident) const;
IdentPtr GetOrAddIdent(FSkeletonKey, Ident) const;   // creates map+entry if absent
IdMapPtr GetRelationships(FSkeletonKey) const;       // mutable — "be like me: demure"
void     RegisterOrAddRelationships(FSkeletonKey, IdMapPtr);
void     DeregisterRelationships(FSkeletonKey);
```

Vectors:
```cpp
Attr3Ptr GetVecAttr(FSkeletonKey, Attr3) const;
void     RegisterOrAddVecAttribs(FSkeletonKey, Attr3MapPtr);
void     DeregisterVecAttribs(FSkeletonKey);
```

Tags — `AtomicTagArray`, plus inventory result-set maintenance on native-tag paths:
```cpp
void AddTagToEntity(FSkeletonKey, const FGameplayTag|FNativeGameplayTag&) const;
void RemoveTagFromEntity(FSkeletonKey, const FGameplayTag|FNativeGameplayTag&) const;
bool DoesEntityHaveTag(FSkeletonKey, const FGameplayTag&) const;
FConservedTags RegisterOrAddGameplayTags(FSkeletonKey, GameplayTagContainerPtrInternal);
FConservedTags GetExistingConservedTags(FSkeletonKey);
FConservedTags GetOrRegisterConservedTags(FSkeletonKey, bool& outExisting);
void         DeregisterGameplayTags(FSkeletonKey);
```

## FAttributeMap (Public/EssentialTypes/FAttributeMap.h) — the easy button

```cpp
TSharedPtr<FAttributeMap> Attrs = MakeShared<FAttributeMap>(
    OwnerKey, Dispatch, TMap<AttribKey,double>{{ Arty::HEALTH, 100.0 }, { Arty::MANA, 50.0 }});
Attrs->Add({{ Arty::PROPOSED_DAMAGE, 10.0 }});  // later additions
// destructor auto-calls Dispatch->DeregisterAttributes(OwnerKey)
```
Registration merges with any existing map for the key. This is what gun `Initialize` and
`UFireControlMachine::CompleteRegistrationByActorParent` use under the hood.

## Blueprint surface (Public/Systems/ArtilleryBPLibs.h — UArtilleryLibrary)

`K2_GetAttrib(ctx, Owner, E_AttribKey, &bFound)`, `K2_GetMyAttrib(Actor, ...)`,
`K2_GetPlayerAttrib(ctx, ...)`, `GetAnyPlayerAttrib`, `K2_GetIdentity(ctx, Owner,
E_IdentityAttrib, &bFound)`, `K2_GetPlayerIdentity`, `K2_GetPlayerVector` /
`K2_GetAnyPlayerVector`, `K2_GetTagsByKey`, `K2_GetPlayerTags`,
`K2_ApplyDamage(ctx, Target, Damage, &bSuccess)`, `K2_GetBarrageLocIfAny`,
`K2_GetLocalPlayerVectors`, `K2_GetLocalPlayerVelocity`. `UGunUtilLibrary`
(Public/Systems/GunBPLibs.h): spread math (`K2_ApplyRandomSpreadToVector` etc.) and
`K2_ApplyDamage(ObjectKey, Damage, Dispatch, isEnemyTarget)`.

Damage: `UArtilleryLibrary::ApplyDamage(Dispatch, Target, Damage, SourceLocation=Zero)` —
reads `ProposedDamage`/health attributes; the standard mutation path for hits.
