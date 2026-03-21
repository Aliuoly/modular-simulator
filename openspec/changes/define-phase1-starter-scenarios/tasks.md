## Wave 1 — Freeze the starter-scenario contract with red tests first

- [ ] 1.1 Add red tests in `tests/gameplay/test_contracts.py` covering these exact contract shapes before implementation:
  - `ScenarioDefinition` exposes `scenario_id`, `title`, `teaching_track`, `learning_objectives`, `template_id`, `seed_source_paths`, `initial_cash`, `available_upgrade_ids`, `success_metrics`, `economics_fields`, and `victory_conditions`,
  - `UpgradeDefinition` exposes `upgrade_id`, `scenario_id`, `title`, `category`, `base_cost`, `prerequisite_upgrade_ids`, and `plant_changes`,
  - `PlantChangeDefinition` exposes `change_id`, `change_kind`, `target_path`, and `summary`,
  - `SuccessMetricDefinition` exposes `metric_id`, `title`, `source_kind`, `source_key`, and `unit`,
  - `EconomicsMetricTerm` exposes `metric_id` and `coefficient`,
  - `EconomicsFieldDefinition` exposes `economics_field`, `base_amount`, and `metric_terms`,
  - `VictoryCondition` exposes `condition_id`, `metric_id`, `comparison`, `target_value`, and `hold_duration_s`.
- [ ] 1.2 Add red tests in `tests/gameplay/test_scenario_catalog.py` covering these exact boundaries before implementation:
  - the catalog contains exactly `heater_flash_intro`, `reactor_control_intro`, and `recycle_purge_intro`,
  - each scenario uses the contract types from `tests/gameplay/test_contracts.py`,
  - each scenario’s `available_upgrade_ids` resolve to concrete `UpgradeDefinition` entries with fixed `base_cost` and explicit `plant_changes`,
  - each scenario defines exactly one `revenue` economics field and one `utility_cost` economics field using only declared non-economics metrics,
  - each scenario’s `victory_conditions` reference declared `success_metrics` by `metric_id`,
  - no scenario introduces staffing, fouling, batch-first gameplay, vertical integration, or cross-scenario campaign state,
  - every allowed upgrade category maps to an explicit plant change rather than a hidden multiplier.
- [ ] 1.3 Verify the red boundary with:
  - `uv run pytest tests/gameplay/test_contracts.py tests/gameplay/test_scenario_catalog.py`
  - Expected evidence: the contract and catalog tests fail before the implementation exists.

## Wave 2 — Add template-backed scenario definitions

- [ ] 2.1 Create `src/modular_simulation/gameplay/contracts.py` with these exact scenario-facing contract types: `ScenarioDefinition`, `UpgradeDefinition`, `PlantChangeDefinition`, `SuccessMetricDefinition`, `EconomicsMetricTerm`, `EconomicsFieldDefinition`, and `VictoryCondition`.
- [ ] 2.2 Create `src/modular_simulation/gameplay/scenario_catalog.py` with exactly the three starter scenarios and no extra placeholders.
- [ ] 2.3 Author concrete `UpgradeDefinition` entries in the scenario layer; fixed `base_cost`, prerequisite ids, and explicit `plant_changes` are owned here and must not be deferred to the gameplay-session layer.
- [ ] 2.4 Create reusable builders under `src/modular_simulation/gameplay/templates/` by extracting or wrapping construction logic from these exact seed assets:
  - `examples/unit_process_flowsheet/easy_2_heater_flash.py`
  - `examples/van_de_vusse_cstr/process_definition.py`
  - `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py`
- [ ] 2.5 Keep the starter scenarios local and explicit: each scenario definition must name its own learning objectives, upgrade list, success metrics, and victory conditions rather than inferring them from docstrings alone.
- [ ] 2.6 Author explicit per-scenario `economics_fields` bindings using the shared phase-1 formula shape; do not leave revenue/utility calculation coefficients implicit or hardcoded in the gameplay-session layer.

## Wave 3 — Verify template provenance and seed compatibility

- [ ] 3.1 Add `tests/gameplay/test_templates.py` covering: builder creation succeeds, template provenance is recorded, and scenario builders do not shell out to example scripts.
- [ ] 3.2 Add or extend `tests/integration/test_gameplay_smoke.py` so each starter scenario can be instantiated and stepped once using its typed contract data without hardcoded scenario-specific branching in the test body.
- [ ] 3.3 Run the targeted matrix:
  - `uv run pytest tests/gameplay/test_contracts.py`
  - `uv run pytest tests/gameplay/test_scenario_catalog.py`
  - `uv run pytest tests/gameplay/test_economics.py -k "bindings or formula"`
  - `uv run pytest tests/gameplay/test_templates.py`
  - `uv run pytest tests/integration/test_gameplay_smoke.py -k "scenario"`
  - `uv run pytest tests/integration/test_examples_smoke.py -k "heater_flash or ammonia_recycle"`
  - Expected evidence: all three scenario definitions are importable and template-backed, and source example seeds remain runnable.

## Wave 4 — Sync docs without rewriting the curated example inventory

- [ ] 4.1 Update `docs/game_backend_overview.md` so each starter scenario points to its seed/template source and teaching track.
- [ ] 4.2 Update `docs/examples_catalog.md` only as needed to cross-reference scenario seeds; do not relabel the catalog as the gameplay scenario list.
- [ ] 4.3 Re-run `uv run pytest tests/test_rework_examples_review_alignment.py -k "canonical or catalog"` and keep the existing canonical-example parity intact.
