## Context

- `docs/game_backend_overview.md` and `openspec/specs/educational-backend-positioning/spec.md` position the repo as a simulation-first educational backend and keep `PlantBackendSession` as substrate rather than gameplay-policy owner.
- `openspec/specs/flowsheet-junction-line-api/spec.md` freezes the canonical topology model as explicit junctions, sinks, and line-owned `PumpInstall` / `ValveInstall` / `HeatInstall` overlays.
- `src/modular_simulation/flowsheet/flowsheet.py` already exposes grounded high-level constructs for `add_junction(...)`, `add_sink(...)`, `connect(..., pump=..., valve=..., heat=...)`, and the supported live unit families.
- `src/modular_simulation/cli/backend_session.py` already exposes `connect_line`, `configure_line`, `attach_valve`, sensor wiring, and controller wiring, but does not yet expose generic `add_junction`, `attach_line_pump`, or `attach_line_heat_actuator` helpers on `TxHandle`.
- The user clarified that there must be **one sandbox**; the prior “three sandbox templates” framing was rejected. Tutorial content is acceptable only as guided starts with explicit goals.

## Goals / Non-Goals

**Goals**
- Freeze the one phase-1 sandbox start state and exact build catalog.
- Freeze tutorial starter states and explicit goal contracts separately from the sandbox.
- Call out the exact thin generic backend-session helpers needed to apply the frozen catalog.

**Non-Goals**
- Implement economics, pricing, buying, selling, or score-like systems; those belong to `define-sandbox-session-and-heuristic-economics`.
- Promise arbitrary process-model factories, stand-alone pump/valve unit families, or open-ended chemistry authoring.
- Treat tutorials as extra sandbox variants.

## Decisions

1. **Phase 1 contains one true sandbox and separate tutorial starts.**
   - The sandbox is the free-play surface.
   - Tutorial starts are guided challenge starts with explicit goals and elapsed-time completion, not alternate sandbox identities.

2. **Start states use one typed contract.**
   - `PlayStartDefinition` fields:
     - `start_id: str`
     - `start_kind: Literal["sandbox", "tutorial_start"]`
     - `title: str`
     - `seed_source_paths: tuple[str, ...]`
     - `starting_topology_summary: str`
     - `published_signal_ids: tuple[str, ...]`
     - `allowed_item_ids: tuple[str, ...]`

3. **The exact phase-1 start-state records are frozen in this pack.**
   - `phase1_process_sandbox_v1`
     - `start_kind = "sandbox"`
     - `title = "Phase-1 process sandbox"`
     - `seed_source_paths = ("examples/unit_process_flowsheet/easy_2_heater_flash.py", "examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py")`
     - `starting_topology_summary = "Two named feeds and two named sinks with no units, junctions, or line overlays preinstalled."`
     - `published_signal_ids = ("feed_a_draw_mol_s", "feed_b_draw_mol_s", "product_a_flow_mol_s", "product_b_flow_mol_s", "heating_steam_duty_W", "total_normalized_pump_load")`
     - `allowed_item_ids = ("place_heater_cooler", "place_flash_drum", "place_heat_exchanger", "place_component_separator", "place_merge_junction_2x1", "place_split_junction_1x2", "build_process_line", "install_line_pump", "install_line_valve", "install_line_heat_actuator", "install_sampled_delayed_sensor", "install_pid_controller")`
   - `heater_flash_tutorial_start_v1`
     - `start_kind = "tutorial_start"`
     - `title = "Heater/flash tutorial start"`
     - `seed_source_paths = ("examples/unit_process_flowsheet/easy_2_heater_flash.py",)`
     - `starting_topology_summary = "One named feed and two named product sinks with no heater, flash drum, or connecting lines preinstalled."`
     - `published_signal_ids = ("feed_draw_mol_s", "vapor_product_flow_mol_s", "liquid_product_flow_mol_s", "heating_steam_duty_W")`
     - `allowed_item_ids = ("place_heater_cooler", "place_flash_drum", "build_process_line")`
   - `reactor_control_tutorial_start_v1`
     - `start_kind = "tutorial_start"`
     - `title = "Reactor control tutorial start"`
     - `seed_source_paths = ("examples/van_de_vusse_cstr/process_definition.py", "examples/van_de_vusse_cstr/component_definition.py", "examples/van_de_vusse_cstr/run_simulation.py")`
     - `starting_topology_summary = "Van de Vusse reactor scaffold is preloaded, but reference sensors and controllers are intentionally absent for learner-installed instrumentation."`
     - `published_signal_ids = ("reactor_temperature_K", "product_b_concentration_mol_l", "cooling_water_duty_W")`
     - `allowed_item_ids = ("install_sampled_delayed_sensor", "install_pid_controller")`
   - `recycle_purge_tutorial_start_v1`
     - `start_kind = "tutorial_start"`
     - `title = "Recycle/purge tutorial start"`
     - `seed_source_paths = ("examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py",)`
     - `starting_topology_summary = "Recycle scaffold includes named recycle and purge lines, but leaves purge throttling and recycle pumping to the learner."`
     - `published_signal_ids = ("fresh_feed_draw_mol_s", "liquid_product_flow_mol_s", "purge_loss_flow_mol_s", "total_normalized_pump_load")`
     - `allowed_item_ids = ("install_line_valve", "install_line_pump")`

4. **The sandbox catalog uses one typed item contract.**
   - `SandboxCatalogItemDefinition` fields:
     - `item_id: str`
     - `title: str`
     - `item_kind: Literal["unit_blueprint", "junction_blueprint", "line", "line_overlay", "sensor", "controller"]`
     - `apply_kind: Literal["add_process", "add_junction", "connect_configure_line", "attach_line_pump", "attach_line_valve", "attach_line_heat_actuator", "create_bind_sensor", "create_bind_activate_controller"]`
     - `default_config: Mapping[str, object]`
     - `required_user_inputs: tuple[str, ...]`
     - `supported_start_ids: tuple[str, ...]`
     - `educational_summary: str`

5. **The exact phase-1 catalog item ids are frozen.**
   - `place_heater_cooler`
   - `place_flash_drum`
   - `place_heat_exchanger`
   - `place_component_separator`
   - `place_merge_junction_2x1`
   - `place_split_junction_1x2`
   - `build_process_line`
   - `install_line_pump`
   - `install_line_valve`
   - `install_line_heat_actuator`
   - `install_sampled_delayed_sensor`
   - `install_pid_controller`

6. **The exact catalog records are frozen in this pack.**

### `place_heater_cooler`
- `title = "Heater/cooler unit"`
- `item_kind = "unit_blueprint"`
- `apply_kind = "add_process"`
- `default_config = {"unit_type": "HeaterCooler", "unit_module": "modular_simulation.unit_processes.thermal.heater_cooler", "constructor_payload": {"mode": "temperature", "external_outlet_temperature": 325.0, "pressure_drop": 0.0}}`
- `required_user_inputs = ("process_id",)`
- `supported_start_ids = ("phase1_process_sandbox_v1", "heater_flash_tutorial_start_v1")`
- `educational_summary = "single-inlet single-outlet heater/cooler with explicit outlet-temperature boundary"`

### `place_flash_drum`
- `title = "Flash drum unit"`
- `item_kind = "unit_blueprint"`
- `apply_kind = "add_process"`
- `default_config = {"unit_type": "FlashDrum", "unit_module": "modular_simulation.unit_processes.separation.flash_drum", "constructor_payload": {"thermal_mode": "isothermal", "imposed_pressure": 101325.0, "imposed_temperature": 320.0}}`
- `required_user_inputs = ("process_id",)`
- `supported_start_ids = ("phase1_process_sandbox_v1", "heater_flash_tutorial_start_v1")`
- `educational_summary = "two-product flash separator with explicit imposed pressure and temperature boundaries"`

### `place_heat_exchanger`
- `title = "Heat exchanger unit"`
- `item_kind = "unit_blueprint"`
- `apply_kind = "add_process"`
- `default_config = {"unit_type": "HeatExchanger", "unit_module": "modular_simulation.unit_processes.thermal.heat_exchanger", "constructor_payload": {"flow_arrangement": "counter", "ua": 7500.0}}`
- `required_user_inputs = ("process_id",)`
- `supported_start_ids = ("phase1_process_sandbox_v1",)`
- `educational_summary = "counter-current dual-stream heat exchanger with explicit UA parameter"`

### `place_component_separator`
- `title = "Component separator unit"`
- `item_kind = "unit_blueprint"`
- `apply_kind = "add_process"`
- `default_config = {"unit_type": "ComponentSeparator", "unit_module": "modular_simulation.unit_processes.separation.component_separator", "constructor_payload": {"configured_split_fraction_targets": {"mode": "equal_split"}}}`
- `required_user_inputs = ("process_id",)`
- `supported_start_ids = ("phase1_process_sandbox_v1",)`
- `educational_summary = "abstract split-fraction separator for material-balance and recovery tradeoff teaching"`

### `place_merge_junction_2x1`
- `title = "Merge junction (2x1)"`
- `item_kind = "junction_blueprint"`
- `apply_kind = "add_junction"`
- `default_config = {"inlet_ports": ("feed_a", "feed_b"), "outlet_ports": ("out",)}`
- `required_user_inputs = ("junction_id",)`
- `supported_start_ids = ("phase1_process_sandbox_v1",)`
- `educational_summary = "explicit two-inlet merge junction using the canonical junction topology model"`

### `place_split_junction_1x2`
- `title = "Split junction (1x2)"`
- `item_kind = "junction_blueprint"`
- `apply_kind = "add_junction"`
- `default_config = {"inlet_ports": ("in",), "outlet_ports": ("product", "recycle")}`
- `required_user_inputs = ("junction_id",)`
- `supported_start_ids = ("phase1_process_sandbox_v1",)`
- `educational_summary = "explicit one-inlet split junction with named product and recycle branches"`

### `build_process_line`
- `title = "Process line"`
- `item_kind = "line"`
- `apply_kind = "connect_configure_line"`
- `default_config = {"radius_m": 0.05, "length_m": 1.0}`
- `required_user_inputs = ("source", "target")`
- `supported_start_ids = ("phase1_process_sandbox_v1", "heater_flash_tutorial_start_v1")`
- `educational_summary = "explicit process line with geometry-owned pressure-loss implications"`

### `install_line_pump`
- `title = "Line pump overlay"`
- `item_kind = "line_overlay"`
- `apply_kind = "attach_line_pump"`
- `default_config = {"initial_pump_speed": 80000.0}`
- `required_user_inputs = ("line_id", "pump_id")`
- `supported_start_ids = ("phase1_process_sandbox_v1", "recycle_purge_tutorial_start_v1")`
- `educational_summary = "line-owned hydraulic boost overlay, not a stand-alone unit family"`

### `install_line_valve`
- `title = "Line valve overlay"`
- `item_kind = "line_overlay"`
- `apply_kind = "attach_line_valve"`
- `default_config = {"minimum_open_fraction": 0.0, "maximum_open_fraction": 1.0, "initial_open_fraction": 1.0}`
- `required_user_inputs = ("line_id", "valve_id")`
- `supported_start_ids = ("phase1_process_sandbox_v1", "recycle_purge_tutorial_start_v1")`
- `educational_summary = "line-owned throttling valve using the existing runtime/control surface"`

### `install_line_heat_actuator`
- `title = "Line heat-actuator overlay"`
- `item_kind = "line_overlay"`
- `apply_kind = "attach_line_heat_actuator"`
- `default_config = {"initial_heat_rate": 0.0}`
- `required_user_inputs = ("line_id", "heat_actuator_id")`
- `supported_start_ids = ("phase1_process_sandbox_v1",)`
- `educational_summary = "line-owned heat actuator overlay using the explicit heat-actuator substrate"`

### `install_sampled_delayed_sensor`
- `title = "Sampled delayed sensor"`
- `item_kind = "sensor"`
- `apply_kind = "create_bind_sensor"`
- `default_config = {"sensor_type": "SampledDelayedSensor", "sensor_module": "modular_simulation.components.sensors.sampled_delayed_sensor", "sensor_config": {"sampling_period": 0.2, "deadtime": 0.0}}`
- `required_user_inputs = ("sensor_id", "signal_key")`
- `supported_start_ids = ("phase1_process_sandbox_v1", "reactor_control_tutorial_start_v1")`
- `educational_summary = "sampled and delayed measurement point for instrumentation tutorials and controller feedback"`

### `install_pid_controller`
- `title = "PID controller"`
- `item_kind = "controller"`
- `apply_kind = "create_bind_activate_controller"`
- `default_config = {"controller_type": "PIDController", "controller_module": "modular_simulation.components.control_system.controllers", "controller_config": {"Kp": 1.0, "Ti": 5.0, "Td": 0.0}}`
- `required_user_inputs = ("controller_id", "signal_key", "actuator_tag")`
- `supported_start_ids = ("phase1_process_sandbox_v1", "reactor_control_tutorial_start_v1")`
- `educational_summary = "standard PID controller bound through the existing runtime wiring APIs"`

7. **Tutorials use typed goal contracts.**
   - `TutorialDefinition` fields:
     - `tutorial_id: str`
     - `title: str`
     - `teaching_track: Literal["topology_separation", "reactor_control", "recycle_process_design"]`
     - `start_id: str`
     - `goal_mode: Literal["sequential", "mixed"]`
     - `goals: tuple[TutorialGoalDefinition, ...]`
     - `guidance_steps: tuple[GuidanceStepDefinition, ...]`
   - `TutorialGoalDefinition` fields:
     - `goal_id: str`
     - `title: str`
     - `goal_kind: Literal["install_item_count"]`
     - `item_id: str`
     - `required_count: int`
     - `prerequisite_goal_ids: tuple[str, ...]`
   - `GuidanceStepDefinition` fields:
     - `step_id: str`
     - `title: str`
     - `related_goal_ids: tuple[str, ...]`
     - `hint_text: str`

8. **The exact tutorial records are frozen in this pack.**
   - `heater_flash_guided_build_v1`
     - `title = "Heater/flash guided build"`
     - `teaching_track = "topology_separation"`
     - `start_id = "heater_flash_tutorial_start_v1"`
     - `goal_mode = "sequential"`
     - goals:
       - `goal_place_heater`: title `Place heater/cooler`, install `place_heater_cooler` count `1`, prerequisites `()`
       - `goal_place_flash`: title `Place flash drum`, install `place_flash_drum` count `1`, prerequisites `("goal_place_heater",)`
       - `goal_wire_flowsheet`: title `Wire the flowsheet`, install `build_process_line` count `4`, prerequisites `("goal_place_flash",)`
      - guidance steps:
        - `step_place_heater`: title `Place the heater`, related goals `("goal_place_heater",)`, hint `Warm the incoming stream before attempting any vapor/liquid split.`
        - `step_place_flash`: title `Place the flash drum`, related goals `("goal_place_flash",)`, hint `Add one flash drum to create explicit vapor and liquid product branches.`
        - `step_wire_flowsheet`: title `Wire the flowsheet`, related goals `("goal_wire_flowsheet",)`, hint `Connect feed to heater, heater to flash, and both flash products to sinks.`
   - `reactor_control_fixup_v1`
     - `title = "Reactor control fix-up"`
     - `teaching_track = "reactor_control"`
     - `start_id = "reactor_control_tutorial_start_v1"`
     - `goal_mode = "mixed"`
     - goals:
        - `goal_add_temperature_sensor`: title `Add temperature sensor`, install `install_sampled_delayed_sensor` count `1`, prerequisites `()`
        - `goal_add_quality_sensor`: title `Add quality sensor`, install `install_sampled_delayed_sensor` count `1`, prerequisites `()`
        - `goal_add_pid`: title `Add PID controller`, install `install_pid_controller` count `1`, prerequisites `("goal_add_temperature_sensor", "goal_add_quality_sensor")`
      - guidance steps:
        - `step_instrument_temperature`: title `Instrument temperature`, related goals `("goal_add_temperature_sensor",)`, hint `Instrument reactor temperature before attempting any automatic jacket manipulation.`
        - `step_instrument_quality`: title `Instrument quality`, related goals `("goal_add_quality_sensor",)`, hint `Add a product-quality measurement so tuning discussions connect to selectivity.`
        - `step_close_loop`: title `Close the loop`, related goals `("goal_add_pid",)`, hint `Bind one PID controller to the available actuator tag after both measurements exist.`
   - `recycle_purge_tradeoff_v1`
     - `title = "Recycle/purge tradeoff"`
     - `teaching_track = "recycle_process_design"`
     - `start_id = "recycle_purge_tutorial_start_v1"`
     - `goal_mode = "sequential"`
     - goals:
        - `goal_add_purge_valve`: title `Add purge valve`, install `install_line_valve` count `1`, prerequisites `()`
        - `goal_add_recycle_pump`: title `Add recycle pump`, install `install_line_pump` count `1`, prerequisites `("goal_add_purge_valve",)`
      - guidance steps:
        - `step_throttle_purge`: title `Throttle purge`, related goals `("goal_add_purge_valve",)`, hint `Install a purge-line valve so purge becomes an explicit operating decision.`
        - `step_restore_recycle_drive`: title `Restore recycle drive`, related goals `("goal_add_recycle_pump",)`, hint `Install recycle pumping explicitly rather than relying on hidden hydraulic gain.`

9. **Only exact generic backend-session helpers required by the catalog are in scope here.**
   - This pack owns planning for generic `TxHandle` helpers surfaced through `PlantBackendSession.begin_tx()` for:
     - `TxHandle.add_junction(...)`
     - `TxHandle.attach_line_pump(...)`
     - `TxHandle.attach_line_heat_actuator(...)`
   - These helpers participate in the existing transaction lifecycle exactly like the current typed helpers: they enqueue pending mutations, appear in `preview()`, and apply through `commit()`.
   - No additional top-level `PlantBackendSession` convenience methods are required by this pack.

10. **Phase-1 sandbox boundaries stay intentionally narrow.**
   - Deferred from this pack:
     - arbitrary process-model factories or generic blueprint loading by arbitrary module/type id
     - stand-alone pump or valve unit-process families
     - freeform feed chemistry authoring beyond the frozen sandbox/tutorial starts
     - general purchasable CSTR/PFR/Van-de-Vusse placement

## Risks / Trade-offs

- **Tutorial starts could be mistaken for extra sandboxes.**
  - Mitigation: freeze `start_kind` and keep exactly one `sandbox` start.
- **Implementers may assume helper methods already exist because lower runtime layers support them.**
  - Mitigation: make the missing `TxHandle` helper surface explicit in the pack and its tasks.
- **Tutorial goals could drift into vague learning objectives.**
  - Mitigation: freeze exact goal kinds, item ids, counts, and prerequisite chains.

## Verification Strategy

- TDD should lead the sandbox catalog, start catalog, tutorial goal catalog, and generic backend-session helper surface.
- Required verification for implementation:
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py`
  - `uv run pytest tests/gameplay/test_sandbox_catalog.py`
  - `uv run pytest tests/gameplay/test_start_catalog.py`
  - `uv run pytest tests/gameplay/test_tutorial_catalog.py`
  - `uv run pytest tests/gameplay/test_sandbox_starts.py`
  - `uv run pytest tests/cli/test_backend_session.py -k "junction or line_pump or heat_actuator"`
  - `uv run pytest tests/integration/test_sandbox_start_smoke.py`
  - `uv run pytest tests/integration/test_examples_smoke.py -k "heater_flash or dual_feed or ammonia_recycle or van_de_vusse"`
- Expected evidence:
  - exactly one start state is marked `sandbox`,
  - tutorial starts and tutorial goals are distinct from the sandbox definition,
  - the catalog exposes exactly the frozen item ids and supported start ids,
  - backend-session helper coverage proves the generic facade surface exists for the missing build primitives,
  - start builders preserve the referenced seed examples.
