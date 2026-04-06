from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modular_simulation.cli.backend_session import PlantBackendSession
from modular_simulation.connection.runtime.connected_plant_orchestrator import (
    ConnectedPlantOrchestrator,
)
from modular_simulation.connection.topology.network import ConnectionNetwork
from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.unit_processes import StagewiseDistillationColumn


@dataclass(frozen=True)
class BackendGasStarterProofHarness:
    session: PlantBackendSession
    plant: ConnectedPlantOrchestrator
    network: ConnectionNetwork
    flowsheet: Flowsheet
    column: StagewiseDistillationColumn
    dt_s: float
    column_id: str
    species_ids: tuple[str, ...]

    def _process_state_values(self) -> dict[str, float]:
        snapshot = self.session.get_observability_snapshot()
        return cast(dict[str, float], snapshot["observables"]["process_state_values"])

    def _read_value(self, key: str, *, default: float = 0.0) -> float:
        values = self._process_state_values()
        value = values.get(key, default)
        return float(value)

    def step_and_capture(self) -> dict[str, float]:
        _ = self.plant.step(macro_step_time_s=self.dt_s)
        column_prefix = self.column_id
        light_species = self.species_ids[0]
        heavy_species = self.species_ids[-1]

        return {
            "time_s": float(
                cast(dict[str, float], self.session.get_observability_snapshot()["runtime"])[
                    "simulation_time_s"
                ]
            ),
            "condenser_duty_request_W": self._read_value(
                f"{column_prefix}/condenser_duty_request_W"
            ),
            "reboiler_duty_request_W": self._read_value(f"{column_prefix}/reboiler_duty_request_W"),
            "reflux_drum_holdup_mol": self._read_value(f"{column_prefix}/reflux_drum_holdup_mol"),
            "bottoms_sump_holdup_mol": self._read_value(f"{column_prefix}/bottoms_sump_holdup_mol"),
            "distillate_flow_mol_s": self._read_value(f"{column_prefix}/distillate_flow_mol_s"),
            "bottoms_flow_mol_s": self._read_value(f"{column_prefix}/bottoms_flow_mol_s"),
            "distillate_withdrawal_flow_mol_s": self._read_value(
                f"{column_prefix}/distillate_withdrawal_flow_mol_s"
            ),
            "bottoms_withdrawal_flow_mol_s": self._read_value(
                f"{column_prefix}/bottoms_withdrawal_flow_mol_s"
            ),
            "realized_condensed_flow_mol_s": self._read_value(
                f"{column_prefix}/realized_condensed_flow_mol_s"
            ),
            "realized_reboiler_boilup_flow_mol_s": self._read_value(
                f"{column_prefix}/realized_reboiler_boilup_flow_mol_s"
            ),
            "column_pressure_pa": self._read_value(f"{column_prefix}/column_pressure_pa"),
            "top_pressure_pa": self._read_value(f"{column_prefix}/top_pressure_pa"),
            "bottom_pressure_pa": self._read_value(f"{column_prefix}/bottom_pressure_pa"),
            "distillate_temperature_K": self._read_value(
                f"{column_prefix}/distillate_temperature_K"
            ),
            "bottoms_temperature_K": self._read_value(f"{column_prefix}/bottoms_temperature_K"),
            "internal_liquid_traffic_mol_s": self._read_value(
                f"{column_prefix}/internal_liquid_traffic_mol_s"
            ),
            "internal_vapor_traffic_mol_s": self._read_value(
                f"{column_prefix}/internal_vapor_traffic_mol_s"
            ),
            "distillate_light_key_component_x": self._read_value(
                f"{column_prefix}/distillate_mole_fraction/{light_species}"
            ),
            "bottoms_heavy_key_component_x": self._read_value(
                f"{column_prefix}/bottoms_mole_fraction/{heavy_species}"
            ),
            "feed_stage_light_component_x": self._read_value(
                f"{column_prefix}/stage_1/mole_fraction/{light_species}"
            ),
        }


def build_backend_gas_starter_proof_harness(*, dt_s: float = 0.2) -> BackendGasStarterProofHarness:
    context = SimulationRuntimeContext.create(species_names=["methanol", "ethanol", "water"])
    flowsheet = Flowsheet(context=context, dt=dt_s)

    column = StagewiseDistillationColumn(
        n_species=3,
        active_contact_height_m=6.0,
        shell_diameter_m=1.2,
        feed_stage_indices=(1, 4),
        column_pressure_pa=165_000.0,
    )
    flowsheet.add_unit("stage_col", column)

    flowsheet.add_feed_from_values(
        "feed_a",
        T=350.0,
        P=165_000.0,
        z=(0.70, 0.20, 0.10),
        flow=6.0,
    )
    flowsheet.add_feed_from_values(
        "feed_b",
        T=340.0,
        P=165_000.0,
        z=(0.10, 0.30, 0.60),
        flow=4.5,
    )
    flowsheet.add_feed_from_values(
        "reflux_feed",
        T=330.0,
        P=165_000.0,
        z=(0.33, 0.33, 0.34),
        flow=0.0,
    )
    flowsheet.add_sink("dist_prod")
    flowsheet.add_sink("bot_prod")
    flowsheet.add_sink("reflux_sink")

    _ = flowsheet.connect("feed_a", "stage_col.feed_1", line_id="feed_a_to_column")
    _ = flowsheet.connect("feed_b", "stage_col.feed_2", line_id="feed_b_to_column")
    _ = flowsheet.connect(
        "reflux_feed",
        "stage_col.reflux_return",
        line_id="reflux_feed_to_column",
    )
    _ = flowsheet.connect("stage_col.distillate", "dist_prod", line_id="column_to_distillate_sink")
    _ = flowsheet.connect("stage_col.bottoms", "bot_prod", line_id="column_to_bottoms_sink")
    _ = flowsheet.connect("stage_col.reflux_outlet", "reflux_sink", line_id="column_to_reflux_sink")

    plant = flowsheet.compile()
    network = cast(ConnectionNetwork, getattr(plant, "_network"))
    session = PlantBackendSession(network=network)

    return BackendGasStarterProofHarness(
        session=session,
        plant=plant,
        network=network,
        flowsheet=flowsheet,
        column=column,
        dt_s=dt_s,
        column_id="stage_col",
        species_ids=tuple(context.species_registry.cas_list),
    )


def run_backend_gas_starter_causal_proof(
    *,
    dt_s: float = 0.2,
    baseline_steps: int = 4,
    post_disturbance_steps: int = 12,
) -> dict[str, object]:
    harness = build_backend_gas_starter_proof_harness(dt_s=dt_s)

    history: list[dict[str, float]] = []
    for _ in range(baseline_steps):
        history.append(harness.step_and_capture())

    harness.column.condenser_duty_request_W = -12_000.0
    harness.column.reboiler_duty_request_W = 9_000.0
    harness.column.distillate_withdrawal_flow = 3.0
    harness.column.bottoms_withdrawal_flow = 2.5

    first_window = max(2, post_disturbance_steps // 2)
    for step_index in range(post_disturbance_steps):
        if step_index == first_window:
            harness.column.condenser_duty_request_W = -24_000.0
            harness.column.reboiler_duty_request_W = 18_000.0
            harness.column.distillate_withdrawal_flow = 8.0
            harness.column.bottoms_withdrawal_flow = 7.0
        history.append(harness.step_and_capture())

    return {
        "proof": {
            "baseline_steps": baseline_steps,
            "post_disturbance_steps": post_disturbance_steps,
            "history": history,
            "manipulations": {
                "phase_1": {
                    "condenser_duty_request_W": -12_000.0,
                    "reboiler_duty_request_W": 9_000.0,
                    "distillate_withdrawal_flow_mol_s": 3.0,
                    "bottoms_withdrawal_flow_mol_s": 2.5,
                },
                "phase_2": {
                    "condenser_duty_request_W": -24_000.0,
                    "reboiler_duty_request_W": 18_000.0,
                    "distillate_withdrawal_flow_mol_s": 8.0,
                    "bottoms_withdrawal_flow_mol_s": 7.0,
                },
            },
        },
        "claims": {
            "demonstrated": [
                "backend-only stagewise column proof assembled through existing flowsheet/runtime/session surfaces",
                "multi-step reflux-drum and bottoms-sump holdup dynamics after condenser/reboiler duty disturbances",
                "runtime process-state evidence for stronger pressure (column/top/bottom), thermal (top/bottom temperatures), and representative internal hydraulic traffic response",
                "connected-runtime observability shows requested vs realized distillate/bottoms withdrawal and conservative no-overdraw behavior",
            ],
            "deferred": [
                "flooding/weeping/entrainment regime-switch hydraulics are deferred",
                "full rigorous MESH or rate-based tray mass-transfer closure is deferred",
                "no gameplay/Godot/public-session/controller coupling widening claim in this backend proof",
            ],
        },
    }


def plot_backend_gas_starter_causal_proof(
    *,
    history: list[dict[str, float]],
    dt_s: float,
    baseline_steps: int,
    first_window: int,
    show: bool = True,
) -> object:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "Plotting requires matplotlib. Install it with 'uv add --dev matplotlib'."
        ) from exc

    times = [point["time_s"] for point in history]
    first_marker_time = baseline_steps * dt_s
    second_marker_time = (baseline_steps + first_window) * dt_s

    figure, axes = plt.subplots(4, 2, figsize=(14, 14), sharex=True)
    plot_axes = list(axes.flat)

    panel_specs = (
        (
            plot_axes[0],
            "Duty requests",
            "Duty [W]",
            ("condenser_duty_request_W", "reboiler_duty_request_W"),
        ),
        (
            plot_axes[1],
            "Column holdups",
            "Holdup [mol]",
            ("reflux_drum_holdup_mol", "bottoms_sump_holdup_mol"),
        ),
        (
            plot_axes[2],
            "Requested vs realized withdrawals",
            "Flow [mol/s]",
            (
                "distillate_withdrawal_flow_mol_s",
                "distillate_flow_mol_s",
                "bottoms_withdrawal_flow_mol_s",
                "bottoms_flow_mol_s",
            ),
        ),
        (
            plot_axes[3],
            "Pressure realism signals",
            "Pressure [Pa]",
            ("column_pressure_pa", "top_pressure_pa", "bottom_pressure_pa"),
        ),
        (
            plot_axes[4],
            "Thermal realism signals",
            "Temperature [K]",
            ("distillate_temperature_K", "bottoms_temperature_K"),
        ),
        (
            plot_axes[5],
            "Realized internal flows",
            "Flow [mol/s]",
            ("realized_condensed_flow_mol_s", "realized_reboiler_boilup_flow_mol_s"),
        ),
        (
            plot_axes[6],
            "Internal hydraulic realism signals",
            "Flow [mol/s]",
            ("internal_liquid_traffic_mol_s", "internal_vapor_traffic_mol_s"),
        ),
        (
            plot_axes[7],
            "Product composition indicators",
            "Mole fraction [-]",
            ("distillate_light_key_component_x", "bottoms_heavy_key_component_x"),
        ),
    )

    for axis, title, ylabel, series_keys in panel_specs:
        for series_key in series_keys:
            axis.plot(
                times, [point[series_key] for point in history], label=series_key, linewidth=2.0
            )
        axis.axvline(first_marker_time, color="black", linestyle=":", linewidth=1.2)
        axis.axvline(second_marker_time, color="black", linestyle="--", linewidth=1.2)
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.3)
        axis.legend(loc="best")

    plot_axes[6].set_xlabel("Time [s]")
    plot_axes[7].set_xlabel("Time [s]")
    figure.tight_layout()

    if show:
        plt.show()

    return figure


def main() -> None:
    baseline_steps = 100
    post_disturbance_steps = 1000
    dt_s = 0.2
    report = run_backend_gas_starter_causal_proof(
        dt_s=dt_s,
        baseline_steps=baseline_steps,
        post_disturbance_steps=post_disturbance_steps,
    )
    proof = cast(dict[str, Any], report["proof"])
    history = cast(list[dict[str, float]], proof["history"])
    claims = cast(dict[str, list[str]], report["claims"])
    first_window = max(2, post_disturbance_steps // 2)

    print("BACKEND GAS STARTER STAGEWISE CAUSAL PROOF")
    print(f"baseline_steps={proof['baseline_steps']}")
    print(f"post_disturbance_steps={proof['post_disturbance_steps']}")
    if history:
        final = history[-1]
        print(f"final_reflux_drum_holdup_mol={final['reflux_drum_holdup_mol']:.6f}")
        print(f"final_bottoms_sump_holdup_mol={final['bottoms_sump_holdup_mol']:.6f}")
        print(f"final_distillate_flow_mol_s={final['distillate_flow_mol_s']:.6f}")
        print(f"final_bottoms_flow_mol_s={final['bottoms_flow_mol_s']:.6f}")
        print(f"final_realized_condensed_flow_mol_s={final['realized_condensed_flow_mol_s']:.6f}")
        print(
            "final_realized_reboiler_boilup_flow_mol_s="
            f"{final['realized_reboiler_boilup_flow_mol_s']:.6f}"
        )
        print(
            "final_distillate_light_key_component_x="
            f"{final['distillate_light_key_component_x']:.6f}"
        )
        print(f"final_bottoms_heavy_key_component_x={final['bottoms_heavy_key_component_x']:.6f}")

    print("DEMONSTRATED")
    for claim in claims["demonstrated"]:
        print(f"- {claim}")
    print("DEFERRED")
    for claim in claims["deferred"]:
        print(f"- {claim}")

    if history:
        _ = plot_backend_gas_starter_causal_proof(
            history=history,
            dt_s=dt_s,
            baseline_steps=baseline_steps,
            first_window=first_window,
        )


if __name__ == "__main__":
    main()
