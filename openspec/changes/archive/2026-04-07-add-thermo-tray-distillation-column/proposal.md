## Why

The live distillation runtime family now has one reduced-order backend baseline (`StagewiseDistillationColumn`) and two backend-only paper-faithful comparison models (`Howard1970DistillationColumn`, `Gani1986DistillationColumn`), but it still has no general thermo-backed actual-tray runtime path that can work with arbitrary active species inside the repo's supported Peng-Robinson vapor-liquid-equilibrium envelope.

The user wants that stronger path specified before implementation, with the governing equations, startup procedure, and runtime numerical boundaries frozen explicitly so the implementation does not drift into another ad hoc or paper-shaped model. The pack must stay backend-only, avoid widening gameplay/build/client exposure, avoid a separate steady-state solver in v1, and avoid broad hard clipping except where flash failure would otherwise stall the unit.

## What Changes

- Add a new backend-only monolithic runtime model path, `ThermoTrayDistillationColumn`, for actual-tray equilibrium-stage distillation with:
  - dynamic liquid component holdups on each tray,
  - one shared equilibrium tray temperature state per tray,
  - Peng-Robinson-backed tray thermodynamic closure,
  - dynamic condenser-drum and reboiler-kettle end regions,
  - startup-and-settle operation that uses the same runtime equations rather than a separate steady-state solver,
  - and minimal numerical guards limited to epsilon floors, composition normalization, and flash-protection fallback.
- Keep `StagewiseDistillationColumn` as the existing reduced-order baseline and keep `Howard1970DistillationColumn` / `Gani1986DistillationColumn` as backend-only comparison models.
- Expand the live backend runtime contract so `ThermoTrayDistillationColumn` is a legal sibling runtime path without widening starts, public build surfaces, gameplay exposure, or controller scope.
- Keep v1 narrow and explicit:
  - backend-only,
  - PR-only vapor-liquid-equilibrium scope,
  - no Murphree tray efficiency in this pack,
  - no rate-based transport,
  - no separate steady-state solver,
  - no public gameplay/build/client exposure changes.

## Capabilities

### New Capabilities
- `thermo-tray-distillation`: backend-only actual-tray equilibrium-stage distillation with explicit thermo-backed tray closures, startup-and-settle simulation procedure, and equation-bearing runtime contract.

### Modified Capabilities
- `units-and-components`: allow `ThermoTrayDistillationColumn` as an additional backend-only monolithic runtime distillation model while preserving `StagewiseDistillationColumn` as the reduced-order baseline and keeping Howard/Gani as comparison siblings.
- `session`: relax the current stagewise-only runtime wording so backend session/runtime expectations can use `ThermoTrayDistillationColumn` without widening starts, public build lists, or controller proof scope.

## Impact

- Expected implementation focus:
  - `src/modular_simulation/unit_processes/separation/thermo_tray_distillation.py`
  - `src/modular_simulation/thermodynamics/distillation_closures.py`
  - `src/modular_simulation/thermodynamics/property_package.py`
  - `src/modular_simulation/unit_processes/separation/__init__.py`
  - `src/modular_simulation/unit_processes/__init__.py`
- Expected verification focus:
  - `tests/unit_process/test_layer4_thermo_tray_distillation.py`
  - `tests/integration/test_thermo_tray_distillation_runtime.py`
  - `examples/dynamic_simulation_demos/thermo_tray_distillation_startup_demo.py`
- Expected live spec updates:
  - `openspec/specs/thermo-tray-distillation/spec.md`
  - `openspec/specs/units-and-components/spec.md`
  - `openspec/specs/session/spec.md`
- Existing `openspec/specs/observability/spec.md` coverage is intentionally reused rather than modified in this pack because the live dynamic-distillation observability contract already covers substrate-owned distillation process-state, pressure, and duty readouts without requiring a new snapshot envelope.
- The `thermo-tray-distillation` capability is equation-bearing and must carry the governing tray balances, thermo closures, end-region balances, startup-and-settle procedure, and numerical-guard rules directly in the spec/design packet rather than collapsing them into prose.
