## MODIFIED Requirements

### Requirement: Distillation-Column Foundation Work Targets Approved Dynamic Backend Behavior
This change SHALL keep one monolithic `StagewiseDistillationColumn` as the repo's existing reduced-order dynamic distillation baseline, SHALL additionally allow monolithic `Howard1970DistillationColumn` and `Gani1986DistillationColumn` comparison models, SHALL additionally allow backend-only `ThermoTrayDistillationColumnTotalCondenser` as the active thermo-backed actual-tray runtime model path defined by the `thermo-tray-distillation` capability, and SHALL reserve backend-only `ThermoTrayDistillationColumnPartialCondenser` as a separate sibling capability/class boundary rather than treating total-condenser overload behavior as partial-condenser semantics.

#### Scenario: Dynamic model boundary remains monolithic and names the thermo-tray family explicitly
- **WHEN** contributors inspect the runtime distillation-model contract for this change
- **THEN** `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, `Gani1986DistillationColumn`, and `ThermoTrayDistillationColumnTotalCondenser` are explicit monolithic runtime model classes
- **AND** `StagewiseDistillationColumn` remains the reduced-order baseline
- **AND** `ThermoTrayDistillationColumnTotalCondenser` is governed by the `thermo-tray-distillation` capability rather than silently repurposing the stagewise baseline
- **AND** `ThermoTrayDistillationColumnPartialCondenser` remains a separately named backend-only sibling boundary for later work rather than an overload mode of the total-condenser path
- **AND** no lumped main model is the completion contract
- **AND** the paper-faithful models do not replace the existing stagewise baseline.
