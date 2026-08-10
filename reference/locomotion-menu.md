# Locomotion Menu — consult this, NOT the source

Locomotion questions get answered from this menu. You do not open LocomoCore files.
You do not open the busy worker. If this menu can't answer it, escalate to the user.

## Two different things get called "locomo"

1. **LocomoCore** — a plugin at repo root (`LocomoCore/Source/LocomoCore`). It is NOT movement
   code. It's the deterministic math/data-structure toolkit ("weird math used for cameras,
   controls, fast checks" — JMK). Gun code touches it for spread/aim/spatial queries.
2. **Locomotion proper** — movement execution, living in Artillery's controllite flow and
   `ABarragePlayerController` / `BarragePlayerAgent`. This is the context shredder.

## Locomotion data flow (all you get, all you need)

```
input stream -> ArtilleryBusyWorker builds LocomotionParams {time, parent(FSkeletonKey),
  previousIndex(FArtilleryShell), currentIndex(FArtilleryShell)}      // NOT current-1, beware
  -> RequestorQueue_Locomos (MovementBuffer, plain TArray, NOT thread-safe, NOT triple-buffered)
  -> UArtilleryDispatch::RunLocomotions()
  -> KeyToControlliteMapping[parent]->ArtilleryTick(previousIndex, currentIndex, false, false)
```
- Ordering is deterministic: `operator<` sorts by (time, parent).
- AI variant: `AILocomotionParams {time, parent, moveVec}` via the AI worker thread.
- `MachineLet = IArtilleryControllite*`; register with `Dispatch->RegisterControllite(key, ptr)`.
  **There is no deregistration.** Controllites are immortal for the session.
- Interface (`EssentialTypes/ArtilleryActorControllerConcepts.h`, ~line 185):
  `virtual void ArtilleryTick(FArtilleryShell PreviousMovement, FArtilleryShell Movement,
   bool RunAtLeastOnce, bool Smear)`. Implementations: `AArtilleryController`,
  `ABarragePlayerController` (the real player locomo), `UBrokenController`, `FControllite`.
- ECS-only ticking without a controllite: `FTickECSOnly`
  (`EssentialTypes/ArtilleryECSOnlyArtilleryTickable.h`) — override
  `ArtilleryTick(uint64_t TicksSoFar)`, may ONLY touch its target skeleton key; expires when the
  physics body (`FBLet`) vanishes. Install via `StructureFullTL` + `RequestAddTicklite`.

## LocomoCore menu (what exists, when to reach for it)

| Section | Contains | Reach for it when |
|---|---|---|
| `Public/Distances/` | Z-order/Morton distances, Hilbert curves, atypical metrics | Non-euclidean comparisons, stick-in-socket control feel, fast spatial hashing |
| `Public/Geometry/` | `aim.h`, `WeaponDeflection/` (AimResponse, RecoilCurve, SampleAimProfiles, TurretRig), QuaternionAveraging, gks_hull | Aim/recoil/turret behavior, "find shit to shoot, characterize a zone, figure out how to best shoot it" |
| `Public/Structures/` | RTree (+DETERMINISM.md), TesseralTree 3D spatial index, SuperSparseSets, softheap, RadixSpline, InterpolationTable, FixedWidth/PascalCircularBuffer, ApproximateMembership (FLargeGate/SmallGate bloom-ish), ConcurrencyTypes (TimeCoheredReadHead, ParallelFixedQueueTypes, MV-regs) | Spatial queries, deterministic containers, the read-head types behind conserved attributes |
| `Public/Grouping/` | sketch/ (bottom-k/minhash/HLL — big), Miniball, CsorbaKurzerSimilarity, LSH | Set similarity, clustering, approximate counting |
| `Public/Sorts/` | Intel SIMD sorts (avx2/avx512), pdqselect, median_common | NEVER hand-roll a sort. "Always use a lib." |
| `Public/Memory/` | arena (untested), TLSF (+TLSFEW "rickety" shim), IntraTickThreadblindAlloc | Almost never. TLSF is the only battle-tested one. |
| `Public/LibMorton/` | morton 2D/3D encode/decode (+LUTs, BMI/AVX512 paths) | Z-order curve codes directly |
| Loose | `FArcShot.h`, `FFastBitTracker.h`, `FakeRandom.h` (deterministic RNG), `LocomoUtil.h`, `LowLogTimeAndRate.h`, `hedley.h` | Arced projectiles, bit tracking, deterministic randomness |

Known-bad / fragile per the author: arena (untested), TLSFEW (very rickety), RTree (permissively
licensed, largely untested), most of what used to be in Structures was removed.

## Rules of engagement

- Gun work that needs spatial/aim math: **include the header and call it**. Don't reimplement,
  don't study the implementation.
- Changing locomotion behavior itself: that's `ABarragePlayerController::ArtilleryTick`
  territory — OUT OF SCOPE for gun tasks. Escalate.
- `FArtilleryShell` = canonical movement/input snapshot type (`BasicTypes/ArtilleryShell.h`).
  Read that one header if a shell's fields are genuinely needed; it's small.
- Determinism constraints apply to anything you call from sim code: no wall-clock, no
  platform RNG (`FakeRandom` exists for a reason), fixed iteration order.
