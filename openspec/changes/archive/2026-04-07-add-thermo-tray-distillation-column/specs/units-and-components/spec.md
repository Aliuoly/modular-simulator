## MODIFIED Requirements

### Requirement: Distillation-Column Foundation Work Targets Approved Dynamic Backend Behavior
This change SHALL keep one monolithic `StagewiseDistillationColumn` as the repo's existing reduced-order dynamic distillation baseline, SHALL additionally allow monolithic `Howard1970DistillationColumn` and `Gani1986DistillationColumn` comparison models, SHALL additionally allow backend-only `ThermoTrayDistillationColumn` as the actual-tray thermo-backed runtime model path defined by the `thermo-tray-distillation` capability, and SHALL NOT define a lumped main model as the completion contract.

#### Scenario: Dynamic model boundary remains monolithic and gains a thermo-backed sibling path
- **WHEN** contributors inspect the runtime distillation-model contract for this change
- **THEN** `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, `Gani1986DistillationColumn`, and `ThermoTrayDistillationColumn` are explicit monolithic runtime model classes
- **AND** `StagewiseDistillationColumn` remains the reduced-order baseline
- **AND** `ThermoTrayDistillationColumn` is governed by the `thermo-tray-distillation` capability rather than silently repurposing the stagewise baseline
- **AND** no lumped main model is the completion contract
- **AND** the paper-faithful models do not replace the existing stagewise baseline.

### Requirement: Distillation Runtime Semantics Use Approved Backend Paths With No Shortcut Shim
This capability SHALL treat `StagewiseDistillationColumn` as the existing reduced-order runtime distillation baseline, SHALL additionally allow `Howard1970DistillationColumn` and `Gani1986DistillationColumn` as approved paper-faithful runtime comparison-model paths in this slice, SHALL additionally allow backend-only `ThermoTrayDistillationColumn` as the thermo-backed actual-tray runtime path defined by `thermo-tray-distillation`, and SHALL NOT reintroduce a `ShortcutDistillation` class, alias, or compatibility shim.

#### Scenario: Completion does not rely on a shortcut compatibility path and may use the thermo-backed sibling
- **WHEN** implementation or tests evaluate dynamic distillation behavior
- **THEN** completion may use runtime behavior from `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, `Gani1986DistillationColumn`, or `ThermoTrayDistillationColumn`
- **AND** no `ShortcutDistillation` runtime/shim pathway is required or preserved.
