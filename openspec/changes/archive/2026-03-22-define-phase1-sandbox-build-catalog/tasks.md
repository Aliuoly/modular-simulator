## Wave 1 — Freeze one sandbox, tutorial goals, and helper boundary with red tests first

- [x] 1.1 Add red tests in `tests/gameplay/test_sandbox_contracts.py` covering these exact contract shapes before implementation:
  - `PlayStartDefinition` exposes `start_id`, `start_kind`, `title`, `seed_source_paths`, `starting_topology_summary`, `published_signal_ids`, and `allowed_item_ids`,
  - `SandboxCatalogItemDefinition` exposes `item_id`, `title`, `item_kind`, `apply_kind`, `default_config`, `required_user_inputs`, `supported_start_ids`, and `educational_summary`,
  - `TutorialDefinition` exposes `tutorial_id`, `title`, `teaching_track`, `start_id`, `goal_mode`, `goals`, and `guidance_steps`,
  - `TutorialGoalDefinition` exposes `goal_id`, `title`, `goal_kind`, `item_id`, `required_count`, and `prerequisite_goal_ids`,
  - `GuidanceStepDefinition` exposes `step_id`, `title`, `related_goal_ids`, and `hint_text`.
- [x] 1.2 Add red tests in `tests/gameplay/test_start_catalog.py` covering these exact boundaries before implementation:
  - the start catalog contains exactly `phase1_process_sandbox_v1`, `heater_flash_tutorial_start_v1`, `reactor_control_tutorial_start_v1`, and `recycle_purge_tutorial_start_v1`,
  - `phase1_process_sandbox_v1` uses `start_kind = "sandbox"` and each remaining frozen start record uses `start_kind = "tutorial_start"`,
  - each start record matches the exact frozen title, provenance, starting-topology summary, published signal ids, and allowed item ids.
- [x] 1.3 Add red tests in `tests/gameplay/test_sandbox_catalog.py` covering these exact boundaries before implementation:
  - the catalog contains exactly the 12 frozen item ids from `design.md`,
  - each item uses the exact frozen `title`, `item_kind`, `apply_kind`, `default_config`, `required_user_inputs`, `supported_start_ids`, and `educational_summary`,
  - no catalog item introduces stand-alone pump/valve unit families, arbitrary process factories, or tutorial-only mechanics.
- [x] 1.4 Add red tests in `tests/gameplay/test_tutorial_catalog.py` covering these exact boundaries before implementation:
  - the tutorial catalog contains exactly `heater_flash_guided_build_v1`, `reactor_control_fixup_v1`, and `recycle_purge_tradeoff_v1`,
  - each tutorial matches the exact frozen `title`, `teaching_track`, `start_id`, `goal_mode`, and goal payloads,
  - each goal matches the exact frozen `title`, `goal_kind`, `item_id`, `required_count`, and prerequisite chain,
  - each guidance step matches the exact frozen `step_id`, `title`, `related_goal_ids`, and `hint_text`.
- [x] 1.5 Extend `tests/cli/test_backend_session.py` with red tests covering these exact generic helper methods before implementation:
  - `session.begin_tx().add_junction(...)`,
  - `session.begin_tx().attach_line_pump(...)`,
  - `session.begin_tx().attach_line_heat_actuator(...)`,
  - each helper queues a mutation, appears in `preview()`, and applies through `commit()` exactly like the existing typed `TxHandle` helpers,
  - no new top-level gameplay-policy convenience methods are introduced on `PlantBackendSession`.
- [x] 1.6 Add red tests in `tests/gameplay/test_sandbox_starts.py` covering start-builder behavior before implementation:
  - each frozen start builder returns the exact start metadata contract for its start id,
  - the sandbox builder and all tutorial-start builders expose the exact frozen published signal ids,
  - no start builder shells out to example scripts or invents unpublished start ids.
- [x] 1.7 Add a red integration smoke in `tests/integration/test_sandbox_start_smoke.py` that will instantiate the sandbox start and each tutorial start once and assert the declared topology/published-signal contract before any builder implementation lands.
- [x] 1.8 Verify the red boundary with:
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py tests/gameplay/test_start_catalog.py tests/gameplay/test_sandbox_catalog.py tests/gameplay/test_tutorial_catalog.py`
  - `uv run pytest tests/gameplay/test_sandbox_starts.py`
  - `uv run pytest tests/cli/test_backend_session.py -k "junction or line_pump or heat_actuator"`
  - `uv run pytest tests/integration/test_sandbox_start_smoke.py`
  - Expected evidence: catalog/start/tutorial/helper tests fail before the implementation exists.

## Wave 2 — Encode the exact sandbox, tutorial starts, and generic helpers

- [x] 2.1 Create `src/modular_simulation/gameplay/contracts.py` with `PlayStartDefinition`, `SandboxCatalogItemDefinition`, `TutorialDefinition`, `TutorialGoalDefinition`, and `GuidanceStepDefinition`.
- [x] 2.2 Create `src/modular_simulation/gameplay/sandbox_catalog.py` with exactly the frozen 12 catalog item records and no additional placeholders.
- [x] 2.3 Create `src/modular_simulation/gameplay/start_catalog.py` with exactly the frozen one-sandbox plus three-tutorial-start records.
- [x] 2.4 Create `src/modular_simulation/gameplay/tutorial_catalog.py` with exactly the frozen tutorial goal and guidance records.
- [x] 2.5 Create reusable builders under `src/modular_simulation/gameplay/starts/` for the four frozen start states using these exact seed assets:
  - `examples/unit_process_flowsheet/easy_2_heater_flash.py`
  - `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py`
  - `examples/van_de_vusse_cstr/process_definition.py`
  - `examples/van_de_vusse_cstr/component_definition.py`
  - `examples/van_de_vusse_cstr/run_simulation.py`
  - `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py`
- [x] 2.6 Extend `src/modular_simulation/cli/backend_session.py` with only the frozen generic `TxHandle` helper surface required by the catalog:
  - `add_junction(...)`,
  - `attach_line_pump(...)`,
  - `attach_line_heat_actuator(...)`.
- [x] 2.7 Keep the helper work generic: do not add pricing, inventory, tutorial timing, or economics logic to `src/modular_simulation/cli/backend_session.py`.

## Wave 3 — Make the red builder/start checks pass and verify provenance

- [x] 3.1 Make `tests/gameplay/test_sandbox_starts.py` pass for the exact sandbox/tutorial start builders introduced in Wave 2.
- [x] 3.2 Make `tests/integration/test_sandbox_start_smoke.py` pass so the sandbox start and each tutorial start instantiate once and surface their declared topology/published-signal contract.
- [x] 3.3 Extend or preserve `tests/integration/test_examples_smoke.py` coverage for:
  - `easy_2_heater_flash.py`
  - `easy_3_dual_feed_heat_exchanger.py`
  - `complex_6_ammonia_recycle_loop.py`
  - `van_de_vusse_cstr/run_simulation.py`
- [x] 3.4 Run the targeted matrix:
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py`
  - `uv run pytest tests/gameplay/test_start_catalog.py`
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py`
  - `uv run pytest tests/gameplay/test_tutorial_catalog.py`
  - `uv run pytest tests/gameplay/test_sandbox_starts.py`
  - `uv run pytest tests/cli/test_backend_session.py -k "junction or line_pump or heat_actuator"`
  - `uv run pytest tests/integration/test_sandbox_start_smoke.py`
  - `uv run pytest tests/integration/test_examples_smoke.py -k "heater_flash or dual_feed or ammonia_recycle or van_de_vusse"`
  - Expected evidence: the exact sandbox/tutorial starts and facade helpers are importable, generic, and still grounded in runnable seed assets.

## Wave 4 — Sync docs to one-sandbox terminology

- [x] 4.1 Update `docs/game_backend_overview.md` so follow-on wording names one sandbox plus tutorial challenges rather than multiple sandbox templates.
- [x] 4.2 Update `docs/plant_backend_session_user_guide.md` only as needed to mention the new generic helper surface without moving gameplay policy into that guide.
- [x] 4.3 Re-run `uv run pytest tests/test_game_backend_positioning.py` after doc updates to keep repo identity and substrate ownership aligned.
