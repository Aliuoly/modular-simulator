# Two-Pass Remediation Backlog and Sequencing

Plan: `process-unit-misalignment-two-pass`
Task: `10 - Consolidate two-pass remediation backlog and sequencing`

## Backlog Intent

- This backlog merges `.sisyphus/evidence/task-5-pass1-register.md` and `.sisyphus/evidence/task-9-pass2-register.md` into one execution-ready sequence for Task 11 and the final verification wave.
- The backlog preserves the user-selected two-pass strategy: Pass 1 control-contract alignment first, Pass 2 broader consistency work second.
- Oracle-inspired severity order is preserved as verified: Pass 1 `critical` before Pass 1 `high` before Pass 1 `medium` before Pass 1 `low`, then Pass 2 `high` before Pass 2 `medium`; Pass 2 benign `low` divergences stay deferred unless new verified evidence upgrades them.
- No verified evidence in the source registers justifies changing that severity order.

## Global Execution Guardrails

- `dependency`: finish each backlog group in order, because Task 10 depends on Tasks 5 and 9, Task 10 blocks Task 11, and Pass 2 consistency fixes must not rewrite unresolved Pass 1 control contracts.
- `rollback guardrail`: if any remediation changes controller binding, subsystem publication, tag naming, or runtime validation behavior, revert to the last passing group boundary before continuing.
- `stop condition`: stop the sequence when any group introduces failing targeted tests, breaks controller-resolvability assumptions, changes verified pass ownership, or requires severity reprioritization without new anchored evidence.
- `priority order`: remediate contract-exposure risks before naming cleanup, and remediate runtime-safety inconsistencies before benign divergence documentation.

## Dependency-Aware Backlog

### Group 1, Pass 1 highest-risk contract exposure

- `priority order`: 1
- `dependency`: start here. This group gates every later group because it establishes first-class or adapter-backed MV expectations.
- `units`: `PFR`, `ConversionReactor`, `HeatExchanger`
- `scope`: Pass 1 contract work only. Expose or define safe runtime actuator contracts before broader naming or consistency normalization.
- `why now`: `PFR` is the only `critical` Pass 1 row. `ConversionReactor` and `HeatExchanger` are the top `high` Pass 1 rows and remain `not-ready` for controller use.
- `rollback guardrail`: do not merge a redesign that changes reactor physics, stoichiometry, or exchanger performance semantics while trying to expose runtime MVs.
- `stop condition`: stop if a proposed fix needs a physics-law change, removes current unit-test coverage, or cannot preserve controller-readiness reasoning from Task 5.
- `task11 reuse`: Task 11 should verify this group first because later groups assume these units have stable actuator-contract decisions.

### Group 2, Pass 1 adapter and coverage completion

- `priority order`: 2
- `dependency`: starts after Group 1 establishes the portfolio pattern for explicit MV exposure or approved adapter policy.
- `units`: `ShortcutDistillation`, `CSTR`, `Pump`, `ComponentSeparator`
- `scope`: Pass 1 contract work only. `ShortcutDistillation` is mainly coverage completion, while `CSTR`, `Pump`, and `ComponentSeparator` need adapter-safe exposure patterns consistent with Group 1.
- `why now`: these units are Pass 1 `medium`, but they directly influence later Pass 2 naming and semantic cleanup around setpoints, pressure, and split-allocation contracts.
- `rollback guardrail`: keep `CSTR` internal control behavior, `Pump` dimensional behavior, and `ComponentSeparator` vector-shape expectations intact unless equivalent regression coverage lands in the same change.
- `stop condition`: stop if adapter-backed changes create ambiguous MV dimensionality, remove existing direct-ready behavior, or downgrade existing strong unit coverage.
- `task11 reuse`: Task 11 should run the controller/subsystem bundle after this group because it closes the remaining Pass 1 contract hotspots.

### Group 3, Pass 1 direct-ready hardening

- `priority order`: 3
- `dependency`: starts after Groups 1 and 2 confirm the shared direct-MV versus adapter policy.
- `units`: `Splitter`, `FlashDrum`, `Valve`, `HeaterCooler`
- `scope`: Pass 1 hardening only. Preserve direct-ready contracts and close guardrail or configuration gaps without redesigning already controller-ready surfaces.
- `why now`: these rows are Pass 1 `low`, but they provide the safe baseline templates for the rest of the library. `HeaterCooler` remains the gold standard, `FlashDrum` needs mode-gated deployment guardrails, `Valve` needs template retention, and `Splitter` needs dimensionality-safe examples.
- `rollback guardrail`: do not weaken existing direct `T.CONTROLLED` contracts or remove known-good integration patterns, especially the `HeaterCooler` controller path.
- `stop condition`: stop if a hardening change converts a direct-ready unit into adapter-only behavior or breaks the existing controller integration baseline.
- `task11 reuse`: Task 11 should treat this group as the final Pass 1 regression gate before any Pass 2 execution.

### Group 4, Pass 2 runtime-safety consistency

- `priority order`: 4
- `dependency`: starts only after all Pass 1 groups are stable, because these fixes can alter validation and runtime semantics used by controller-facing paths.
- `units`: `CSTR`, `PFR`, `ConversionReactor`, `Mixer`, `Splitter`, `Pump`, `HeaterCooler`
- `scope`: Pass 2 consistency work only. Address verified `high` severity semantics without reopening Pass 1 severity.
- `included rows`:
  - reactor-family validation and clamping gap: `CSTR`, `PFR`, `ConversionReactor`
  - passive pressure-contract gap: `Mixer`, `Splitter`
  - pump zero-flow algebraic versus `step()` mismatch: `Pump`
  - shared parameter-name contract divergence: `HeaterCooler`, `ConversionReactor`
- `why now`: these are the Pass 2 `high` rows with direct runtime-safety or controller-intent impact.
- `rollback guardrail`: preserve the verified distinction between contract exposure and consistency cleanup. Do not use this group to invent new actuators, remove aliases blindly, or collapse passive-unit semantics into reactor semantics without evidence.
- `stop condition`: stop if a consistency fix changes public contracts without a migration path, breaks pass-specific evidence links, or promotes a benign divergence into remediation work without new proof.
- `task11 reuse`: Task 11 should rerun the reactor, runtime-mutation, and transaction-atomicity tests immediately after this group.

### Group 5, Pass 2 portfolio naming and cross-unit coherence

- `priority order`: 5
- `dependency`: starts after Group 4 stabilizes runtime semantics, because naming cleanup should reflect the final validated contracts rather than precede them.
- `units`: `Valve`, `FlashDrum`, `ShortcutDistillation`, `ComponentSeparator`, `HeatExchanger`, `HeaterCooler`, `CSTR`, `PFR`, `ConversionReactor`, `Splitter`
- `scope`: Pass 2 consistency work only. Normalize or alias verified `medium` severity naming and shared-contract mismatches.
- `included rows`:
  - valve algebraic bound revalidation gap: `Valve`
  - thermal selector name divergence: `HeaterCooler`, `FlashDrum`, `ConversionReactor`
  - implicit setpoint name and tag divergence: `CSTR`, `HeaterCooler`, `FlashDrum`, `ShortcutDistillation`
  - split allocation name and tag divergence: `Splitter`, `ComponentSeparator`
  - thermal conductance alias divergence: `HeatExchanger`, `CSTR`, `PFR`
- `why now`: these rows are important, but they depend on stable contract and validation decisions from the first four groups.
- `rollback guardrail`: prefer alias maps, compatibility shims, or explicit metadata before renaming public fields outright.
- `stop condition`: stop if a naming cleanup breaks backward compatibility, obscures prior evidence anchors, or forces Task 11 to reinterpret the Pass 1 gold-standard `HeaterCooler` path.
- `task11 reuse`: Task 11 should verify that all evidence artifacts and cross-links still map deterministically after naming normalization.

### Group 6, Deferred benign divergence documentation

- `priority order`: 6
- `dependency`: only after Groups 1 through 5 pass targeted verification.
- `units`: `HeaterCooler`, `FlashDrum`, `CSTR`, `PFR`, `Mixer`, `ComponentSeparator`, `ShortcutDistillation`, `ConversionReactor`, `HeatExchanger`
- `scope`: no immediate remediation. Record and monitor Pass 2 benign `low` divergences.
- `why deferred`: the source register already classifies these rows as benign. There is no verified evidence that they should outrank actionable work.
- `rollback guardrail`: do not convert documentation-only clarification into behavior changes during this group.
- `stop condition`: stop if new evidence shows one of these divergences causes contract breakage, because that requires a fresh severity decision before implementation.
- `task11 reuse`: Task 11 should confirm the backlog still leaves benign rows deferred unless a new artifact records verified escalation.

## Unit-by-Unit Priority Map

| unit | pass ownership | priority order | dependency | rollback guardrail | stop condition |
| --- | --- | --- | --- | --- | --- |
| `PFR` | Pass 1 first, Pass 2 later | `1`, then `4`, then `5` | Group 1 starts the backlog | Keep thermal-actuation exposure separate from reactor physics changes | Stop on any fix that changes physics instead of contract/validation behavior |
| `ConversionReactor` | Pass 1 first, Pass 2 later | `1`, then `4`, then `5` | Follows `PFR` in Group 1 | Keep mode/stoichiometric model definition separate from actuator exposure | Stop on any unverified severity escalation or contract rename without migration |
| `HeatExchanger` | Pass 1 first, Pass 2 later | `1`, then `5` | Completes Group 1 pattern | Preserve exchanger arrangement/performance semantics while exposing safe contracts | Stop if naming cleanup starts before actuator-contract decision is stable |
| `ShortcutDistillation` | Pass 1, then Pass 2 naming | `2`, then `5` | Depends on Group 1 adapter/direct-ready policy | Treat `reflux_ratio_setpoint` as coverage work first, not redesign | Stop if direct-ready surfaces are redesigned instead of tested |
| `CSTR` | Pass 1, then Pass 2 | `2`, then `4`, then `5` | Depends on Group 1 pattern for internal-control exposure | Preserve embedded level-control semantics until explicit replacement is verified | Stop if internal-law behavior changes without same-change regression proof |
| `Pump` | Pass 1, then Pass 2 | `2`, then `4` | Depends on Group 1 adapter policy | Preserve scalar actuation bounds and current dimensional behavior | Stop if zero-flow alignment changes only one API path |
| `ComponentSeparator` | Pass 1, then Pass 2 naming | `2`, then `5` | Depends on Group 1 vector-adapter policy | Preserve species-vector meaning and shape checks | Stop if split-contract naming changes before vector mapping is explicit |
| `Splitter` | Pass 1 hardening, then Pass 2 | `3`, then `4`, then `5` | Wait for adapter/direct-ready policy to settle | Keep direct-ready vector MV contract intact | Stop if pressure-contract work breaks split-ratio controller readiness |
| `FlashDrum` | Pass 1 hardening, then Pass 2 naming | `3`, then `5` | Wait for Pass 1 direct-ready baseline checks | Preserve mode-gated controller-ready path | Stop if selector cleanup changes existing mode behavior |
| `Valve` | Pass 1 hardening, then Pass 2 validation | `3`, then `5` | Follows direct-ready baseline retention | Keep `open_fraction` as the direct MV reference pattern | Stop if validation hardening weakens direct MV semantics |
| `HeaterCooler` | Pass 1 hardening, then Pass 2 | `3`, then `4`, then `5` | Remains the Pass 1 reference contract | Preserve the known-good controller coupling path | Stop if any cleanup breaks the existing gold-standard integration flow |
| `Mixer` | Pass 2 only | `4`, then `6` | Wait for all Pass 1 groups to finish | Keep passive-unit scope separate from Pass 1 contract work | Stop if passive pressure normalization is used to invent new control surfaces |

## Sequencing Notes For Task 11 And Final Verification Wave

- Task 11 should verify backlog completion in group order, not as a flat batch, so failures identify the exact dependency boundary that regressed.
- The final verification wave should preserve the same order: Pass 1 contract groups first, Pass 2 runtime-safety second, Pass 2 naming third, benign divergences last.
- If a later group fails, resume from the last passing priority order group after rollback rather than continuing forward.
