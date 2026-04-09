## Why

The current thermo-backed tray column freezes a constant top-pressure anchor, a constant per-tray pressure increment, and a liquid-only total-condenser drum. That contract cannot represent three important plant behaviors the user explicitly wants to preserve as part of the substrate realism boundary:

- insufficient condenser duty leaving a non-condensed vapor fraction,
- top-headspace pressure buildup that feeds back into tray hydraulics and outlet conditions,
- and subcooled condenser/drum liquid rather than forcing the condenser outlet to bubble point.

The current implementation also overrides the base `ProcessModel.step()` path and bypasses the framework solver options, even though the repo’s intended runtime contract is that the base process-model step owns integration through `solve_ivp` / LSODA unless a unit has a narrowly justified reason not to.

This change matters now because the thermo tray column is the repo’s physically grounded distillation path. The total-condenser top closure needs an honest pressure/headspace model before later control-facing work can build on it without inheriting a fake constant-pressure top end.

## What Changes

- Upgrade the thermo-tray distillation contract from a liquid-only total-condenser drum to an explicit **total-condenser with vapor headspace and overload behavior** model.
- Split the current public thermo-tray class semantics into:
  - an explicit **total-condenser** runtime path, and
  - a separate **partial-condenser** sibling path for later work, so insufficient cooling in the total-condenser model does not silently change topology.
- Replace the constant top-pressure anchor and constant per-tray pressure increment with a stronger pressure contract:
  - dynamic top vapor-headspace pressure,
  - liquid outlet pressures derived from headspace pressure plus hydrostatic head,
  - dynamic bottom pressure derived from top pressure plus tray/column pressure-drop closure,
  - tray pressures interpolated between live end pressures.
- Freeze explicit condenser-side governing equations for:
  - `realized_condensed_flow`,
  - `non_condensed_flow`,
  - headspace pressure,
  - condenser/drum subcooling energy balance,
  - and accepted tray pressure-drop decomposition.
- Keep blanket-gas addition and vent/backpressure capability in scope as **optional physical ports/boundaries** on the total-condenser unit, while keeping pressure-control policy itself outside the unit as a later controller concern.
- Restore the thermo-tray runtime contract to the framework-owned solver path so the unit does not keep bypassing LSODA through a private explicit-Euler step implementation.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `thermo-tray-distillation`: replace the current generic thermo-tray top-pressure and top-end closure with an explicit total-condenser-overload contract, freeze the reduced-order PR-bubble-plus-excess-headspace-pressure equations, keep partial-condenser semantics explicitly separate from total-condenser overload, and restore framework-solver alignment.
- `units-and-components`: relax the current thermo-tray family wording so the backend runtime contract names the upgraded total-condenser implementation path explicitly and reserves a separate partial-condenser sibling family without widening gameplay/client exposure.

## Impact

- Expected implementation focus:
  - `src/modular_simulation/unit_processes/separation/thermo_tray_distillation.py`
  - `src/modular_simulation/measurables/process_model.py` only if needed to preserve solver-path expectations cleanly
  - `src/modular_simulation/thermodynamics/distillation_closures.py` only where new thermo helper seams are required by the frozen equations
  - connection/hydraulic participation surfaces already used by process units if pressure-state exposure needs extension
  - thermo-tray demos and tests under `examples/dynamic_simulation_demos/` and `tests/`
- Expected live spec updates:
  - `openspec/specs/thermo-tray-distillation/spec.md`
  - `openspec/specs/units-and-components/spec.md`
- Equation-bearing capabilities in this change pack:
  - `thermo-tray-distillation`
  This spec must preserve governing equations, symbol definitions, closures/correlations, and named assumptions explicitly so planning does not collapse the physics into vague prose. The separate partial-condenser path is reserved by the contract boundary in this same capability rather than by a second equation-bearing spec in this pack.
