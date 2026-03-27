"""Phase-1 sandbox build catalog.

Returns a dict keyed by item_id containing SandboxCatalogItemDefinition records.
"""

from __future__ import annotations

from modular_simulation.gameplay.contracts import SandboxCatalogItemDefinition


def build_sandbox_catalog() -> dict[str, SandboxCatalogItemDefinition]:
    """Return the frozen phase-1 sandbox build catalog."""
    entries = [
        SandboxCatalogItemDefinition(
            item_id="place_heater_cooler",
            title="Heater/cooler unit",
            item_kind="unit_blueprint",
            apply_kind="add_process",
            default_config={
                "unit_type": "HeaterCooler",
                "unit_module": "modular_simulation.unit_processes.thermal.heater_cooler",
                "constructor_payload": {
                    "mode": "temperature",
                    "external_outlet_temperature": 325.0,
                    "pressure_drop": 0.0,
                },
            },
            required_user_inputs=("process_id",),
            supported_start_ids=(
                "phase1_process_sandbox_v1",
                "heater_flash_tutorial_start_v1",
            ),
            educational_summary=(
                "single-inlet single-outlet heater/cooler with explicit outlet-temperature boundary"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="place_flash_drum",
            title="Flash drum unit",
            item_kind="unit_blueprint",
            apply_kind="add_process",
            default_config={
                "unit_type": "FlashDrum",
                "unit_module": "modular_simulation.unit_processes.separation.flash_drum",
                "constructor_payload": {
                    "thermal_mode": "isothermal",
                    "imposed_pressure": 101325.0,
                    "imposed_temperature": 320.0,
                },
            },
            required_user_inputs=("process_id",),
            supported_start_ids=(
                "phase1_process_sandbox_v1",
                "heater_flash_tutorial_start_v1",
            ),
            educational_summary=(
                "two-product flash separator with explicit imposed pressure and temperature boundaries"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="place_heat_exchanger",
            title="Heat exchanger unit",
            item_kind="unit_blueprint",
            apply_kind="add_process",
            default_config={
                "unit_type": "HeatExchanger",
                "unit_module": "modular_simulation.unit_processes.thermal.heat_exchanger",
                "constructor_payload": {
                    "flow_arrangement": "counter",
                    "ua": 7500.0,
                },
            },
            required_user_inputs=("process_id",),
            supported_start_ids=("phase1_process_sandbox_v1",),
            educational_summary=(
                "counter-current dual-stream heat exchanger with explicit UA parameter"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="place_component_separator",
            title="Component separator unit",
            item_kind="unit_blueprint",
            apply_kind="add_process",
            default_config={
                "unit_type": "ComponentSeparator",
                "unit_module": "modular_simulation.unit_processes.separation.component_separator",
                "constructor_payload": {
                    "configured_split_fraction_targets": {"mode": "equal_split"}
                },
            },
            required_user_inputs=("process_id",),
            supported_start_ids=("phase1_process_sandbox_v1",),
            educational_summary=(
                "abstract split-fraction separator for material-balance and recovery tradeoff teaching"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="place_shortcut_distillation_column",
            title="Stagewise distillation column (legacy item id)",
            item_kind="unit_blueprint",
            apply_kind="add_process",
            default_config={
                "unit_type": "StagewiseDistillationColumn",
                "unit_module": "modular_simulation.unit_processes.separation.stagewise_distillation",
                "constructor_payload": {
                    "n_species": 3,
                    "active_contact_height_m": 4.0,
                    "shell_diameter_m": 1.0,
                    "feed_stage_indices": (1,),
                },
            },
            required_user_inputs=("process_id",),
            supported_start_ids=(),
            educational_summary=(
                "legacy catalog id that instantiates the monolithic dynamic stagewise "
                "distillation column with duty-limited condenser/reboiler surrogates and "
                "explicit holdup-bounded reflux/product seams"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="place_merge_junction_2x1",
            title="Merge junction (2x1)",
            item_kind="junction_blueprint",
            apply_kind="add_junction",
            default_config={
                "inlet_ports": ("feed_a", "feed_b"),
                "outlet_ports": ("out",),
            },
            required_user_inputs=("junction_id",),
            supported_start_ids=("phase1_process_sandbox_v1",),
            educational_summary=(
                "explicit two-inlet merge junction using the canonical junction topology model"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="place_split_junction_1x2",
            title="Split junction (1x2)",
            item_kind="junction_blueprint",
            apply_kind="add_junction",
            default_config={
                "inlet_ports": ("in",),
                "outlet_ports": ("product", "recycle"),
            },
            required_user_inputs=("junction_id",),
            supported_start_ids=("phase1_process_sandbox_v1",),
            educational_summary=(
                "explicit one-inlet split junction with named product and recycle branches"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="build_process_line",
            title="Process line",
            item_kind="line",
            apply_kind="connect_configure_line",
            default_config={
                "radius_m": 0.05,
                "length_m": 1.0,
            },
            required_user_inputs=("source", "target"),
            supported_start_ids=(
                "phase1_process_sandbox_v1",
                "heater_flash_tutorial_start_v1",
            ),
            educational_summary=(
                "explicit process line with geometry-owned pressure-loss implications"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="install_line_pump",
            title="Line pump overlay",
            item_kind="line_overlay",
            apply_kind="attach_line_pump",
            default_config={
                "initial_pump_speed": 80000.0,
            },
            required_user_inputs=("line_id", "pump_id"),
            supported_start_ids=(
                "phase1_process_sandbox_v1",
                "recycle_purge_tutorial_start_v1",
            ),
            educational_summary=(
                "line-owned hydraulic boost overlay, not a stand-alone unit family"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="install_line_valve",
            title="Line valve overlay",
            item_kind="line_overlay",
            apply_kind="attach_line_valve",
            default_config={
                "minimum_open_fraction": 0.0,
                "maximum_open_fraction": 1.0,
                "initial_open_fraction": 1.0,
            },
            required_user_inputs=("line_id", "valve_id"),
            supported_start_ids=(
                "phase1_process_sandbox_v1",
                "recycle_purge_tutorial_start_v1",
            ),
            educational_summary=(
                "line-owned throttling valve using the existing runtime/control surface"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="install_line_heat_actuator",
            title="Line heat-actuator overlay",
            item_kind="line_overlay",
            apply_kind="attach_line_heat_actuator",
            default_config={
                "initial_heat_rate": 0.0,
            },
            required_user_inputs=("line_id", "heat_actuator_id"),
            supported_start_ids=("phase1_process_sandbox_v1",),
            educational_summary=(
                "line-owned heat actuator overlay using the explicit heat-actuator substrate"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="install_sampled_delayed_sensor",
            title="Sampled delayed sensor",
            item_kind="sensor",
            apply_kind="create_bind_sensor",
            default_config={
                "sensor_type": "SampledDelayedSensor",
                "sensor_module": "modular_simulation.components.sensors.sampled_delayed_sensor",
                "sensor_config": {
                    "sampling_period": 0.2,
                    "deadtime": 0.0,
                },
            },
            required_user_inputs=("sensor_id", "signal_key"),
            supported_start_ids=(
                "phase1_process_sandbox_v1",
                "reactor_control_tutorial_start_v1",
            ),
            educational_summary=(
                "sampled and delayed measurement point for instrumentation tutorials and controller feedback"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="install_pid_controller",
            title="PID controller",
            item_kind="controller",
            apply_kind="create_bind_activate_controller",
            default_config={
                "controller_type": "PIDController",
                "controller_module": "modular_simulation.components.control_system.controllers",
                "controller_config": {
                    "Kp": 1.0,
                    "Ti": 5.0,
                    "Td": 0.0,
                },
            },
            required_user_inputs=("controller_id", "signal_key", "actuator_tag"),
            supported_start_ids=(
                "phase1_process_sandbox_v1",
                "reactor_control_tutorial_start_v1",
            ),
            educational_summary=(
                "standard PID controller bound through the existing runtime wiring APIs"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="place_holding_tank",
            title="Holding tank",
            item_kind="unit_blueprint",
            apply_kind="add_process",
            default_config={
                "unit_type": "HoldingTank",
                "unit_module": "modular_simulation.unit_processes.storage.holding_tank",
                "constructor_payload": {},
            },
            required_user_inputs=("process_id",),
            supported_start_ids=(),
            educational_summary=(
                "single-inlet single-outlet buffer vessel for future tank-mediated material holdup and transfer"
            ),
        ),
        SandboxCatalogItemDefinition(
            item_id="place_quality_control_lab",
            title="Quality control lab",
            item_kind="unit_blueprint",
            apply_kind="add_process",
            default_config={
                "unit_type": "QualityControlLab",
                "unit_module": "modular_simulation.unit_processes.analysis.quality_control_lab",
                "constructor_payload": {"minimum_purity_mol_fraction": 0.95},
            },
            required_user_inputs=("process_id", "tracked_component_id"),
            supported_start_ids=(),
            educational_summary=(
                "process-stream quality gate that counts accepted moles toward later research progress and rejects off-spec material to disposal"
            ),
        ),
    ]
    return {entry.item_id: entry for entry in entries}
