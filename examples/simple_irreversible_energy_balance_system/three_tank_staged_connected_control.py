from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path
import sys
from types import MappingProxyType
from typing import cast

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
from modular_simulation.connection.hydraulic_compile import HydraulicCompileLifecycle
from modular_simulation.connection.hydraulic_element import HydraulicElement, ValveHydraulicElement
from modular_simulation.connection.hydraulic_solver import (
    ElementEquation,
    HydraulicSystemDefinition,
)
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.framework import System
from modular_simulation.utils.wrappers import second


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


def clamp(value: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, value))


def hydrostatic_pressure_pa(volume_l: float, area_m2: float) -> float:
    volume_m3 = max(volume_l, 1e-9) * 1e-3
    height_m = volume_m3 / max(area_m2, 1e-9)
    return P_ATM_PA + (RHO_KG_PER_M3 * GRAVITY_M_PER_S2 * height_m)


def valve_flow_lps(open_fraction: float, flow_gain: float, delta_p_pa: float) -> float:
    return max(0.0, flow_gain * clamp(open_fraction, 0.0, 1.0) * sqrt(max(delta_p_pa, 0.0)))


def _hydraulic_system(topology) -> HydraulicSystemDefinition:
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
                unknown_name_map=MappingProxyType(
                    {
                        "flow_rate": f"flow_{edge.edge_id}",
                    }
                ),
                residual_name_map=MappingProxyType(
                    {
                        "head_balance": f"eq_{edge.edge_id}",
                    }
                ),
            )
        )
    return HydraulicSystemDefinition(equations=tuple(equations), linear_residual_equations=())


@dataclass(slots=True)
class TankUnit:
    name: str
    area_m2: float
    system: System

    @property
    def model(self) -> EnergyBalanceProcessModel:
        return cast(EnergyBalanceProcessModel, self.system.process_model)


def make_tank(name: str, area_m2: float, initial_b: float) -> TankUnit:
    model = EnergyBalanceProcessModel(
        V=900.0,
        A=max(2.2 - initial_b, 0.1),
        B=initial_b,
        T=308.15,
        T_J=288.15,
        F_in=0.55,
        T_J_in=285.15,
        CA_in=FRESH_A_MOL_PER_L,
        T_in=FRESH_T_K,
        Cv=0.018,
        jacket_volume=850.0,
        jacket_flow=0.55,
    )
    system = System(
        dt=second(10.0),
        process_model=model,
        sensors=(),
        calculations=(),
        control_elements=(),
        show_progress=False,
    )
    return TankUnit(name=name, area_m2=area_m2, system=system)


def build_network() -> ConnectionNetwork:
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


def queue_valves(network: ConnectionNetwork, openings: dict[str, float]) -> str:
    return network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "set_valve_open_fraction",
                    "line_id": line_id,
                    "open_fraction": clamp(opening, 0.05, 1.0),
                }
                for line_id, opening in openings.items()
            ],
        }
    )


def run_three_tank_staged_control(
    *,
    duration_s: float = 4.0 * 3_600.0,
    dt_s: float = 10.0,
    final_product_target_b_mol_per_l: float = 4.80,
    step_change_time_s: float | None = None,
    step_target_b_mol_per_l: float | None = None,
) -> dict[str, object]:
    network = build_network()

    tank_1 = make_tank("tank_1", area_m2=1.20, initial_b=0.00)
    tank_2 = make_tank("tank_2", area_m2=1.00, initial_b=0.10)
    tank_3 = make_tank("tank_3", area_m2=0.85, initial_b=0.20)

    v1_sp_l = 900.0
    v2_sp_l = 900.0
    v3_sp_l = 900.0

    gain_feed = 0.0036
    gain_interstage = 0.0100
    gain_product = 0.0105

    open_feed_1 = 0.44
    open_feed_2 = 0.32
    open_feed_3 = 0.27
    open_1_to_2 = 0.58
    open_2_to_3 = 0.55
    open_product = 0.50

    composition_gain_2 = 0.08
    composition_gain_3 = 0.10
    level_comp_2 = 0.00035
    level_comp_3 = 0.00060

    steps = int(duration_s / dt_s)
    request_ids: list[str] = []
    history: list[dict[str, float]] = []

    for index in range(steps):
        time_s = index * dt_s
        v1_l = float(tank_1.model.V)
        v2_l = float(tank_2.model.V)
        v3_l = float(tank_3.model.V)
        b3 = float(tank_3.model.B)

        target_b3_sp = final_product_target_b_mol_per_l
        if (
            step_change_time_s is not None
            and step_target_b_mol_per_l is not None
            and time_s >= step_change_time_s
        ):
            target_b3_sp = step_target_b_mol_per_l

        composition_error = target_b3_sp - b3
        open_1_to_2 = clamp(0.55 + (0.0010 * (v1_l - v1_sp_l)), 0.05, 1.0)
        open_2_to_3 = clamp(0.55 + (0.0011 * (v2_l - v2_sp_l)), 0.05, 1.0)
        open_product = clamp(
            0.58 + (0.0014 * (v3_l - v3_sp_l)) - (0.05 * composition_error),
            0.05,
            1.0,
        )

        open_feed_2 = clamp(
            0.30 - (composition_gain_2 * composition_error) - (level_comp_2 * (v2_l - v2_sp_l)),
            0.05,
            0.95,
        )
        open_feed_3 = clamp(
            0.24 - (composition_gain_3 * composition_error) - (level_comp_3 * (v3_l - v3_sp_l)),
            0.05,
            0.95,
        )

        p1_pa = hydrostatic_pressure_pa(v1_l, tank_1.area_m2)
        p2_pa = hydrostatic_pressure_pa(v2_l, tank_2.area_m2)
        p3_pa = hydrostatic_pressure_pa(v3_l, tank_3.area_m2)

        flow_12_lps = valve_flow_lps(open_1_to_2, gain_interstage, p1_pa - P_ATM_PA)
        flow_23_lps = valve_flow_lps(open_2_to_3, gain_interstage, p2_pa - P_ATM_PA)

        flow_feed_1_lps = valve_flow_lps(
            open_feed_1, gain_feed, FRESH_SUPPLY_PRESSURE_PA - P_ATM_PA
        )
        flow_feed_2_lps = valve_flow_lps(
            open_feed_2, gain_feed, FRESH_SUPPLY_PRESSURE_PA - P_ATM_PA
        )
        flow_feed_3_lps = valve_flow_lps(
            open_feed_3, gain_feed, FRESH_SUPPLY_PRESSURE_PA - P_ATM_PA
        )
        flow_product_lps = valve_flow_lps(open_product, gain_product, p3_pa - P_ATM_PA)

        request_ids.append(
            queue_valves(
                network,
                {
                    LINE_FEED_1: open_feed_1,
                    LINE_1_TO_2: open_1_to_2,
                    LINE_FEED_2: open_feed_2,
                    LINE_2_TO_3: open_2_to_3,
                    LINE_FEED_3: open_feed_3,
                    LINE_PRODUCT: open_product,
                },
            )
        )
        network.step(macro_step_time_s=dt_s)

        flow_in_1 = flow_feed_1_lps
        flow_in_2 = flow_12_lps + flow_feed_2_lps
        flow_in_3 = flow_23_lps + flow_feed_3_lps

        ca_in_2 = float(tank_2.model.CA_in)
        t_in_2 = float(tank_2.model.T_in)
        if flow_in_2 > 1e-9:
            ca_in_2 = (
                (flow_12_lps * float(tank_1.model.A)) + (flow_feed_2_lps * FRESH_A_MOL_PER_L)
            ) / flow_in_2
            t_in_2 = (
                (flow_12_lps * float(tank_1.model.T)) + (flow_feed_2_lps * FRESH_T_K)
            ) / flow_in_2

        ca_in_3 = float(tank_3.model.CA_in)
        t_in_3 = float(tank_3.model.T_in)
        if flow_in_3 > 1e-9:
            ca_in_3 = (
                (flow_23_lps * float(tank_2.model.A)) + (flow_feed_3_lps * FRESH_A_MOL_PER_L)
            ) / flow_in_3
            t_in_3 = (
                (flow_23_lps * float(tank_2.model.T)) + (flow_feed_3_lps * FRESH_T_K)
            ) / flow_in_3

        tank_1.model.F_in = flow_in_1
        tank_1.model.Cv = flow_12_lps / max(sqrt(max(v1_l, 1e-9)), 1e-9)
        tank_1.model.CA_in = FRESH_A_MOL_PER_L
        tank_1.model.T_in = FRESH_T_K
        tank_1.model.T_J_in = clamp(286.0 + (2.5 * composition_error), 280.0, 295.0)

        tank_2.model.F_in = flow_in_2
        tank_2.model.Cv = flow_23_lps / max(sqrt(max(v2_l, 1e-9)), 1e-9)
        tank_2.model.CA_in = ca_in_2
        tank_2.model.T_in = t_in_2
        tank_2.model.T_J_in = clamp(285.0 + (4.0 * composition_error), 278.0, 296.0)

        tank_3.model.F_in = flow_in_3
        tank_3.model.Cv = flow_product_lps / max(sqrt(max(v3_l, 1e-9)), 1e-9)
        tank_3.model.CA_in = ca_in_3
        tank_3.model.T_in = t_in_3
        tank_3.model.T_J_in = clamp(284.0 + (6.0 * composition_error), 276.0, 296.0)

        tank_1.system.step(duration=second(dt_s))
        tank_2.system.step(duration=second(dt_s))
        tank_3.system.step(duration=second(dt_s))

        if (index % max(int(300.0 / dt_s), 1)) == 0:
            history.append(
                {
                    "time_s": time_s,
                    "target_b3_sp": target_b3_sp,
                    "tank1_B": float(tank_1.model.B),
                    "tank2_B": float(tank_2.model.B),
                    "tank3_B": float(tank_3.model.B),
                    "tank1_V": float(tank_1.model.V),
                    "tank2_V": float(tank_2.model.V),
                    "tank3_V": float(tank_3.model.V),
                    "open_feed_2": open_feed_2,
                    "open_feed_3": open_feed_3,
                    "open_1_to_2": open_1_to_2,
                    "open_2_to_3": open_2_to_3,
                    "open_product": open_product,
                }
            )

    summary: dict[str, object] = {
        "target_b3_initial": final_product_target_b_mol_per_l,
        "target_b3_step_time_s": step_change_time_s,
        "target_b3_step_value": step_target_b_mol_per_l,
        "target_b3_final_sp": history[-1]["target_b3_sp"]
        if history
        else final_product_target_b_mol_per_l,
        "final_b3": float(tank_3.model.B),
        "final_a3": float(tank_3.model.A),
        "final_t3_k": float(tank_3.model.T),
        "final_volumes_l": {
            "tank_1": float(tank_1.model.V),
            "tank_2": float(tank_2.model.V),
            "tank_3": float(tank_3.model.V),
        },
        "final_valve_openings": {
            "fresh_feed_1": open_feed_1,
            "fresh_feed_2": open_feed_2,
            "fresh_feed_3": open_feed_3,
            "tank1_to_tank2": open_1_to_2,
            "tank2_to_tank3": open_2_to_3,
            "tank3_to_product": open_product,
        },
        "queued_valve_request_count": len(request_ids),
        "last_valve_request_id": request_ids[-1] if request_ids else None,
        "history": history,
    }
    return summary


if __name__ == "__main__":
    result = run_three_tank_staged_control()
    print("Three-stage connected train summary")
    print(f"  target B3 initial [mol/L]: {result['target_b3_initial']:.3f}")
    print(f"  target B3 final SP [mol/L]: {result['target_b3_final_sp']:.3f}")
    print(f"  final B3  [mol/L]: {result['final_b3']:.3f}")
    print(f"  final T3      [K]: {result['final_t3_k']:.2f}")
    print(f"  final volumes [L]: {result['final_volumes_l']}")
    print(f"  final openings   : {result['final_valve_openings']}")
