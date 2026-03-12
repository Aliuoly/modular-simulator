from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from math import isfinite, sqrt
from pathlib import Path
import sys
from typing import Annotated, cast

try:
    from examples.simple_irreversible_energy_balance_system.process_definition import (
        EnergyBalanceProcessModel,
    )
except ModuleNotFoundError:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from examples.simple_irreversible_energy_balance_system.process_definition import (
        EnergyBalanceProcessModel,
    )
from modular_simulation.components import (
    ControlElement,
    PIDController,
    SampledDelayedSensor,
    Trajectory,
)
from modular_simulation.connection.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulic_element import HydraulicElement, ValveHydraulicElement
from modular_simulation.connection.hydraulic_solver import (
    ElementEquation,
    HydraulicSystemDefinition,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.pressure_inference import (
    BoundaryEndpoint,
    EndpointDescriptor,
    ProcessPortEndpoint,
    TopologyEndpointContext,
    build_topology_endpoint_context,
    hydrostatic_pressure_from_submerged_head_pa,
    resolve_edge_pressure_deltas_pa,
)
from modular_simulation.connection.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.topology import TopologyGraph
from modular_simulation.framework import System
from modular_simulation.measurables import StateMetadata as M
from modular_simulation.measurables import StateType as T
from modular_simulation.utils.wrappers import second
from types import MappingProxyType


P_ATM_PA = 101_325.0
RHO_KG_PER_M3 = 997.0
GRAVITY_M_PER_S2 = 9.81
FRESH_SUPPLY_PRESSURE_PA = 140_000.0
FRESH_A_MOL_PER_L = 2.4
FRESH_T_K = 288.15

LINE_FEED_1 = "line_fresh1_to_tank1"
LINE_FEED_2 = "line_fresh2_to_tank2"
LINE_FEED_3 = "line_fresh3_to_tank3"
LINE_1_TO_2 = "line_tank1_to_tank2"
LINE_2_TO_3 = "line_tank2_to_tank3"
LINE_PRODUCT = "line_tank3_to_product"

VALVE_MV_TO_LINE = {
    "mv_open_1_to_2": LINE_1_TO_2,
    "mv_open_2_to_3": LINE_2_TO_3,
    "mv_open_product": LINE_PRODUCT,
    "mv_open_feed_2": LINE_FEED_2,
    "mv_open_feed_3": LINE_FEED_3,
}
LINE_TO_VALVE_MV = {line_id: mv_tag for mv_tag, line_id in VALVE_MV_TO_LINE.items()}
TANK_LOOP_ORDER: tuple[str, ...] = ("tank_1", "tank_2", "tank_3")
LINE_ORDER: tuple[str, ...] = (
    LINE_FEED_1,
    LINE_1_TO_2,
    LINE_FEED_2,
    LINE_2_TO_3,
    LINE_FEED_3,
    LINE_PRODUCT,
)
FEED_FLOW_GAIN = 0.0036
INTERSTAGE_FLOW_GAIN = 0.0100
PRODUCT_FLOW_GAIN = 0.0105
FIXED_FEED_1_OPEN_FRACTION = 0.44

LINE_FLOW_GAIN = {
    LINE_FEED_1: FEED_FLOW_GAIN,
    LINE_1_TO_2: INTERSTAGE_FLOW_GAIN,
    LINE_FEED_2: FEED_FLOW_GAIN,
    LINE_2_TO_3: INTERSTAGE_FLOW_GAIN,
    LINE_FEED_3: FEED_FLOW_GAIN,
    LINE_PRODUCT: PRODUCT_FLOW_GAIN,
}
DEFAULT_PORT_HEIGHT_FRACTION_BY_DIRECTION: dict[str, float] = {
    "inlet": 0.85,
    "outlet": 0.12,
}
PORT_HEIGHT_FRACTION_BY_PORT: dict[str, float] = {
    "fresh_in": 0.90,
    "makeup_in": 0.82,
    "cascade_in": 0.70,
    "out": 0.12,
    "aux_out": 0.45,
}
REFERENCE_LIQUID_VOLUME_L = 900.0

CONTROLLED = partial(M, type=T.CONTROLLED)


class TankProcessModel(EnergyBalanceProcessModel):
    mv_open_1_to_2: Annotated[
        float,
        CONTROLLED(unit="1", description="tank_1 to tank_2 valve opening"),
    ] = 0.55
    mv_open_2_to_3: Annotated[
        float,
        CONTROLLED(unit="1", description="tank_2 to tank_3 valve opening"),
    ] = 0.55
    mv_open_product: Annotated[
        float,
        CONTROLLED(unit="1", description="tank_3 to product valve opening"),
    ] = 0.55
    mv_open_feed_2: Annotated[
        float,
        CONTROLLED(unit="1", description="fresh feed 2 valve opening"),
    ] = 0.28
    mv_open_feed_3: Annotated[
        float,
        CONTROLLED(unit="1", description="fresh feed 3 valve opening"),
    ] = 0.24


@dataclass(slots=True)
class TankUnit:
    name: str
    area_m2: float
    system: System

    @property
    def model(self) -> TankProcessModel:
        return cast(TankProcessModel, self.system.process_model)


@dataclass(frozen=True, slots=True)
class TankStageLink:
    tank_id: str
    upstream_tank_id: str | None
    cascade_line_id: str | None
    makeup_line_id: str
    discharge_line_id: str


STAGE_LINKS: tuple[TankStageLink, ...] = (
    TankStageLink(
        tank_id="tank_1",
        upstream_tank_id=None,
        cascade_line_id=None,
        makeup_line_id=LINE_FEED_1,
        discharge_line_id=LINE_1_TO_2,
    ),
    TankStageLink(
        tank_id="tank_2",
        upstream_tank_id="tank_1",
        cascade_line_id=LINE_1_TO_2,
        makeup_line_id=LINE_FEED_2,
        discharge_line_id=LINE_2_TO_3,
    ),
    TankStageLink(
        tank_id="tank_3",
        upstream_tank_id="tank_2",
        cascade_line_id=LINE_2_TO_3,
        makeup_line_id=LINE_FEED_3,
        discharge_line_id=LINE_PRODUCT,
    ),
)


def _clamp_open_fraction(value: float) -> float:
    return min(1.0, max(0.05, float(value)))


def valve_flow_lps(open_fraction: float, flow_gain: float, delta_p_pa: float) -> float:
    return max(0.0, flow_gain * _clamp_open_fraction(open_fraction) * sqrt(max(delta_p_pa, 0.0)))


def _tank_liquid_height_m(volume_l: float, area_m2: float) -> float:
    volume_m3 = max(volume_l, 1e-9) * 1e-3
    return volume_m3 / max(area_m2, 1e-9)


def _tank_reference_height_m(area_m2: float) -> float:
    return _tank_liquid_height_m(REFERENCE_LIQUID_VOLUME_L, area_m2)


def _hydraulic_system(topology: TopologyGraph) -> HydraulicSystemDefinition:
    equations: list[ElementEquation] = []
    for edge in sorted(topology.edges, key=lambda item: item.edge_id):
        source_id = edge.source.node_id
        upstream_pressure = (
            FRESH_SUPPLY_PRESSURE_PA if source_id.startswith("fresh_feed") else (P_ATM_PA + 4_000.0)
        )
        equations.append(
            ElementEquation(
                name=f"eq_{edge.edge_id}",
                element=cast(HydraulicElement, cast(object, ValveHydraulicElement())),
                inputs=MappingProxyType(
                    {
                        "upstream_pressure": upstream_pressure,
                        "downstream_pressure": P_ATM_PA,
                    }
                ),
                parameters=MappingProxyType(
                    {
                        "valve_resistance": 1.0,
                        "delta": 1e-6,
                    }
                ),
                unknown_name_map=MappingProxyType({"flow_rate": f"flow_{edge.edge_id}"}),
                residual_name_map=MappingProxyType({"head_balance": f"eq_{edge.edge_id}"}),
            )
        )
    return HydraulicSystemDefinition(equations=tuple(equations), linear_residual_equations=())


def _build_network() -> ConnectionNetwork:
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=_hydraulic_system,
        runtime_orchestrator=ConnectionRuntimeOrchestrator(),
    )
    network.add_process("tank_1", inlet_ports=("fresh_in",), outlet_ports=("out",))
    network.add_process(
        "tank_2",
        inlet_ports=("cascade_in", "makeup_in"),
        outlet_ports=("out", "aux_out"),
    )
    network.add_process(
        "tank_3",
        inlet_ports=("cascade_in", "makeup_in"),
        outlet_ports=("out", "aux_out"),
    )
    network.add_boundary_source("fresh_feed_1")
    network.add_boundary_source("fresh_feed_2")
    network.add_boundary_source("fresh_feed_3")
    network.add_boundary_sink("product_sink")

    network.connect("fresh_feed_1", "tank_1.fresh_in", edge_id=LINE_FEED_1)
    network.connect("tank_1.out", "tank_2.cascade_in", edge_id=LINE_1_TO_2)
    network.connect("fresh_feed_2", "tank_2.makeup_in", edge_id=LINE_FEED_2)
    network.connect("tank_2.out", "tank_3.cascade_in", edge_id=LINE_2_TO_3)
    network.connect("fresh_feed_3", "tank_3.makeup_in", edge_id=LINE_FEED_3)
    network.connect("tank_3.out", "product_sink.inlet", edge_id=LINE_PRODUCT)

    for line_id, radius_m, length_m in (
        (LINE_FEED_1, 0.020, 12.0),
        (LINE_1_TO_2, 0.030, 8.0),
        (LINE_FEED_2, 0.020, 12.0),
        (LINE_2_TO_3, 0.030, 8.0),
        (LINE_FEED_3, 0.020, 12.0),
        (LINE_PRODUCT, 0.032, 10.0),
    ):
        network.configure_line_geometry(
            line_id=line_id,
            radius_m=radius_m,
            length_m=length_m,
            equation_name=f"eq_{line_id}",
            resistance_parameter_name="valve_resistance",
        )
        network.configure_line_resistance(line_id=line_id, mode="derived")
        network.attach_line_valve(
            line_id=line_id,
            valve_id=f"valve_{line_id}",
            minimum_open_fraction=0.05,
            maximum_open_fraction=1.0,
            initial_open_fraction=0.6,
            equation_name=f"eq_{line_id}",
            resistance_parameter_name="valve_resistance",
        )
    network.compile()
    return network


def _level_element(mv_tag: str) -> ControlElement:
    return ControlElement(
        mv_tag=mv_tag,
        mv_range=(0.05, 1.0),
        mv_trajectory=Trajectory(y0=0.55),
        controller=PIDController(
            cv_tag="V",
            cv_range=(0.0, 2_000.0),
            reference_trajectory=Trajectory(y0=900.0),
            Kp=1.0e-3,
            Ti=300.0,
        ),
    )


def _composition_element(mv_tag: str, reference_b: float, gain: float) -> ControlElement:
    return ControlElement(
        mv_tag=mv_tag,
        mv_range=(0.05, 1.0),
        mv_trajectory=Trajectory(y0=0.25),
        controller=PIDController(
            cv_tag="B",
            cv_range=(0.0, 8.0),
            reference_trajectory=Trajectory(y0=reference_b),
            Kp=gain,
            Ti=500.0,
            inverted=True,
        ),
    )


def _jacket_element() -> ControlElement:
    return ControlElement(
        mv_tag="T_J_in",
        mv_range=(275.0, 310.0),
        mv_trajectory=Trajectory(y0=286.0),
        controller=PIDController(
            cv_tag="T_J",
            cv_range=(250.0, 350.0),
            reference_trajectory=Trajectory(y0=289.0),
            Kp=0.2,
            Ti=150.0,
        ),
    )


def _make_tank_unit(
    name: str,
    area_m2: float,
    initial_b: float,
    control_elements: tuple[ControlElement, ...],
) -> TankUnit:
    sensors = (
        SampledDelayedSensor(measurement_tag="V", unit="L"),
        SampledDelayedSensor(measurement_tag="B", unit="mol/L"),
        SampledDelayedSensor(measurement_tag="T_J", unit="K"),
    )
    model = TankProcessModel(
        V=900.0,
        A=max(2.2 - initial_b, 0.1),
        B=initial_b,
        T=308.15,
        T_J=288.15,
        F_in=0.55,
        T_J_in=286.0,
        CA_in=FRESH_A_MOL_PER_L,
        T_in=FRESH_T_K,
        Cv=0.018,
        jacket_volume=850.0,
        jacket_flow=0.55,
        mv_open_1_to_2=0.55,
        mv_open_2_to_3=0.55,
        mv_open_product=0.55,
        mv_open_feed_2=0.28,
        mv_open_feed_3=0.24,
    )
    system = System(
        dt=second(10.0),
        process_model=model,
        sensors=sensors,
        calculations=(),
        control_elements=control_elements,
        show_progress=False,
    )
    return TankUnit(name=name, area_m2=area_m2, system=system)


def build_three_tank_units() -> dict[str, TankUnit]:
    return {
        "tank_1": _make_tank_unit(
            "tank_1",
            area_m2=1.20,
            initial_b=0.00,
            control_elements=(_level_element("mv_open_1_to_2"), _jacket_element()),
        ),
        "tank_2": _make_tank_unit(
            "tank_2",
            area_m2=1.00,
            initial_b=0.10,
            control_elements=(
                _level_element("mv_open_2_to_3"),
                _composition_element("mv_open_feed_2", reference_b=3.20, gain=0.04),
                _jacket_element(),
            ),
        ),
        "tank_3": _make_tank_unit(
            "tank_3",
            area_m2=0.85,
            initial_b=0.20,
            control_elements=(
                _level_element("mv_open_product"),
                _composition_element("mv_open_feed_3", reference_b=4.80, gain=0.05),
                _jacket_element(),
            ),
        ),
    }


def _collect_valve_mv_outputs(tank_units: dict[str, TankUnit]) -> dict[str, float]:
    outputs: dict[str, float] = {}
    for tank in tank_units.values():
        for element in tank.system.control_elements:
            if element.mv_tag not in VALVE_MV_TO_LINE:
                continue
            raw_value = float(getattr(tank.model, element.mv_tag))
            outputs[element.mv_tag] = _clamp_open_fraction(raw_value)
    for mv_tag in VALVE_MV_TO_LINE:
        outputs.setdefault(mv_tag, 0.05)
    return outputs


def _queue_valve_reconfiguration(
    network: ConnectionNetwork,
    mv_outputs: dict[str, float],
) -> tuple[str, dict[str, float]]:
    bounded_outputs = {
        mv_tag: _clamp_open_fraction(mv_outputs.get(mv_tag, 0.05)) for mv_tag in VALVE_MV_TO_LINE
    }
    mutations = [
        {
            "operation": "set_valve_open_fraction",
            "line_id": line_id,
            "open_fraction": bounded_outputs[mv_tag],
        }
        for mv_tag, line_id in VALVE_MV_TO_LINE.items()
    ]
    request_id = network.queue_reconfiguration(
        {"operation": "batch_update", "mutations": mutations}
    )
    return request_id, bounded_outputs


def _resolve_port_height_fraction(*, endpoint: ProcessPortEndpoint) -> float:
    return float(
        PORT_HEIGHT_FRACTION_BY_PORT.get(
            endpoint.port_name,
            DEFAULT_PORT_HEIGHT_FRACTION_BY_DIRECTION[endpoint.direction],
        )
    )


def _process_endpoint_pressure_pa(
    *,
    endpoint: ProcessPortEndpoint,
    tank_units: dict[str, TankUnit],
) -> float:
    tank = tank_units.get(endpoint.process_id)
    if tank is None:
        raise KeyError(f"unknown process endpoint process_id {endpoint.process_id!r}")
    liquid_height_m = _tank_liquid_height_m(float(tank.model.V), tank.area_m2)
    reference_height_m = _tank_reference_height_m(tank.area_m2)
    port_height_fraction = _resolve_port_height_fraction(endpoint=endpoint)
    port_elevation_m = max(0.0, min(1.0, port_height_fraction)) * reference_height_m
    return hydrostatic_pressure_from_submerged_head_pa(
        reference_pressure_pa=P_ATM_PA,
        liquid_density_kg_per_m3=RHO_KG_PER_M3,
        gravity_m_per_s2=GRAVITY_M_PER_S2,
        liquid_surface_elevation_m=liquid_height_m,
        port_elevation_m=port_elevation_m,
    )


def _boundary_endpoint_pressure_pa(*, endpoint: BoundaryEndpoint) -> float:
    if endpoint.direction == "source":
        return FRESH_SUPPLY_PRESSURE_PA
    if endpoint.direction == "sink":
        return P_ATM_PA
    raise ValueError(f"unsupported boundary direction {endpoint.direction!r}")


def _make_endpoint_pressure_resolver(
    *,
    tank_units: dict[str, TankUnit],
):
    def _resolve(endpoint: EndpointDescriptor) -> float:
        if isinstance(endpoint, ProcessPortEndpoint):
            return _process_endpoint_pressure_pa(endpoint=endpoint, tank_units=tank_units)
        return _boundary_endpoint_pressure_pa(endpoint=endpoint)

    return _resolve


def _compute_line_pressure_deltas_pa(
    *,
    topology: TopologyGraph,
    endpoint_context: TopologyEndpointContext,
    tank_units: dict[str, TankUnit],
) -> dict[str, float]:
    return resolve_edge_pressure_deltas_pa(
        topology=topology,
        endpoint_context=endpoint_context,
        endpoint_pressure_resolver=_make_endpoint_pressure_resolver(tank_units=tank_units),
    )


def _line_open_fraction(
    line_id: str,
    mv_outputs: dict[str, float],
    fixed_feed_1_open_fraction: float,
) -> float:
    if line_id == LINE_FEED_1:
        return _clamp_open_fraction(fixed_feed_1_open_fraction)
    mv_tag = LINE_TO_VALVE_MV.get(line_id)
    if mv_tag is None:
        return 1.0
    return _clamp_open_fraction(mv_outputs[mv_tag])


def _compute_line_flows_lps(
    *,
    mv_outputs: dict[str, float],
    line_pressure_deltas_pa: dict[str, float],
    fixed_feed_1_open_fraction: float,
) -> dict[str, float]:
    flows_lps: dict[str, float] = {}
    for line_id in sorted(line_pressure_deltas_pa):
        flows_lps[line_id] = valve_flow_lps(
            _line_open_fraction(
                line_id=line_id,
                mv_outputs=mv_outputs,
                fixed_feed_1_open_fraction=fixed_feed_1_open_fraction,
            ),
            LINE_FLOW_GAIN.get(line_id, INTERSTAGE_FLOW_GAIN),
            line_pressure_deltas_pa[line_id],
        )
    return flows_lps


def _apply_stage_hydraulic_coupling(
    *,
    tank_units: dict[str, TankUnit],
    flows_lps: dict[str, float],
) -> None:
    for link in STAGE_LINKS:
        model = tank_units[link.tank_id].model
        flow_in_lps = 0.0
        ca_weighted_sum = 0.0
        t_weighted_sum = 0.0

        cascade_flow_lps = 0.0
        if link.cascade_line_id is not None and link.upstream_tank_id is not None:
            cascade_flow_lps = flows_lps[link.cascade_line_id]
            upstream_model = tank_units[link.upstream_tank_id].model
            ca_weighted_sum += cascade_flow_lps * float(upstream_model.A)
            t_weighted_sum += cascade_flow_lps * float(upstream_model.T)
            flow_in_lps += cascade_flow_lps

        makeup_flow_lps = flows_lps[link.makeup_line_id]
        ca_weighted_sum += makeup_flow_lps * FRESH_A_MOL_PER_L
        t_weighted_sum += makeup_flow_lps * FRESH_T_K
        flow_in_lps += makeup_flow_lps

        ca_in = float(model.CA_in)
        t_in = float(model.T_in)
        if flow_in_lps > 1e-9:
            ca_in = ca_weighted_sum / flow_in_lps
            t_in = t_weighted_sum / flow_in_lps

        discharge_flow_lps = flows_lps[link.discharge_line_id]
        model.F_in = flow_in_lps
        model.Cv = discharge_flow_lps / max(sqrt(max(float(model.V), 1e-9)), 1e-9)
        model.CA_in = ca_in
        model.T_in = t_in


def _history_row(
    *,
    time_s: float,
    target_b3_reference: float,
    mv_outputs: dict[str, float],
    tank_units: dict[str, TankUnit],
) -> dict[str, float]:
    tank_1 = tank_units["tank_1"].model
    tank_2 = tank_units["tank_2"].model
    tank_3 = tank_units["tank_3"].model
    row = {
        "time_h": float(time_s) / 3_600.0,
        "target_b3_reference": float(target_b3_reference),
        "v1_l": float(tank_1.V),
        "v2_l": float(tank_2.V),
        "v3_l": float(tank_3.V),
        "b1_mol_per_l": float(tank_1.B),
        "b2_mol_per_l": float(tank_2.B),
        "b3_mol_per_l": float(tank_3.B),
        "open_1_to_2": _clamp_open_fraction(mv_outputs["mv_open_1_to_2"]),
        "open_2_to_3": _clamp_open_fraction(mv_outputs["mv_open_2_to_3"]),
        "open_product": _clamp_open_fraction(mv_outputs["mv_open_product"]),
        "open_feed_2": _clamp_open_fraction(mv_outputs["mv_open_feed_2"]),
        "open_feed_3": _clamp_open_fraction(mv_outputs["mv_open_feed_3"]),
    }
    return row


def run_three_tank_staged_connected_components(
    *,
    duration_s: float = 4.0 * 3_600.0,
    dt_s: float = 10.0,
    final_product_target_b_mol_per_l: float = 4.80,
    step_change_time_s: float = 3_600.0,
    step_target_b_mol_per_l: float = 5.05,
) -> dict[str, object]:
    dt_s = max(float(dt_s), 1e-6)
    steps = max(int(float(duration_s) / dt_s), 0)
    network = _build_network()
    compiled = network.compiled
    if compiled is None:
        raise RuntimeError("connection network compile did not produce a compiled graph")
    topology = compiled.topology
    tank_units = build_three_tank_units()
    tank_2 = tank_units["tank_2"]
    tank_3 = tank_units["tank_3"]
    endpoint_context = build_topology_endpoint_context(topology)

    tank_2.system.extend_controller_reference_trajectory(
        cv_tag="B",
        value=0.67 * final_product_target_b_mol_per_l,
    )
    tank_3.system.extend_controller_reference_trajectory(
        cv_tag="B",
        value=final_product_target_b_mol_per_l,
    )

    request_ids: list[str] = []
    history: list[dict[str, float]] = []
    target_b3_reference = final_product_target_b_mol_per_l
    initial_mv = _collect_valve_mv_outputs(tank_units)
    last_bridge_openings = {
        mv_tag: _clamp_open_fraction(initial_mv.get(mv_tag, 0.05)) for mv_tag in VALVE_MV_TO_LINE
    }
    history.append(
        _history_row(
            time_s=0.0,
            target_b3_reference=target_b3_reference,
            mv_outputs=last_bridge_openings,
            tank_units=tank_units,
        )
    )

    step_applied = False

    for index in range(steps):
        time_s = index * dt_s

        if (not step_applied) and (time_s >= step_change_time_s):
            target_b3_reference = step_target_b_mol_per_l
            tank_2.system.extend_controller_reference_trajectory(
                cv_tag="B", value=0.67 * target_b3_reference
            )
            tank_3.system.extend_controller_reference_trajectory(
                cv_tag="B", value=target_b3_reference
            )
            step_applied = True

        mv_outputs = _collect_valve_mv_outputs(tank_units)
        line_pressure_deltas_pa = _compute_line_pressure_deltas_pa(
            topology=topology,
            endpoint_context=endpoint_context,
            tank_units=tank_units,
        )
        line_flows_lps = _compute_line_flows_lps(
            mv_outputs=mv_outputs,
            line_pressure_deltas_pa=line_pressure_deltas_pa,
            fixed_feed_1_open_fraction=FIXED_FEED_1_OPEN_FRACTION,
        )
        _apply_stage_hydraulic_coupling(tank_units=tank_units, flows_lps=line_flows_lps)

        for tank_id in TANK_LOOP_ORDER:
            tank_units[tank_id].system.step(duration=second(dt_s))

        step_mv = _collect_valve_mv_outputs(tank_units)
        request_id, bounded_step_mv = _queue_valve_reconfiguration(network, step_mv)
        request_ids.append(request_id)
        last_bridge_openings = bounded_step_mv

        network.step(macro_step_time_s=dt_s)

        history.append(
            _history_row(
                time_s=time_s + dt_s,
                target_b3_reference=target_b3_reference,
                mv_outputs=bounded_step_mv,
                tank_units=tank_units,
            )
        )

    final_openings = dict(last_bridge_openings)
    for mv_tag in list(final_openings):
        if not isfinite(final_openings[mv_tag]):
            final_openings[mv_tag] = 0.05

    return {
        "history": history,
        "queued_valve_request_count": len(request_ids),
        "last_valve_request_id": request_ids[-1] if request_ids else None,
        "final_valve_openings": final_openings,
        "final_b3_mol_per_l": float(tank_3.model.B),
        "final_v3_l": float(tank_3.model.V),
    }
