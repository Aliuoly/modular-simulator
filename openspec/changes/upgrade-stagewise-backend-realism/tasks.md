## Dependency gate

- [ ] D0 Confirm this change pack is approved, linked Beads execution items exist, and implementation starts from this pack as the active source of truth for `upgrade-stagewise-backend-realism`.

## Wave 1 — Write the failing realism and seam tests first

- [ ] 1.1 `simulation-realism-required: true` Expand `tests/unit_process/test_layer4_stagewise_distillation.py` with red coverage for dynamic internal hydraulic states, stronger pressure behavior, reduced-order thermodynamic temperature response, and conservative withdrawal realizability.
- [ ] 1.2 `simulation-realism-required: true` Extend `tests/integration/test_dynamic_process_network_workflow.py` with a red connected-runtime scenario that applies hydraulic-solved outlet demand to distillate/bottoms ports and proves the column does not overdraw owner holdup when local realizability and accepted-step demand diverge.
- [ ] 1.3 `simulation-realism-required: true` Rewrite `tests/integration/test_backend_gas_starter_causal_proof.py` so the backend proof requires multi-step pressure, hydraulic, and thermal response and fails if proxy temperatures, dead pressure, or fixed internal stage traffic remain the effective behavior.
- [ ] 1.4 Run the red boundary:
  - `uv run pytest tests/unit_process/test_layer4_stagewise_distillation.py -k "pressure or hydraulic or thermal or withdrawal"`
  - `uv run pytest tests/integration/test_dynamic_process_network_workflow.py -k "stagewise or distillation or withdrawal"`
  - `uv run pytest tests/integration/test_backend_gas_starter_causal_proof.py`
  - Expected evidence: the new tests fail against the old fixed-flow, dead-pressure, proxy-temperature, and `Q/λ`-first closure.

## Wave 2 — Replace the old stagewise core closures

- [ ] 2.1 `simulation-realism-required: true` Add the concrete reduced-order dynamic states in `src/modular_simulation/unit_processes/separation/stagewise_distillation.py`:
  - per-stage liquid energy states `stage_internal_energy_J[i]`,
  - `reflux_drum_internal_energy_J`,
  - `bottoms_sump_internal_energy_J`,
  - `top_vapor_holdup_mol`,
  - `bottom_vapor_holdup_mol`,
  while retaining conserved component-holdup ownership in the existing stage, drum, and sump mole states.
- [ ] 2.2 `simulation-realism-required: true` Replace fixed internal `stage_liquid_flow_mol_s` and `stage_vapor_flow_mol_s` with the frozen reduced-order hydraulic laws from `design.md`:
  - liquid downflow from holdup/head using a smooth weir/downcomer-style relation `L_i = C_L_i * max(h_i - h_weir_i, 0)^(3/2)`,
  - vapor upflow from pressure-drop availability using `V_i = C_V_i * sqrt(DeltaP_available_i / max(rho_vap_i, eps))`,
  - no flooding/weeping logic in this pack.
- [ ] 2.3 `simulation-realism-required: true` Add stronger internal pressure treatment by deriving runtime pressures from the new vapor-holdup states and preserving the minimum shared `column_pressure_pa` interface used by existing runtime and connection surfaces.
- [ ] 2.4 `simulation-realism-required: true` Implement the frozen thermal and equilibrium closure stack:
  - per-stage energy balances,
  - reduced-order multicomponent `K`-value stage equilibrium with weak pressure/temperature dependence,
  - property-package-backed top and bottom flash use where the design requires it,
  - no proxy temperatures and no bare fixed-latent-heat `Q/λ` primary closure.
- [ ] 2.5 `simulation-realism-required: true` Implement the specific monolithic top/bottom regions frozen in `design.md`:
  - top = dynamic condenser plus reflux-drum region,
  - bottom = dynamic sump plus thermosyphon-inspired reboiler region with named internal circulation heuristic,
  - no separate placeable condenser/reboiler unit and no public circulation seam.
- [ ] 2.6 `simulation-realism-required: true` Keep the column monolithic and avoid hidden distillation-specific line restrictions that should instead belong on connection-network hydraulic components.

## Wave 3 — Make product withdrawals network-compatible and conservative

- [ ] 3.1 `simulation-realism-required: true` Add `apply_requested_outlet_through_flow_demand(...)` support to `src/modular_simulation/unit_processes/separation/stagewise_distillation.py` so connected-runtime hydraulic-solved outflows can drive distillate and bottoms withdrawal requests without bypassing owner holdup.
- [ ] 3.2 `simulation-realism-required: true` Keep connected-runtime demand semantics aligned with the existing outlet-demand callback path in `src/modular_simulation/connection/runtime/process_stream_io.py`, `src/modular_simulation/connection/runtime/runtime.py`, and `src/modular_simulation/connection/runtime/thermo_coupling.py`; only widen those files if fresh evidence proves the current callback path is insufficient.
- [ ] 3.3 `simulation-realism-required: true` Implement the preferred mismatch handling order frozen in `design.md`: when accepted-step hydraulic demand exceeds locally realizable withdrawal, try internal substep refinement first and only then conservatively cap realized withdrawal if the step still cannot be physically realized.
- [ ] 3.4 `simulation-realism-required: true` Prove in tests that the final handling order never creates component moles, never overdraws owner holdup, and never fakes a satisfied line flow when the local state cannot realize it.
- [ ] 3.5 `simulation-realism-required: true` Keep any needed substep refinement internal to runtime stepping and do not widen public session, controller, or actuation contracts.

## Wave 4 — Refresh proof/example and runtime observability evidence

- [ ] 4.1 `simulation-realism-required: true` Update `examples/dynamic_simulation_demos/backend_gas_starter_causal_proof.py` so the proof demonstrates the stronger pressure, hydraulic, and thermal realism boundary without overclaiming flooding/weeping, full rigorous MESH, or gameplay coupling.
- [ ] 4.2 `simulation-realism-required: true` Expand runtime-owned process-state evidence in `tests/integration/test_backend_gas_starter_causal_proof.py` and `tests/integration/test_dynamic_process_network_workflow.py` so top/bottom pressure, hydraulic state, thermal state, and conservative withdrawal behavior are visible through connected-runtime observability.
- [ ] 4.3 `simulation-realism-required: true` Re-check `examples/unit_process_flowsheet/gas_2_teg_dehydration.py` and nearby gas-stage examples/docs for realism drift that would contradict the new backend boundary, and if a broader follow-on is discovered, create Beads work for it rather than broadening this pack.

## Wave 5 — Independent review gate

- [ ] 5.1 `simulation-realism-required: true` Run `hybrid-code-reviewer` and `simulation-advisor` in parallel on the upgraded backend stagewise slice.
- [ ] 5.2 `simulation-realism-required: true` Do not close implementation until review evidence is non-blocking and still shows:
  - dynamic internal stage traffic rather than fixed global L/V constants,
  - stronger internal pressure and thermal behavior rather than dead/proxy placeholders,
  - connected-runtime hydraulic demand staying explicit while realized withdrawal remains conservative,
  - no gameplay, Godot, or public controller/actuation widening,
  - flooding/weeping explicitly deferred.

## Wave 6 — Verification and closure hygiene

- [ ] 6.1 `simulation-realism-required: true` Run the focused and full verification set:
  - `uv run pytest tests/unit_process/test_layer4_stagewise_distillation.py`
  - `uv run pytest tests/integration/test_dynamic_process_network_workflow.py -k "stagewise or distillation or withdrawal"`
  - `uv run pytest tests/integration/test_backend_gas_starter_causal_proof.py`
  - `uv run python examples/dynamic_simulation_demos/backend_gas_starter_causal_proof.py`
  - `openspec validate --specs --strict --no-interactive`
- [ ] 6.2 Expected evidence:
  - internal stage traffic changes dynamically with runtime state rather than fixed global liquid/vapor constants
  - pressure and thermal outputs evolve from stronger internal state rather than dead/proxy placeholders
  - connected-runtime product withdrawals follow hydraulic-solved demand conservatively and do not overdraw owner holdup
  - no gameplay, Godot, or public controller/actuation widening occurs
  - flooding/weeping remain explicitly deferred
- [ ] 6.3 Sync live `openspec/specs/connection/spec.md` and `openspec/specs/units-and-components/spec.md` after code, verification, and review are complete, and update the linked Beads items with final evidence before closure.
