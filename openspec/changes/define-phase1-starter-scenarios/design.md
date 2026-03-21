## Context

- The current canonical examples are intentionally small and flowsheet-first (`docs/examples_catalog.md`, `openspec/specs/curated-flowsheet-examples/spec.md`).
- Grounded seed assets already exist for two of the desired teaching tracks:
  - `examples/unit_process_flowsheet/easy_2_heater_flash.py` for topology + simple separation.
  - `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` for recycle, purge, and explicit line-installed recycle boost.
- A reactor/control teaching seed exists as a reference example rather than as part of the canonical flowsheet path:
  - `examples/van_de_vusse_cstr/process_definition.py`
  - `examples/van_de_vusse_cstr/run_simulation.py`
  - controller references in `src/modular_simulation/components/control_system/controllers/`
- The repo does not contain a gameplay scenario catalog or reusable scenario-template package yet.

## Goals / Non-Goals

**Goals**
- Freeze the exact phase-1 starter scenario list.
- Make each starter scenario concrete enough to implement without inventing learning goals, upgrade scope, or victory logic.
- Keep scenario construction grounded in reusable builders extracted or wrapped from existing repo assets.

**Non-Goals**
- Implement economics, cash flow, or progression-state APIs; those belong to the gameplay-session pack.
- Expand the scenario catalog beyond the initial three starter scenarios.
- Redefine the curated canonical example inventory; scenario seeds may come from both canonical and reference-only examples.

## Decisions

1. **Phase 1 has exactly three starter scenarios.**
   - `heater_flash_intro`
   - `reactor_control_intro`
   - `recycle_purge_intro`
   - No additional scenario ids are in scope for this pack.

2. **Each starter scenario is template-backed and names its seed source.**
   - `heater_flash_intro` is seeded from `examples/unit_process_flowsheet/easy_2_heater_flash.py`.
   - `reactor_control_intro` is seeded from `examples/van_de_vusse_cstr/process_definition.py` and the controller package in `src/modular_simulation/components/control_system/controllers/`.
   - `recycle_purge_intro` is seeded from `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py`.
   - Implementations may wrap rather than literally copy the source examples, but provenance must remain explicit.

3. **Each scenario must declare a small, explicit, machine-readable metadata contract.**
   - Required `ScenarioDefinition` fields:
     - `scenario_id: str`
     - `title: str`
     - `teaching_track: Literal["topology_separation", "reactor_control", "recycle_process_design"]`
     - `learning_objectives: tuple[str, ...]`
     - `template_id: str`
     - `seed_source_paths: tuple[str, ...]`
     - `initial_cash: float`
     - `available_upgrade_ids: tuple[str, ...]`
     - `success_metrics: tuple[SuccessMetricDefinition, ...]`
     - `economics_fields: tuple[EconomicsFieldDefinition, ...]`
     - `victory_conditions: tuple[VictoryCondition, ...]`
   - The contract must be strong enough that an orchestrator can delegate scenario work without guessing what the scenario is for.

4. **Starter scenarios own concrete upgrade definitions; the gameplay-session layer only consumes them.**
   - `UpgradeDefinition` is authored in the starter-scenario pack and must include:
     - `upgrade_id: str`
     - `scenario_id: str`
     - `title: str`
     - `category: Literal["line_install", "unit_parameter", "instrumentation", "topology_edit"]`
     - `base_cost: float`
     - `prerequisite_upgrade_ids: tuple[str, ...]`
     - `plant_changes: tuple[PlantChangeDefinition, ...]`
   - `PlantChangeDefinition` must include:
     - `change_id: str`
     - `change_kind: Literal["line_install", "unit_parameter", "sensor_install", "controller_install", "topology_edit"]`
     - `target_path: str`
     - `summary: str`
   - Phase 1 uses fixed scenario-authored `base_cost`; dynamic repricing is out of scope.
   - The gameplay-session pack must not invent upgrade ids, prices, prerequisites, or plant changes that are absent from the scenario definition.

5. **Allowed upgrades are limited to explicit plant changes.**
   - Legal phase-1 upgrade categories:
     - line-installed hydraulic or heat equipment
     - unit parameter changes tied to a modeled plant effect
     - sensors and controllers
     - topology changes that remain within the scenario’s declared template boundary
   - Illegal phase-1 upgrade categories:
     - hidden profit multipliers
     - purely abstract purity bonuses
     - staffing/fouling/maintenance systems
     - opening a second plant or vertical-integration chain

6. **Learning outcomes are scenario-specific and intentionally narrow.**
   - `heater_flash_intro` teaches basic topology, explicit feeds/sinks, heater effect, and simple product-quality separation signals.
   - `reactor_control_intro` teaches reactor dynamics, observability limits, sensor/controller installation, and control-law impact on stability or product quality.
   - `recycle_purge_intro` teaches recycle closure, purge tradeoffs, pressure-driven recirculation constraints, and throughput/selectivity tradeoffs.

7. **Success metrics and victory conditions are typed and scenario-authored.**
   - `SuccessMetricDefinition` must include:
     - `metric_id: str`
     - `title: str`
     - `source_kind: Literal["simulation_output", "economics_field", "derived_formula"]`
     - `source_key: str`
     - `unit: str`
   - `VictoryCondition` must include:
     - `condition_id: str`
     - `metric_id: str`
     - `comparison: Literal[">=", "<="]`
     - `target_value: float`
     - `hold_duration_s: float`
   - Victory conditions reference `metric_id` values declared in `success_metrics`; they are not free-form prose.

8. **Scenario-authored economics bindings are typed and use one shared phase-1 formula shape.**
   - `EconomicsMetricTerm` must include:
     - `metric_id: str`
     - `coefficient: float`
   - `EconomicsFieldDefinition` must include:
     - `economics_field: Literal["revenue", "utility_cost"]`
     - `base_amount: float`
     - `metric_terms: tuple[EconomicsMetricTerm, ...]`
   - Each scenario must declare exactly one `EconomicsFieldDefinition` for `revenue` and exactly one for `utility_cost`.
   - Each `EconomicsMetricTerm.metric_id` must reference a declared `SuccessMetricDefinition.metric_id` whose `source_kind` is `simulation_output` or `derived_formula`; economics fields may not depend on other economics fields.
   - The shared phase-1 step formula is:
     - `step_value(economics_field) = max(0.0, base_amount + sum(coefficient * metric_value(metric_id)))`
   - Pack 3 consumes these bindings directly; it does not redefine per-scenario economics formulas.

9. **Victory conditions use measurable plant outcomes, not narrative completion flags alone.**
   - A scenario may include qualitative guidance text, but completion must reduce to measurable outputs such as throughput, composition/purity, stable operating window, or recycle/purge performance thresholds.

10. **Scenario scope stays intentionally small.**
   - Each starter scenario is a local ladder with a bounded upgrade list.
   - Cross-scenario unlock trees and campaign stitching are deferred.

## Risks / Trade-offs

- **The reactor/control seed is not in the canonical flowsheet set.**
  - Mitigation: name that provenance explicitly and treat it as a reference-backed gameplay seed rather than relabeling it as canonical onboarding.
- **Template extraction could break example entry points.**
  - Mitigation: future implementation must keep the source example smoke tests in the verification matrix.
- **Upgrade lists may quietly reintroduce sandbox sprawl.**
  - Mitigation: restrict upgrades to scenario-declared explicit plant changes and freeze the catalog at three scenarios.
- **Pack 3 could diverge from pack 2 by inventing its own pricing or objective logic.**
  - Mitigation: make upgrade definitions, success metrics, and victory conditions scenario-authored here and require the gameplay-session layer to consume them as data.

## Verification Strategy

- TDD should lead the scenario-contract and scenario-catalog surface with red tests under `tests/gameplay/` before catalog or template code is added.
- Required verification for implementation:
  - `uv run pytest tests/gameplay/test_contracts.py`
  - `uv run pytest tests/gameplay/test_scenario_catalog.py`
  - `uv run pytest tests/gameplay/test_economics.py -k "bindings or formula"`
  - `uv run pytest tests/gameplay/test_templates.py`
  - `uv run pytest tests/integration/test_gameplay_smoke.py -k "scenario"`
  - `uv run pytest tests/integration/test_examples_smoke.py -k "heater_flash or ammonia_recycle"`
- Expected evidence:
  - the contract types expose the required fields and typed enums/literals,
  - the catalog contains exactly three starter scenarios,
  - each scenario exposes the required metadata contract,
  - each scenario defines explicit `revenue` and `utility_cost` bindings using the shared phase-1 formula shape,
  - template provenance points back to the declared seed assets,
  - source example seeds still run after template extraction or wrapping.
