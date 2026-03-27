## Dependency gate

- [x] D0 Wave 0 artifacts must be rewritten and approved before any additional implementation starts.
- [x] D1 Preserve current honesty boundary during implementation:
  - `place_shortcut_distillation_column` stays hidden from current topology-only supported-build lists
  - current topology-only starts continue rejecting direct install attempts with `unsupported_on_start`
  - `_install_unit()` invalid-config translation boundary remains unchanged.

## Wave 0 — Rewrite and realign artifacts (this packet)

- [x] 0.1 Rewrite `proposal.md` to pivot from steady-state shortcut completion to multicomponent stage-by-stage dynamic distillation-column scope.
- [x] 0.2 Rewrite `design.md` with execution-ready sections (Context / Goals / Non-Goals / Decisions / Risks / Verification Strategy) and explicit expanded monolithic architecture.
- [x] 0.3 Rewrite this `tasks.md` into dependency-gated waves with honest unchecked status for the new target.
- [x] 0.4 Rewrite delta specs for `units-and-components`, `connection`, `observability`, and `session` to normative monolithic dynamic-column contracts aligned with approved expanded actuation scope.
- [x] 0.5 Run a consistency pass: proposal/design/tasks/spec deltas must agree on monolithic scope, reflux/product/utility actuation seams, fixed-latent-heat `Q/λ` duty surrogate, liquid-phase holdup bounds, non-actuating ratio semantics, pressure/geometry contracts, observability, unchanged gameplay gating, and deferred controller proof.

## Wave 1 — TDD red tests for dynamic-column behavior and boundaries

- [x] 1.1 Add red unit-process tests for multicomponent stagewise transients and component conservation on monolithic `StagewiseDistillationColumn`.
  - Likely files:
    - `tests/unit_process/test_layer4_stagewise_distillation.py`
- [x] 1.2 Add red tests for multi-feed behavior and feed-stage assignment/feed-height semantics.
  - Likely files:
    - `tests/unit_process/test_layer4_stagewise_distillation.py`
    - `tests/unit_process/test_stream_port_io.py`
- [x] 1.3 Add red tests for geometry semantics and pressure contract.
  - `active_contact_height_m` drives tray-equivalent stage count under fixed spacing.
  - `shell_diameter_m` affects area/holdup/capacity through an area-scaled proxy heuristic, not direct thermodynamic selectivity.
  - minimum contract: shared dynamic `column_pressure_pa` for stages/ports, while allowing future stagewise pressure implementation.
  - Likely files:
    - `tests/unit_process/test_layer4_stagewise_distillation.py`
- [x] 1.4 Add red tests for unit-local boundary-request seams plus explicit external material-routing seams.
   - reflux liquid outlet + reflux-return inlet are explicit unit-local boundary seams.
   - distillate and bottoms are external withdrawals from reflux-drum/bottoms-sump holdups.
   - condenser and reboiler use unit-local duty-request boundary fields on `StagewiseDistillationColumn`, not controller-bound utility-service namespaces.
   - reflux-return and product-withdrawal seams stay liquid-phase, holdup-bounded, and cannot bypass owning holdup states or go negative.
   - `actuator/valve/<id>`, `actuator/pump/<id>`, and `actuator/heat/<id>` remain repo-native general platform namespaces for line-owned actuation, but distillation-specific binding proof remains deferred.
  - Assert `reflux_ratio`/`boilup_ratio` are not required as runtime actuation knobs, and controller binding proof for distillation remains deferred.
  - Likely files:
    - `tests/unit_process/test_control_surface_contract.py`
    - `tests/connection/test_connected_plant_orchestrator.py`
    - `tests/integration/test_dynamic_process_network_workflow.py`
- [x] 1.5 Add red runtime observability tests for dynamic-column process-state keys.
  - selected stage compositions
  - product compositions for all active species
  - reflux-drum and bottoms-sump holdups
  - actual flows including reflux-return and external withdrawal related readouts
  - each feed’s actual flow/composition and assigned stage
  - dynamic pressure
  - geometry values if public/runtime
  - utility-side and duty-service readouts if present
  - derived/reference-only `reflux_ratio` and `boilup_ratio` readouts if exposed.
  - Likely files:
    - `tests/connection/test_network_api.py`
    - `tests/cli/test_backend_session.py`
- [x] 1.6 Add red regression tests keeping gameplay gating unchanged while enforcing stagewise-only/no-shim distillation semantics.
  - current starts/build lists remain unchanged
  - `place_shortcut_distillation_column` remains hide/reject gated
  - `_install_unit()` invalid-config translation boundary remains unchanged and is still proven by regression coverage
  - dynamic closure remains stagewise-only with no `ShortcutDistillation` class/alias/shim path.
  - Likely files:
    - `tests/gameplay/test_sandbox_catalog.py`
    - `tests/gameplay/test_start_catalog.py`
    - `tests/gameplay/test_sandbox_session.py`
    - `tests/gameplay/test_realtime_game_service.py`

## Wave 2 — Implement dynamic column on recommended path

- [x] 2.1 Keep one monolithic ProcessModel-based `StagewiseDistillationColumn` as the only runtime distillation model (do not split into separately placeable condenser/reboiler/tower units).
  - Likely files:
    - `src/modular_simulation/unit_processes/separation/` (new dynamic column module)
    - related unit registration/wiring files where required.
- [x] 2.2 Implement multicomponent stage-by-stage RHS with named stagewise VLE closure.
  - If constant-relative-volatility-first is used, freeze a multicomponent alpha-vector/LK-referenced set.
  - Keep non-keys present across inventories/feeds/products.
- [x] 2.3 Implement multi-feed stage assignment and two-product dynamic column structures.
   - duty-limited condenser surrogate + reflux drum
   - partial-equilibrium kettle reboiler + bottoms sump.
- [x] 2.4 Implement geometry and pressure contracts per spec.
  - `active_contact_height_m` -> tray-equivalent stage count
  - `shell_diameter_m` -> area/holdup/capacity effects
  - dynamic pressure minimum contract via shared `column_pressure_pa` (or stronger stagewise dynamic pressure treatment).
- [x] 2.5 Wire unit-local boundary-request seams and preserve line-owned actuator namespace conventions.
- [x] 2.6 Implement explicit monolithic actuation topology.
   - expose reflux liquid outlet + reflux-return inlet as unit-local boundary seams
   - implement distillate/bottoms as external withdrawals from reflux-drum/bottoms-sump holdups
   - couple condenser/reboiler requests through unit-local duty-request boundary fields under the constant-molar-overflow slice
   - keep withdrawals and reflux-return liquid-phase, inventory-bounded, and unable to bypass owning holdup states
   - keep repo-native actuator namespaces honest for material lines while leaving distillation controller binding deferred.
- [x] 2.7 Keep runtime behavior stagewise-only with no `ShortcutDistillation` compatibility shim.
  - Do not treat Fenske/Underwood/Gilliland/Hengstebeck-Geddes as the live dynamic RHS closure.
- [x] 2.8 Enforce ratio-field semantics.
  - `reflux_ratio` and `boilup_ratio` remain initialization/reference/derived-observable only
  - if exposed, ratio values are derived from actual runtime flows
  - no live runtime actuation path uses ratio knobs.

## Wave 3 — Runtime proof via normal composition and observability

- [x] 3.1 Prove dynamic-column runtime behavior through existing subsystem/network composition (no controller-state hacks).
  - include runtime proof that direct-duty services alter internal condensation/boilup through fixed-latent-heat `Q/λ` mapping while preserving component conservation.
  - include runtime proof that reflux-return/product-withdrawal seams remain liquid-phase, holdup-bounded, and cannot drive negative owner inventories.
  - Likely files/tests:
    - `tests/integration/test_dynamic_process_network_workflow.py`
    - `tests/connection/test_connected_plant_orchestrator.py`
- [x] 3.2 Prove observability payload numerically matches runtime-owned state under `observables.process_state_values`.
  - include runtime proof for reflux-return/product-withdrawal/utility-duty seam state readouts where exposed.
  - Likely files/tests:
    - `tests/connection/test_network_api.py`
    - `tests/cli/test_backend_session.py`
- [x] 3.3 Prove unchanged topology-only gameplay surface and rejection behavior still hold.
  - include explicit assertion that controller proof remains deferred to `ModularSimulator-9tr.6` despite expanded actuation seams.
  - Likely files/tests:
    - `tests/gameplay/test_sandbox_catalog.py`
    - `tests/gameplay/test_start_catalog.py`
    - `tests/gameplay/test_sandbox_session.py`
    - `tests/gameplay/test_realtime_game_service.py`

## Wave 4 — Verification, independent review, and spec sync/closure

- [x] 4.1 Run verification commands (full matrix):
  - `uv run pytest tests/unit_process/test_layer4_stagewise_distillation.py`
  - `uv run pytest tests/unit_process/test_layer4_distillation.py`
  - `uv run pytest tests/unit_process/test_stream_port_io.py`
  - `uv run pytest tests/unit_process/test_control_surface_contract.py`
  - `uv run pytest tests/unit_process/test_unit_wrapping.py`
  - `uv run pytest tests/connection/test_connected_plant_orchestrator.py`
  - `uv run pytest tests/connection/test_network_api.py`
  - `uv run pytest tests/cli/test_backend_session.py`
  - `uv run pytest tests/integration/test_dynamic_process_network_workflow.py`
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py tests/gameplay/test_start_catalog.py tests/gameplay/test_sandbox_session.py tests/gameplay/test_realtime_game_service.py`
- [x] 4.2 Require independent parallel review by `hybrid-code-reviewer` and `simulation-advisor` before closure.
- [x] 4.3 Verify OpenSpec change consistency and sync approved deltas into `openspec/specs/*` only when implementation state warrants.
- [x] 4.4 Confirm deferred work stays deferred (`ModularSimulator-9tr.6` controller proof) and close this change with evidence.
