from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

import numpy as np

from modular_simulation.connection.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.connected_plant_orchestrator import ConnectedPlantOrchestrator
from modular_simulation.connection.hydraulic_solver import HydraulicSolveResult
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.process_binding import ProcessBinding
from modular_simulation.connection.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.state import MaterialState, PortCondition
from modular_simulation.connection.subsystem_descriptor import SubsystemRuntimeDescriptor
from modular_simulation.connection.thermo_coupling import ThermoBoundaryPropagationStep
from modular_simulation.connection.transport import LagTransportState, LagTransportUpdateResult
from modular_simulation.thermodynamics.kinetics import PowerLawRateLaw, Reaction, ReactionSet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import CSTR, FlashDrum, HeaterCooler, ShortcutDistillation


@dataclass(frozen=True)
class _StreamSnapshot:
    flow: float
    temperature: float
    pressure: float
    composition: tuple[float, ...]


def _attach(model: object) -> None:
    attach_system = getattr(model, "attach_system", None)
    if not callable(attach_system):
        raise TypeError("Model must provide attach_system(system).")
    cast(Callable[[object], None], attach_system)(SimpleNamespace(solver_options={}))


def _to_tuple(values: object) -> tuple[float, ...]:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    return tuple(float(item) for item in array)


def _reaction_set() -> ReactionSet:
    return ReactionSet(
        reactions=(
            Reaction(
                name="ethanol_to_water",
                stoichiometry={"ethanol": -1.0, "water": 1.0},
                rate_law=PowerLawRateLaw(
                    k_ref=0.2,
                    orders={"ethanol": 1.0},
                    key_species="r1",
                ),
            ),
        )
    )


def _port_condition(
    *,
    pressure: float,
    temperature: float,
    composition: tuple[float, ...],
    flow: float,
    species_ids: tuple[str, ...],
) -> PortCondition:
    return PortCondition(
        state=MaterialState(
            pressure=pressure,
            temperature=temperature,
            mole_fractions=composition,
            species_ids=species_ids,
            phase="liquid",
        ),
        species_ids=species_ids,
        through_molar_flow_rate=flow,
        macro_step_time_s=0.0,
    )


@dataclass
class _UnitSubsystem:
    descriptor: SubsystemRuntimeDescriptor
    apply_inlet: Callable[[PortCondition], None]
    step_unit: Callable[[float], None]
    snapshot_outlets: Callable[[], Mapping[str, _StreamSnapshot]]
    latest_port_conditions: dict[str, PortCondition]
    fallback_inlet: PortCondition
    fixed_inlet: PortCondition | None = None
    _binding: ProcessBinding | None = None

    def attach_binding(self, binding: ProcessBinding) -> None:
        self._binding = binding
        initial = self.fixed_inlet if self.fixed_inlet is not None else self.fallback_inlet
        inlet_port = self.descriptor.inlet_ports[0]
        binding.set_inlet(inlet_port, float(initial.through_molar_flow_rate))
        outlet_payload = self._outlet_payload()
        binding.bind_outlets(outlet_payload)

    def run_sensor_phase(self) -> None:
        return

    def run_calculation_phase(self) -> None:
        return

    def run_controller_phase(self) -> None:
        return

    def run_process_phase(self, duration: float) -> None:
        inlet = self._resolve_inlet_condition()
        self.fallback_inlet = inlet
        self.apply_inlet(inlet)
        self.step_unit(duration)
        if self._binding is None:
            raise RuntimeError(
                f"Binding not attached for subsystem '{self.descriptor.descriptor_id}'."
            )
        self._binding.bind_outlets(self._outlet_payload())

    def stream_for_port(self, outlet_port: str) -> _StreamSnapshot:
        snapshots = self.snapshot_outlets()
        return snapshots[outlet_port]

    def _resolve_inlet_condition(self) -> PortCondition:
        if self.fixed_inlet is not None:
            return self.fixed_inlet
        inlet_key = f"{self.descriptor.process_id}.{self.descriptor.inlet_ports[0]}"
        return self.latest_port_conditions.get(inlet_key, self.fallback_inlet)

    def _outlet_payload(self) -> dict[str, dict[str, object]]:
        snapshots = self.snapshot_outlets()
        payload: dict[str, dict[str, object]] = {}
        for outlet_port in self.descriptor.outlet_ports:
            stream = snapshots[outlet_port]
            payload[outlet_port] = {
                "role": "outlet",
                "flow": float(stream.flow),
                "composition": stream.composition,
            }
        return payload


def run_flowsheet_demo(
    *,
    macro_steps: int = 80,
    macro_step_time_s: float = 0.1,
    print_results: bool = True,
) -> dict[str, float | tuple[float, ...] | tuple[str, ...]]:
    context = SimulationRuntimeContext.create(species_names=["ethanol", "water"])
    package = context.property_package
    species_ids = context.species_registry.cas_list

    feed_condition = _port_condition(
        pressure=180000.0,
        temperature=320.0,
        composition=(0.65, 0.35),
        flow=4.0,
        species_ids=species_ids,
    )

    heater = HeaterCooler(
        mode="duty",
        n_species=2,
        inlet_flow=4.0,
        inlet_temperature=320.0,
        inlet_pressure=180000.0,
        inlet_composition=np.array([0.65, 0.35], dtype=np.float64),
        pressure_drop=8000.0,
        duty_setpoint=12000.0,
    )
    heater.set_property_package(package)
    _attach(heater)

    cstr = CSTR(
        n_species=2,
        species_names=("ethanol", "water"),
        reaction_set=_reaction_set(),
        species_moles=np.array([20.0, 10.0], dtype=np.float64),
        temperature=335.0,
        volume=30.0,
        inlet_flow=4.0,
        inlet_temperature=335.0,
        inlet_pressure=172000.0,
        inlet_composition=np.array([0.6, 0.4], dtype=np.float64),
        reactor_volume=30.0,
        level_control_gain=3.0,
        volumetric_heat_capacity=4100.0,
        reaction_heat_coeffs=np.array([45000.0, 0.0], dtype=np.float64),
        heat_transfer_coeff=120.0,
        jacket_area=2.0,
        jacket_temperature=330.0,
    )
    _attach(cstr)

    flash = FlashDrum(
        thermal_mode="isothermal",
        n_species=2,
        inlet_flow=3.5,
        inlet_temperature=348.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.45, 0.55], dtype=np.float64),
        flash_pressure=101325.0,
        flash_temperature_setpoint=348.0,
    )
    flash.set_property_package(package)
    _attach(flash)

    column = ShortcutDistillation(
        n_species=2,
        light_key_index=0,
        heavy_key_index=1,
        inlet_flow=2.0,
        inlet_temperature=348.0,
        inlet_pressure=101325.0,
        inlet_composition=np.array([0.62, 0.38], dtype=np.float64),
        light_key_distillate_recovery=0.90,
        heavy_key_bottoms_recovery=0.90,
        reflux_ratio_factor=1.6,
    )
    column.set_property_package(package)
    _attach(column)

    latest_port_conditions: dict[str, PortCondition] = {}

    def _apply_heater_inlet(condition: PortCondition) -> None:
        heater.inlet_flow = float(condition.through_molar_flow_rate)
        heater.inlet_temperature = float(condition.state.temperature)
        heater.inlet_pressure = float(condition.state.pressure)
        heater.inlet_composition = np.asarray(condition.state.mole_fractions, dtype=np.float64)

    def _apply_cstr_inlet(condition: PortCondition) -> None:
        cstr.inlet_flow = float(condition.through_molar_flow_rate)
        cstr.inlet_temperature = float(condition.state.temperature)
        cstr.inlet_pressure = float(condition.state.pressure)
        cstr.inlet_composition = np.asarray(condition.state.mole_fractions, dtype=np.float64)

    def _apply_flash_inlet(condition: PortCondition) -> None:
        flash.inlet_flow = float(condition.through_molar_flow_rate)
        flash.inlet_temperature = float(condition.state.temperature)
        flash.inlet_pressure = float(condition.state.pressure)
        flash.inlet_composition = np.asarray(condition.state.mole_fractions, dtype=np.float64)

    def _apply_column_inlet(condition: PortCondition) -> None:
        inlet_composition = tuple(float(value) for value in condition.state.mole_fractions)
        if len(inlet_composition) != 2:
            inlet_composition = (0.5, 0.5)
        ethanol_fraction = max(0.05, min(0.64, inlet_composition[0]))
        bounded_composition = np.array([ethanol_fraction, 1.0 - ethanol_fraction], dtype=np.float64)
        column.inlet_flow = float(condition.through_molar_flow_rate)
        column.inlet_temperature = float(condition.state.temperature)
        column.inlet_pressure = float(condition.state.pressure)
        column.inlet_composition = bounded_composition

    heater_subsystem = _UnitSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="heater_subsystem",
            process_id="heater",
            inlet_ports=("inlet",),
            outlet_ports=("outlet",),
            publication_map={"heater_subsystem/temperature": 0.0},
        ),
        apply_inlet=_apply_heater_inlet,
        step_unit=lambda duration: heater.step(duration),
        snapshot_outlets=lambda: {
            "outlet": _StreamSnapshot(
                flow=float(heater.outlet_flow),
                temperature=float(heater.outlet_temperature),
                pressure=float(heater.outlet_pressure),
                composition=_to_tuple(heater.outlet_composition),
            )
        },
        latest_port_conditions=latest_port_conditions,
        fallback_inlet=feed_condition,
        fixed_inlet=feed_condition,
    )

    cstr_subsystem = _UnitSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="cstr_subsystem",
            process_id="cstr",
            inlet_ports=("inlet",),
            outlet_ports=("outlet",),
            publication_map={"cstr_subsystem/temperature": 0.0},
        ),
        apply_inlet=_apply_cstr_inlet,
        step_unit=lambda duration: cstr.step(duration),
        snapshot_outlets=lambda: {
            "outlet": _StreamSnapshot(
                flow=float(cstr.outlet_flow),
                temperature=float(cstr.outlet_temperature),
                pressure=float(cstr.inlet_pressure),
                composition=_to_tuple(cstr.outlet_composition),
            )
        },
        latest_port_conditions=latest_port_conditions,
        fallback_inlet=_port_condition(
            pressure=172000.0,
            temperature=335.0,
            composition=(0.6, 0.4),
            flow=4.0,
            species_ids=species_ids,
        ),
    )

    flash_subsystem = _UnitSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="flash_subsystem",
            process_id="flash",
            inlet_ports=("inlet",),
            outlet_ports=("outlet",),
            publication_map={"flash_subsystem/temperature": 0.0},
        ),
        apply_inlet=_apply_flash_inlet,
        step_unit=lambda duration: flash.step(duration),
        snapshot_outlets=lambda: {
            "outlet": _StreamSnapshot(
                flow=float(flash.inlet_flow),
                temperature=float(flash.outlet_temperature),
                pressure=float(flash.flash_pressure),
                composition=_to_tuple(flash.inlet_composition),
            ),
        },
        latest_port_conditions=latest_port_conditions,
        fallback_inlet=_port_condition(
            pressure=101325.0,
            temperature=348.0,
            composition=(0.45, 0.55),
            flow=3.5,
            species_ids=species_ids,
        ),
    )

    column_subsystem = _UnitSubsystem(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="column_subsystem",
            process_id="column",
            inlet_ports=("inlet",),
            outlet_ports=("outlet",),
            publication_map={"column_subsystem/temperature": 0.0},
        ),
        apply_inlet=_apply_column_inlet,
        step_unit=lambda duration: column.step(duration),
        snapshot_outlets=lambda: {
            "outlet": _StreamSnapshot(
                flow=float(column.distillate_flow),
                temperature=float(column.inlet_temperature),
                pressure=float(column.inlet_pressure),
                composition=_to_tuple(column.distillate_composition),
            ),
        },
        latest_port_conditions=latest_port_conditions,
        fallback_inlet=_port_condition(
            pressure=101325.0,
            temperature=348.0,
            composition=(0.62, 0.38),
            flow=2.0,
            species_ids=species_ids,
        ),
    )

    process_subsystems: dict[str, _UnitSubsystem] = {
        "heater": heater_subsystem,
        "cstr": cstr_subsystem,
        "flash": flash_subsystem,
        "column": column_subsystem,
    }

    boundary_sources: dict[str, _StreamSnapshot] = {
        "feed": _StreamSnapshot(
            flow=float(feed_condition.through_molar_flow_rate),
            temperature=float(feed_condition.state.temperature),
            pressure=float(feed_condition.state.pressure),
            composition=tuple(float(v) for v in feed_condition.state.mole_fractions),
        )
    }

    boundary_step_impl = ThermoBoundaryPropagationStep(runtime_context=context)

    def _boundary_step(
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        transport_and_mixing_update: TransportAndMixingUpdate,
        macro_step_time_s: float,
    ) -> Mapping[str, PortCondition]:
        conditions = boundary_step_impl(
            network=network,
            hydraulic_result=hydraulic_result,
            transport_and_mixing_update=transport_and_mixing_update,
            macro_step_time_s=macro_step_time_s,
        )
        latest_port_conditions.clear()
        latest_port_conditions.update(conditions)
        return conditions

    def _edge_source_snapshot(
        edge_source_node_id: str, edge_source_port_name: str
    ) -> _StreamSnapshot:
        process_source = process_subsystems.get(edge_source_node_id)
        if process_source is not None:
            return process_source.stream_for_port(edge_source_port_name)
        source = boundary_sources.get(edge_source_node_id)
        if source is not None:
            return source
        return _StreamSnapshot(
            flow=0.0,
            temperature=300.0,
            pressure=101325.0,
            composition=(0.5, 0.5),
        )

    def _hydraulic_step(
        *, network: ConnectionNetwork, macro_step_time_s: float
    ) -> HydraulicSolveResult:
        del macro_step_time_s
        compiled = network.compiled
        if compiled is None:
            raise RuntimeError("Connection network must be compiled before runtime stepping.")

        unknowns: dict[str, float] = {}
        for edge in sorted(compiled.topology.edges, key=lambda item: item.edge_id):
            stream = _edge_source_snapshot(edge.source.node_id, edge.source.port_name)
            unknowns[edge.edge_id] = float(stream.flow)
            unknowns[f"{edge.edge_id}.pressure"] = float(stream.pressure)

        unknown_names = sorted(unknowns)
        solution_vector = np.asarray([unknowns[name] for name in unknown_names], dtype=np.float64)
        unknown_index_map = {name: index for index, name in enumerate(unknown_names)}
        return HydraulicSolveResult(
            converged=True,
            iterations=1,
            residual_norm=1.0e-12,
            solution_vector=solution_vector,
            unknowns=unknowns,
            unknown_index_map=unknown_index_map,
            residual_index_map={"balance": 0},
        )

    def _transport_step(
        *,
        network: ConnectionNetwork,
        hydraulic_result: HydraulicSolveResult,
        macro_step_time_s: float,
    ) -> TransportAndMixingUpdate:
        del hydraulic_result, macro_step_time_s
        compiled = network.compiled
        if compiled is None:
            raise RuntimeError("Connection network must be compiled before runtime stepping.")

        transport_results: dict[str, LagTransportUpdateResult] = {}
        for edge in sorted(compiled.topology.edges, key=lambda item: item.edge_id):
            stream = _edge_source_snapshot(edge.source.node_id, edge.source.port_name)
            transport_results[edge.edge_id] = LagTransportUpdateResult(
                state=LagTransportState(
                    composition=stream.composition,
                    temperature=float(stream.temperature),
                ),
                update_fraction=1.0,
                flow_scale=1.0,
                flow_sign_changed=False,
                held_for_near_zero_flow=False,
            )

        return TransportAndMixingUpdate(transport_results=transport_results)

    runtime = ConnectionRuntimeOrchestrator(
        runtime_context=context,
        hydraulic_solve_step=_hydraulic_step,
        transport_and_mixing_step=_transport_step,
        boundary_propagation_step=_boundary_step,
    )

    network = ConnectionNetwork(runtime_orchestrator=runtime)
    network.add_process("heater", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_process("cstr", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_process(
        "flash",
        inlet_ports=("inlet",),
        outlet_ports=("outlet",),
    )
    network.add_process(
        "column",
        inlet_ports=("inlet",),
        outlet_ports=("outlet",),
    )
    network.add_boundary_source("feed")
    network.add_boundary_sink("distillate_product")
    _ = network.connect("feed", "heater.inlet")
    _ = network.connect("heater.outlet", "cstr.inlet")
    _ = network.connect("cstr.outlet", "flash.inlet")
    _ = network.connect("flash.outlet", "column.inlet")
    _ = network.connect("column.outlet", "distillate_product")

    compiled = network.compile()
    for process_id, subsystem in process_subsystems.items():
        subsystem.attach_binding(compiled.process_bindings[process_id])

    plant = ConnectedPlantOrchestrator(
        subsystems=(heater_subsystem, cstr_subsystem, flash_subsystem, column_subsystem),
        network=network,
        runtime_orchestrator=runtime,
        runtime_context=context,
    )

    last_step = None
    for _ in range(macro_steps):
        last_step = plant.step(macro_step_time_s=macro_step_time_s)

    if last_step is None:
        raise RuntimeError("Flowsheet simulation did not execute any macro-steps.")

    coupled_column_inlet = latest_port_conditions.get(
        "column.inlet", column_subsystem.fallback_inlet
    )
    updated_port_keys = last_step.runtime_step_result.bookkeeping.updated_port_keys

    heater_outlet_composition = _to_tuple(heater.outlet_composition)
    cstr_outlet_composition = _to_tuple(cstr.outlet_composition)
    flash_vapor_composition = _to_tuple(flash.vapor_composition)
    flash_liquid_composition = _to_tuple(flash.liquid_composition)
    distillate_composition = _to_tuple(column.distillate_composition)
    bottoms_composition = _to_tuple(column.bottoms_composition)

    column_mass_balance_error = float(
        float(column.distillate_flow) + float(column.bottoms_flow) - float(column.inlet_flow)
    )

    kpis: dict[str, float | tuple[float, ...] | tuple[str, ...]] = {
        "feed_flow": float(feed_condition.through_molar_flow_rate),
        "feed_temperature": float(feed_condition.state.temperature),
        "heater_outlet_temperature": float(heater.outlet_temperature),
        "heater_outlet_composition": heater_outlet_composition,
        "cstr_outlet_temperature": float(cstr.outlet_temperature),
        "cstr_outlet_composition": cstr_outlet_composition,
        "flash_vapor_fraction": float(flash.vapor_fraction),
        "flash_vapor_flow": float(flash.vapor_flow),
        "flash_total_flow": float(flash.vapor_flow + flash.liquid_flow),
        "flash_vapor_composition": flash_vapor_composition,
        "flash_liquid_composition": flash_liquid_composition,
        "coupled_column_inlet_flow": float(coupled_column_inlet.through_molar_flow_rate),
        "coupled_column_inlet_temperature": float(coupled_column_inlet.state.temperature),
        "coupled_column_inlet_composition": tuple(
            float(value) for value in coupled_column_inlet.state.mole_fractions
        ),
        "distillate_flow": float(column.distillate_flow),
        "bottoms_flow": float(column.bottoms_flow),
        "distillate_composition": distillate_composition,
        "bottoms_composition": bottoms_composition,
        "minimum_stages": float(column.minimum_stages),
        "minimum_reflux_ratio": float(column.minimum_reflux_ratio),
        "actual_stages": float(column.actual_stages),
        "actual_reflux_ratio": float(column.actual_reflux_ratio),
        "column_mass_balance_error": column_mass_balance_error,
        "last_updated_port_keys": tuple(updated_port_keys),
    }

    if print_results:
        print("UNIT PROCESS FLOWSHEET DEMO")
        print("Feed -> Heater -> CSTR -> FlashDrum -> ShortcutDistillation")
        print(f"Feed flow [mol/s]: {kpis['feed_flow']:.4f}")
        print(f"Heater outlet temperature [K]: {kpis['heater_outlet_temperature']:.4f}")
        print(f"CSTR outlet temperature [K]: {kpis['cstr_outlet_temperature']:.4f}")
        print(f"Flash vapor fraction [-]: {kpis['flash_vapor_fraction']:.6f}")
        print(
            "Distillation ethanol purity (distillate/bottoms) [-]: "
            + f"{distillate_composition[0]:.6f}/{bottoms_composition[0]:.6f}"
        )
        print(f"Coupling-updated inlet keys: {', '.join(updated_port_keys)}")
        print(f"Column mass-balance residual [mol/s]: {column_mass_balance_error:.3e}")

    return kpis


def main() -> None:
    _ = run_flowsheet_demo(print_results=True)


if __name__ == "__main__":
    main()
