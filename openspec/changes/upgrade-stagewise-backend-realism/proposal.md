## Why

The current backend stagewise proof established that `StagewiseDistillationColumn` can show real multi-step causality, but the live realism boundary still freezes several simplifications that the updated repo contract no longer treats as acceptable long-term substrate behavior:

- dead or minimum-only pressure semantics,
- fixed internal liquid and vapor traffic,
- fixed-latent-heat `Q/λ` phase-change as the primary condenser/reboiler closure,
- proxy temperatures instead of thermodynamic thermal state,
- and an unresolved seam between hydraulic-solved outlet demand and unit-local realizability.

Gameplay is expected to migrate toward substrate-driven plant behavior later, so the backend column model needs a stronger realism boundary now, before gameplay coupling is widened.

## What Changes

- Upgrade the `StagewiseDistillationColumn` backend contract from the current constant-molar-overflow and `Q/λ`-first slice to a stronger reduced-order dynamic column slice with:
  - dynamic internal hydraulic states,
  - stronger internal pressure behavior,
  - reduced-order thermodynamic and thermal-state evolution,
  - a dynamic condenser plus reflux-drum region,
  - and a dynamic sump plus thermosyphon-inspired reboiler region.
- Keep the unit monolithic and backend-only:
  - no gameplay or Godot/client widening,
  - no new public circulation port or separate placeable condenser/reboiler unit,
  - no flooding/weeping regime model in this pack,
  - no full rigorous MESH or rate-based transport requirement in this pack.
- Strengthen connected-runtime withdrawal semantics so hydraulic-solved product-line demand stays runtime-owned while realized withdrawal remains mass-conservative and compatible with owner holdup and accepted-step realizability.
- Preserve the discovered demand-vs-realizability concern explicitly so implementation does not lose the option of internal macro-step refinement or another conservative runtime safeguard if a transient accepted step cannot be physically realized.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `connection`: strengthen dynamic distillation withdrawal and routing semantics so connected-runtime hydraulic demand remains authoritative without allowing nonphysical over-withdrawal or hidden distillation-specific line restrictions.
- `units-and-components`: replace the old reduced-order stagewise realism boundary with a stronger backend-only pressure, hydraulics, and thermal behavior contract while keeping the unit monolithic and gameplay exposure unchanged.

## Impact

- Expected implementation focus:
  - `src/modular_simulation/unit_processes/separation/stagewise_distillation.py`
  - connected-runtime demand application seams already used by dynamic units, including `src/modular_simulation/connection/runtime/process_stream_io.py`
  - proof and regression evidence in:
    - `tests/unit_process/test_layer4_stagewise_distillation.py`
    - `tests/integration/test_dynamic_process_network_workflow.py`
    - `tests/integration/test_backend_gas_starter_causal_proof.py`
    - `examples/dynamic_simulation_demos/backend_gas_starter_causal_proof.py`
- Expected live spec updates:
  - `openspec/specs/connection/spec.md`
  - `openspec/specs/units-and-components/spec.md`
- Reused substrate seams should remain the implementation basis rather than new gameplay-only helpers:
  - `src/modular_simulation/measurables/process_model.py`
  - `src/modular_simulation/framework/system.py`
  - `src/modular_simulation/thermodynamics/property_package.py`
  - `src/modular_simulation/connection/runtime/runtime.py`
