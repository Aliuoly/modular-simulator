from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Any, cast, override

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import solve_ivp

from modular_simulation.connection.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
    ConnectedPlantPhaseHooks,
)
from modular_simulation.connection.connection_layer import TransportAndMixingUpdate
from modular_simulation.connection.hydraulic_solver import HydraulicSolveResult
from modular_simulation.connection.junction import mix_junction_state
from modular_simulation.connection.network import ConnectionNetwork
from modular_simulation.connection.process_binding import ProcessBinding
from modular_simulation.connection.runtime import ConnectionRuntimeOrchestrator
from modular_simulation.connection.state import MaterialState, PortCondition
from modular_simulation.connection.subsystem_descriptor import Subsystem, SubsystemRuntimeDescriptor
from modular_simulation.measurables.process_model import (
    ProcessModel,
    StateMetadata as M,
    StateType as T,
)
from modular_simulation.utils.typing import ArrayIndex

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class TankCascadeConfig:
    horizon_s: float = 8.0
    dt_s: float = 0.05
    pressure_pa: float = 101325.0
    temperature_k: float = 298.15
    feed_reactant_fraction: float = 1.0
    flow_rate_mol_per_s: float = 1.0
    tank_a_holdup_mol: float = 1.8
    tank_b_holdup_mol: float = 2.2
    tank_a_rate_constant_per_s: float = 0.35
    tank_b_rate_constant_per_s: float = 0.18
    use_subsystem_abstraction: bool = True


@dataclass(frozen=True)
class TwoTankComparisonResult:
    times_s: tuple[float, ...]
    tank_a_connection: tuple[float, ...]
    tank_b_connection: tuple[float, ...]
    tank_a_reference: tuple[float, ...]
    tank_b_reference: tuple[float, ...]
    max_abs_error_a: float
    max_abs_error_b: float
    rmse_b: float
    b_lag_steps: int
    monotonic_decay_a: bool
    monotonic_decay_b: bool
    b_not_below_a_fraction: float


class FirstOrderLiquidTankModel(ProcessModel):
    reactant_fraction: Annotated[
        float,
        M(type=T.DIFFERENTIAL, unit="", description="Tank reactant mole fraction"),
    ] = 1.0
    outlet_reactant_fraction: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="", description="Outlet reactant mole fraction"),
    ] = 1.0
    inlet_reactant_fraction: Annotated[
        float,
        M(type=T.CONTROLLED, unit="", description="Inlet reactant mole fraction"),
    ] = 1.0
    inlet_molar_flow_rate: Annotated[
        float,
        M(type=T.CONTROLLED, unit="mol/s", description="Inlet molar flow rate"),
    ] = 1.0
    liquid_holdup_mol: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol", description="Liquid holdup"),
    ] = 1.0
    first_order_rate_constant: Annotated[
        float,
        M(type=T.CONSTANT, unit="1/s", description="First-order consumption constant"),
    ] = 0.1

    @staticmethod
    @override
    def calculate_algebraic_values(
        y: FloatArray,
        u: FloatArray,
        k: FloatArray,
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
        algebraic_size: int,
    ) -> FloatArray:
        del u, k, u_map, k_map
        algebraic: FloatArray = np.zeros(algebraic_size, dtype=np.float64)
        algebraic[algebraic_map["outlet_reactant_fraction"]] = float(y[y_map["reactant_fraction"]])
        return algebraic

    @staticmethod
    @override
    def differential_rhs(
        t: float,
        y: FloatArray,
        u: FloatArray,
        k: FloatArray,
        algebraic: FloatArray,
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
    ) -> FloatArray:
        del t, algebraic, algebraic_map
        x = float(y[y_map["reactant_fraction"]])
        x_in = float(u[u_map["inlet_reactant_fraction"]])
        inlet_flow = float(u[u_map["inlet_molar_flow_rate"]])
        holdup = float(k[k_map["liquid_holdup_mol"]])
        rate_constant = float(k[k_map["first_order_rate_constant"]])

        tau_inverse = inlet_flow / holdup
        dx_dt = tau_inverse * (x_in - x) - rate_constant * x

        rhs: FloatArray = np.zeros_like(y)
        rhs[y_map["reactant_fraction"]] = dx_dt
        return rhs


def _attach_default_solver_options(process_model: ProcessModel) -> None:
    dummy_system = SimpleNamespace(
        solver_options={"method": "RK45", "rtol": 1e-8, "atol": 1e-10},
        use_numba=False,
        numba_options={},
    )
    process_model.attach_system(cast(Any, dummy_system))


def _build_two_tank_network() -> tuple[ConnectionNetwork, ProcessBinding, ProcessBinding]:
    network = ConnectionNetwork()
    network.add_boundary_source("feed")
    network.add_process("tank_a", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_process("tank_b", inlet_ports=("inlet",), outlet_ports=("outlet",))
    network.add_boundary_sink("product")
    network.connect("feed", "tank_a.inlet")
    network.connect("tank_a.outlet", "tank_b.inlet")
    network.connect("tank_b.outlet", "product")
    compiled = network.compile()
    return network, compiled.process_bindings["tank_a"], compiled.process_bindings["tank_b"]


def _constant_hydraulic_result(*, edge_flow: float) -> HydraulicSolveResult:
    return HydraulicSolveResult(
        converged=True,
        iterations=1,
        residual_norm=1.0e-10,
        solution_vector=np.asarray([edge_flow, 5.0], dtype=np.float64),
        unknowns={"flow": edge_flow, "pressure": 5.0},
        unknown_index_map={"flow": 0, "pressure": 1},
        residual_index_map={"balance": 0, "ref": 1},
    )


@dataclass
class _TankSubsystemRuntime:
    descriptor: SubsystemRuntimeDescriptor
    model: FirstOrderLiquidTankModel
    binding: ProcessBinding
    pressure_pa: float
    temperature_k: float
    outlet_flow_mol_per_s: float
    inlet_reactant_fraction: float
    inlet_molar_flow_rate: float
    outlet_state: MaterialState = field(init=False)
    subsystem_handle: Subsystem | None = None

    def __post_init__(self) -> None:
        self.outlet_state = _material_state_from_reactant_fraction(
            float(self.model.reactant_fraction),
            pressure_pa=self.pressure_pa,
            temperature_k=self.temperature_k,
        )

    def run_sensor_phase(self) -> None:
        return

    def run_calculation_phase(self) -> None:
        return

    def run_controller_phase(self) -> None:
        return

    def run_process_phase(self, duration: float) -> None:
        outlet_state_for_binding = _material_state_from_reactant_fraction(
            float(self.model.reactant_fraction),
            pressure_pa=self.pressure_pa,
            temperature_k=self.temperature_k,
        )
        self.binding.bind_inlets({"inlet": self.inlet_molar_flow_rate})
        self.binding.bind_outlets(
            {
                "outlet": {
                    "role": "outlet",
                    "flow": self.outlet_flow_mol_per_s,
                    "composition": outlet_state_for_binding.mole_fractions,
                }
            }
        )
        outlet_binding = self.binding.get_outlet("outlet")
        self.model.inlet_reactant_fraction = self.inlet_reactant_fraction
        self.model.inlet_molar_flow_rate = cast(float, outlet_binding["outlet_flow"])
        self.model.step(duration)
        self.outlet_state = _material_state_from_reactant_fraction(
            float(self.model.reactant_fraction),
            pressure_pa=self.pressure_pa,
            temperature_k=self.temperature_k,
        )

    def snapshot_published_measurements(self) -> dict[str, float]:
        return {
            f"{self.descriptor.descriptor_id}/reactant_fraction": float(
                self.model.reactant_fraction
            )
        }


def _material_state_from_reactant_fraction(
    reactant_fraction: float,
    *,
    pressure_pa: float,
    temperature_k: float,
) -> MaterialState:
    bounded = min(max(reactant_fraction, 0.0), 1.0)
    return MaterialState(
        pressure=pressure_pa,
        temperature=temperature_k,
        mole_fractions=(bounded, 1.0 - bounded),
    )


def _port_condition_from_state(
    state: MaterialState,
    *,
    through_molar_flow_rate: float,
    macro_step_time_s: float,
) -> PortCondition:
    return PortCondition(
        state=state,
        through_molar_flow_rate=through_molar_flow_rate,
        macro_step_time_s=macro_step_time_s,
    )


def _simulate_connection_layer(
    config: TankCascadeConfig,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    if getattr(config, "use_subsystem_abstraction", False):
        return _simulate_subsystem_path(config)
    n_steps = int(round(config.horizon_s / config.dt_s))
    times: FloatArray = np.linspace(0.0, config.horizon_s, n_steps + 1, dtype=np.float64)

    tank_a = FirstOrderLiquidTankModel(
        reactant_fraction=config.feed_reactant_fraction,
        inlet_reactant_fraction=config.feed_reactant_fraction,
        inlet_molar_flow_rate=config.flow_rate_mol_per_s,
        liquid_holdup_mol=config.tank_a_holdup_mol,
        first_order_rate_constant=config.tank_a_rate_constant_per_s,
    )
    tank_b = FirstOrderLiquidTankModel(
        reactant_fraction=config.feed_reactant_fraction,
        inlet_reactant_fraction=config.feed_reactant_fraction,
        inlet_molar_flow_rate=config.flow_rate_mol_per_s,
        liquid_holdup_mol=config.tank_b_holdup_mol,
        first_order_rate_constant=config.tank_b_rate_constant_per_s,
    )

    _attach_default_solver_options(tank_a)
    _attach_default_solver_options(tank_b)
    _, binding_a, binding_b = _build_two_tank_network()

    feed_state = _material_state_from_reactant_fraction(
        config.feed_reactant_fraction,
        pressure_pa=config.pressure_pa,
        temperature_k=config.temperature_k,
    )
    previous_b_inlet_state = feed_state

    tank_a_trajectory: FloatArray = np.zeros(n_steps + 1, dtype=np.float64)
    tank_b_trajectory: FloatArray = np.zeros(n_steps + 1, dtype=np.float64)
    tank_a_trajectory[0] = tank_a.reactant_fraction
    tank_b_trajectory[0] = tank_b.reactant_fraction

    for step in range(1, n_steps + 1):
        current_time = float(times[step - 1])

        tank_a_outlet_state = _material_state_from_reactant_fraction(
            float(tank_a.reactant_fraction),
            pressure_pa=config.pressure_pa,
            temperature_k=config.temperature_k,
        )
        tank_a_outlet_condition = _port_condition_from_state(
            tank_a_outlet_state,
            through_molar_flow_rate=config.flow_rate_mol_per_s,
            macro_step_time_s=current_time,
        )
        binding_a.bind_inlets({"inlet": config.flow_rate_mol_per_s})
        binding_a.bind_outlets(
            {
                "outlet": {
                    "role": "outlet",
                    "flow": config.flow_rate_mol_per_s,
                    "composition": tank_a_outlet_state.mole_fractions,
                }
            }
        )
        tank_a_outlet_binding = binding_a.get_outlet("outlet")
        tank_a.inlet_reactant_fraction = float(feed_state.mole_fractions[0])
        tank_a.inlet_molar_flow_rate = cast(float, tank_a_outlet_binding["outlet_flow"])
        tank_a.step(config.dt_s)

        mixed_b_inlet = mix_junction_state(
            incoming_port_conditions={"edge_a_to_b": tank_a_outlet_condition},
            previous_state=previous_b_inlet_state,
        )
        previous_b_inlet_state = mixed_b_inlet.state

        tank_b_outlet_state = _material_state_from_reactant_fraction(
            float(tank_b.reactant_fraction),
            pressure_pa=config.pressure_pa,
            temperature_k=config.temperature_k,
        )
        binding_b.bind_inlets({"inlet": mixed_b_inlet.total_incoming_flow_rate})
        binding_b.bind_outlets(
            {
                "outlet": {
                    "role": "outlet",
                    "flow": config.flow_rate_mol_per_s,
                    "composition": tank_b_outlet_state.mole_fractions,
                }
            }
        )
        tank_b_outlet_binding = binding_b.get_outlet("outlet")
        tank_b.inlet_reactant_fraction = float(mixed_b_inlet.state.mole_fractions[0])
        tank_b.inlet_molar_flow_rate = cast(float, tank_b_outlet_binding["outlet_flow"])
        tank_b.step(config.dt_s)

        tank_a_trajectory[step] = float(tank_a.reactant_fraction)
        tank_b_trajectory[step] = float(tank_b.reactant_fraction)

    return times, tank_a_trajectory, tank_b_trajectory


def _simulate_subsystem_path(
    config: TankCascadeConfig,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    n_steps = int(round(config.horizon_s / config.dt_s))
    times: FloatArray = np.linspace(0.0, config.horizon_s, n_steps + 1, dtype=np.float64)

    tank_a_model = FirstOrderLiquidTankModel(
        reactant_fraction=config.feed_reactant_fraction,
        inlet_reactant_fraction=config.feed_reactant_fraction,
        inlet_molar_flow_rate=config.flow_rate_mol_per_s,
        liquid_holdup_mol=config.tank_a_holdup_mol,
        first_order_rate_constant=config.tank_a_rate_constant_per_s,
    )
    tank_b_model = FirstOrderLiquidTankModel(
        reactant_fraction=config.feed_reactant_fraction,
        inlet_reactant_fraction=config.feed_reactant_fraction,
        inlet_molar_flow_rate=config.flow_rate_mol_per_s,
        liquid_holdup_mol=config.tank_b_holdup_mol,
        first_order_rate_constant=config.tank_b_rate_constant_per_s,
    )
    _attach_default_solver_options(tank_a_model)
    _attach_default_solver_options(tank_b_model)

    network, binding_a, binding_b = _build_two_tank_network()
    feed_state = _material_state_from_reactant_fraction(
        config.feed_reactant_fraction,
        pressure_pa=config.pressure_pa,
        temperature_k=config.temperature_k,
    )
    feed_reactant_fraction = float(feed_state.mole_fractions[0])

    tank_a_runtime = _TankSubsystemRuntime(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="tank_a",
            process_id="tank_a",
            inlet_ports=("inlet",),
            outlet_ports=("outlet",),
            publication_map={"tank_a/reactant_fraction": float(tank_a_model.reactant_fraction)},
        ),
        model=tank_a_model,
        binding=binding_a,
        pressure_pa=config.pressure_pa,
        temperature_k=config.temperature_k,
        outlet_flow_mol_per_s=config.flow_rate_mol_per_s,
        inlet_reactant_fraction=feed_reactant_fraction,
        inlet_molar_flow_rate=config.flow_rate_mol_per_s,
    )
    tank_b_runtime = _TankSubsystemRuntime(
        descriptor=SubsystemRuntimeDescriptor(
            descriptor_id="tank_b",
            process_id="tank_b",
            inlet_ports=("inlet",),
            outlet_ports=("outlet",),
            publication_map={"tank_b/reactant_fraction": float(tank_b_model.reactant_fraction)},
        ),
        model=tank_b_model,
        binding=binding_b,
        pressure_pa=config.pressure_pa,
        temperature_k=config.temperature_k,
        outlet_flow_mol_per_s=config.flow_rate_mol_per_s,
        inlet_reactant_fraction=feed_reactant_fraction,
        inlet_molar_flow_rate=config.flow_rate_mol_per_s,
    )

    coupling_state: dict[str, MaterialState] = {"previous_b_inlet": feed_state}

    runtime_orchestrator = ConnectionRuntimeOrchestrator(
        hydraulic_solve_step=(
            lambda *, network, macro_step_time_s: _constant_hydraulic_result(
                edge_flow=config.flow_rate_mol_per_s
            )
        ),
        transport_and_mixing_step=(
            lambda *, network, hydraulic_result, macro_step_time_s: TransportAndMixingUpdate(
                transport_results={}
            )
        ),
        boundary_propagation_step=(
            lambda *,
            network,
            hydraulic_result,
            transport_and_mixing_update,
            macro_step_time_s: _update_coupling_state(
                config=config,
                macro_step_time_s=macro_step_time_s,
                tank_a_runtime=tank_a_runtime,
                tank_b_runtime=tank_b_runtime,
                coupling_state=coupling_state,
            )
        ),
    )

    orchestrator = ConnectedPlantOrchestrator(
        subsystems=(tank_a_runtime, tank_b_runtime),
        network=network,
        runtime_orchestrator=runtime_orchestrator,
        phase_hooks=ConnectedPlantPhaseHooks(),
    )

    tank_a_trajectory: FloatArray = np.zeros(n_steps + 1, dtype=np.float64)
    tank_b_trajectory: FloatArray = np.zeros(n_steps + 1, dtype=np.float64)
    tank_a_trajectory[0] = tank_a_model.reactant_fraction
    tank_b_trajectory[0] = tank_b_model.reactant_fraction

    for step in range(1, n_steps + 1):
        _ = orchestrator.step(macro_step_time_s=config.dt_s)
        tank_a_trajectory[step] = float(tank_a_model.reactant_fraction)
        tank_b_trajectory[step] = float(tank_b_model.reactant_fraction)

    return times, tank_a_trajectory, tank_b_trajectory


def _update_coupling_state(
    *,
    config: TankCascadeConfig,
    macro_step_time_s: float,
    tank_a_runtime: _TankSubsystemRuntime,
    tank_b_runtime: _TankSubsystemRuntime,
    coupling_state: dict[str, MaterialState],
) -> dict[str, PortCondition]:
    tank_a_outlet_condition = _port_condition_from_state(
        tank_a_runtime.outlet_state,
        through_molar_flow_rate=config.flow_rate_mol_per_s,
        macro_step_time_s=macro_step_time_s,
    )
    mixed_b_inlet = mix_junction_state(
        incoming_port_conditions={"edge_a_to_b": tank_a_outlet_condition},
        previous_state=coupling_state["previous_b_inlet"],
    )
    coupling_state["previous_b_inlet"] = mixed_b_inlet.state

    tank_b_runtime.inlet_reactant_fraction = float(mixed_b_inlet.state.mole_fractions[0])
    tank_b_runtime.inlet_molar_flow_rate = mixed_b_inlet.total_incoming_flow_rate

    return {
        "tank_a.outlet": tank_a_outlet_condition,
        "tank_b.inlet": _port_condition_from_state(
            mixed_b_inlet.state,
            through_molar_flow_rate=mixed_b_inlet.total_incoming_flow_rate,
            macro_step_time_s=macro_step_time_s,
        ),
    }


def _ad_hoc_coupled_rhs(
    t: float,
    y: FloatArray,
    *args: object,
) -> FloatArray:
    del t
    config = cast(TankCascadeConfig, args[0])
    x_a = float(y[0])
    x_b = float(y[1])

    tau_a_inverse = config.flow_rate_mol_per_s / config.tank_a_holdup_mol
    tau_b_inverse = config.flow_rate_mol_per_s / config.tank_b_holdup_mol

    dx_a_dt = (
        tau_a_inverse * (config.feed_reactant_fraction - x_a)
        - config.tank_a_rate_constant_per_s * x_a
    )
    dx_b_dt = tau_b_inverse * (x_a - x_b) - config.tank_b_rate_constant_per_s * x_b
    return np.array((dx_a_dt, dx_b_dt), dtype=np.float64)


def _simulate_ad_hoc_reference(
    config: TankCascadeConfig, times: FloatArray
) -> tuple[FloatArray, FloatArray]:
    y0: FloatArray = np.array(
        (config.feed_reactant_fraction, config.feed_reactant_fraction), dtype=np.float64
    )
    solution = solve_ivp(
        fun=_ad_hoc_coupled_rhs,
        t_span=(0.0, config.horizon_s),
        y0=y0,
        t_eval=times,
        args=(config,),
        method="RK45",
        rtol=1e-10,
        atol=1e-12,
    )
    if not solution.success:
        raise RuntimeError("ad hoc coupled RHS integration failed")
    return solution.y[0], solution.y[1]


def _first_index_at_or_below(values: FloatArray, threshold: float) -> int:
    crossings = np.flatnonzero(values <= threshold)
    if crossings.size == 0:
        return int(values.size - 1)
    return int(crossings[0])


def run_demo(config: TankCascadeConfig | None = None) -> TwoTankComparisonResult:
    cfg = TankCascadeConfig() if config is None else config

    times, tank_a_connection, tank_b_connection = _simulate_connection_layer(cfg)
    tank_a_reference, tank_b_reference = _simulate_ad_hoc_reference(cfg, times)

    max_abs_error_a = float(np.max(np.abs(tank_a_connection - tank_a_reference)))
    max_abs_error_b = float(np.max(np.abs(tank_b_connection - tank_b_reference)))
    rmse_b = float(np.sqrt(np.mean((tank_b_connection - tank_b_reference) ** 2)))

    threshold = cfg.feed_reactant_fraction * 0.95
    a_cross = _first_index_at_or_below(tank_a_connection, threshold)
    b_cross = _first_index_at_or_below(tank_b_connection, threshold)

    monotonic_decay_a = bool(np.all(np.diff(tank_a_connection) <= 1.0e-12))
    monotonic_decay_b = bool(np.all(np.diff(tank_b_connection) <= 1.0e-12))
    b_not_below_a_fraction = float(np.mean(tank_b_connection >= (tank_a_connection - 1.0e-9)))

    return TwoTankComparisonResult(
        times_s=tuple(times.tolist()),
        tank_a_connection=tuple(tank_a_connection.tolist()),
        tank_b_connection=tuple(tank_b_connection.tolist()),
        tank_a_reference=tuple(tank_a_reference.tolist()),
        tank_b_reference=tuple(tank_b_reference.tolist()),
        max_abs_error_a=max_abs_error_a,
        max_abs_error_b=max_abs_error_b,
        rmse_b=rmse_b,
        b_lag_steps=max(b_cross - a_cross, 0),
        monotonic_decay_a=monotonic_decay_a,
        monotonic_decay_b=monotonic_decay_b,
        b_not_below_a_fraction=b_not_below_a_fraction,
    )


def plot_comparison(
    result: TwoTankComparisonResult,
    *,
    output_path: str | None = None,
    show: bool = True,
) -> str | None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "Plotting requires matplotlib. Install it with 'uv add --dev matplotlib' "
            "or run without --plot."
        ) from exc

    times = np.asarray(result.times_s, dtype=np.float64)
    tank_a_connection = np.asarray(result.tank_a_connection, dtype=np.float64)
    tank_a_reference = np.asarray(result.tank_a_reference, dtype=np.float64)
    tank_b_connection = np.asarray(result.tank_b_connection, dtype=np.float64)
    tank_b_reference = np.asarray(result.tank_b_reference, dtype=np.float64)

    figure, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(9.5, 7.0), sharex=True)

    ax_a.plot(times, tank_a_connection, label="Tank A (connection)", linewidth=2.0)
    ax_a.plot(times, tank_a_reference, label="Tank A (ad hoc)", linewidth=1.6, linestyle="--")
    ax_a.set_ylabel("Reactant fraction")
    ax_a.set_title("Tank A: connection layer vs ad hoc RHS")
    ax_a.grid(True, alpha=0.25)
    ax_a.legend(loc="best")

    ax_b.plot(times, tank_b_connection, label="Tank B (connection)", linewidth=2.0)
    ax_b.plot(times, tank_b_reference, label="Tank B (ad hoc)", linewidth=1.6, linestyle="--")
    ax_b.set_xlabel("Time [s]")
    ax_b.set_ylabel("Reactant fraction")
    ax_b.set_title("Tank B: connection layer vs ad hoc RHS")
    ax_b.grid(True, alpha=0.25)
    ax_b.legend(loc="best")

    figure.tight_layout()

    saved_path: str | None = None
    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(target, dpi=160)
        saved_path = str(target)

    if show:
        plt.show()
    else:
        plt.close(figure)

    return saved_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two-tank connection-layer simulation against an ad hoc coupled RHS model."
        )
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Render comparison plots for Tank A and Tank B trajectories.",
    )
    parser.add_argument(
        "--plot-file",
        default=None,
        help="Optional path to save the plot image (for example: two_tank_comparison.png).",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open a plot window (useful with --plot-file in headless environments).",
    )
    args = parser.parse_args()

    result = run_demo()
    print("TWO-TANK CONNECTION VS AD HOC COMPARISON")
    print("time_s,tank_a_conn,tank_a_ref,tank_b_conn,tank_b_ref")
    for index, time_s in enumerate(result.times_s):
        print(
            f"{time_s:.2f},{result.tank_a_connection[index]:.8f},{result.tank_a_reference[index]:.8f},{result.tank_b_connection[index]:.8f},{result.tank_b_reference[index]:.8f}"
        )
    print(f"max_abs_error_a={result.max_abs_error_a:.6e}")
    print(f"max_abs_error_b={result.max_abs_error_b:.6e}")
    print(f"rmse_b={result.rmse_b:.6e}")
    print(f"b_lag_steps={result.b_lag_steps}")
    print(f"monotonic_decay_a={result.monotonic_decay_a}")
    print(f"monotonic_decay_b={result.monotonic_decay_b}")
    print(f"b_not_below_a_fraction={result.b_not_below_a_fraction:.3f}")

    should_plot = args.plot or args.plot_file is not None
    if should_plot:
        saved_path = plot_comparison(
            result,
            output_path=cast(str | None, args.plot_file),
            show=not bool(args.no_show),
        )
        if saved_path is not None:
            print(f"saved_plot={saved_path}")


if __name__ == "__main__":
    main()
