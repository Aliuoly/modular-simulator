from __future__ import annotations

from pathlib import Path
import sys
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import examples.dynamic_simulation_demos.backend_gas_starter_causal_proof as proof_module
from examples.dynamic_simulation_demos.backend_gas_starter_causal_proof import (
    build_backend_gas_starter_proof_harness,
    plot_backend_gas_starter_causal_proof,
    run_backend_gas_starter_causal_proof,
)


def _count_nonzero_deltas(values: list[float], *, atol: float = 1.0e-9) -> int:
    return sum(1 for idx in range(1, len(values)) if abs(values[idx] - values[idx - 1]) > atol)


def test_stagewise_backend_proof_assembles_on_current_substrate_surfaces() -> None:
    harness = build_backend_gas_starter_proof_harness(dt_s=0.2)

    topology = harness.session.get_topology()
    assert topology["graph_revision"] is not None
    edge_ids = {edge["edge_id"] for edge in topology["topology"]["edges"]}
    assert {
        "feed_a_to_column",
        "feed_b_to_column",
        "reflux_feed_to_column",
        "column_to_distillate_sink",
        "column_to_bottoms_sink",
        "column_to_reflux_sink",
    }.issubset(edge_ids)

    _ = harness.step_and_capture()
    snapshot = harness.session.get_observability_snapshot()
    process_state_values = snapshot["observables"]["process_state_values"]
    prefix = harness.column_id
    for key in (
        f"{prefix}/reflux_drum_holdup_mol",
        f"{prefix}/bottoms_sump_holdup_mol",
        f"{prefix}/distillate_flow_mol_s",
        f"{prefix}/bottoms_flow_mol_s",
        f"{prefix}/realized_condensed_flow_mol_s",
        f"{prefix}/realized_reboiler_boilup_flow_mol_s",
    ):
        assert key in process_state_values


def test_stagewise_duty_disturbances_drive_multi_step_top_bottom_holdup_and_composition_response() -> (
    None
):
    report = run_backend_gas_starter_causal_proof(
        dt_s=0.2,
        baseline_steps=3,
        post_disturbance_steps=10,
    )

    proof = report["proof"]
    history = proof["history"]
    baseline_steps = proof["baseline_steps"]

    assert len(history) >= baseline_steps + 8
    post_history = history[baseline_steps:]
    assert len(post_history) >= 8

    phase_split = len(post_history) // 2
    first_phase = post_history[:phase_split]
    second_phase = post_history[phase_split:]

    for phase in (first_phase, second_phase):
        assert phase
        phase_series = (
            [point["reflux_drum_holdup_mol"] for point in phase],
            [point["bottoms_sump_holdup_mol"] for point in phase],
            [point["distillate_light_key_component_x"] for point in phase],
        )
        assert max(_count_nonzero_deltas(series) for series in phase_series) >= 2

    realized_condensed_series = [point["realized_condensed_flow_mol_s"] for point in post_history]
    realized_boilup_series = [
        point["realized_reboiler_boilup_flow_mol_s"] for point in post_history
    ]

    baseline_last = history[baseline_steps - 1]
    assert post_history[0]["realized_condensed_flow_mol_s"] != pytest.approx(
        baseline_last["realized_condensed_flow_mol_s"]
    )
    assert post_history[0]["realized_reboiler_boilup_flow_mol_s"] != pytest.approx(
        baseline_last["realized_reboiler_boilup_flow_mol_s"]
    )
    assert _count_nonzero_deltas(realized_condensed_series) >= 1
    assert _count_nonzero_deltas(realized_boilup_series) >= 1


def test_stagewise_proof_keeps_withdrawals_passive_while_duty_disturbances_drive_response() -> None:
    report = run_backend_gas_starter_causal_proof(
        dt_s=0.2,
        baseline_steps=3,
        post_disturbance_steps=10,
    )

    proof = report["proof"]
    history = proof["history"]
    baseline_steps = proof["baseline_steps"]

    assert "distillate_withdrawal_flow_mol_s" not in proof["manipulations"]["phase_1"]
    assert "bottoms_withdrawal_flow_mol_s" not in proof["manipulations"]["phase_1"]
    assert "distillate_withdrawal_flow_mol_s" not in proof["manipulations"]["phase_2"]
    assert "bottoms_withdrawal_flow_mol_s" not in proof["manipulations"]["phase_2"]

    post_history = history[baseline_steps:]
    distillate_withdrawal_series = [point["distillate_flow_mol_s"] for point in post_history]
    bottoms_withdrawal_series = [point["bottoms_flow_mol_s"] for point in post_history]

    assert all(value == pytest.approx(0.0) for value in distillate_withdrawal_series)
    assert all(value == pytest.approx(0.0) for value in bottoms_withdrawal_series)


def test_stagewise_proof_claims_remain_honest_and_name_q_over_lambda_limitation() -> None:
    report = run_backend_gas_starter_causal_proof(
        dt_s=0.2,
        baseline_steps=2,
        post_disturbance_steps=6,
    )

    claims = report["claims"]
    demonstrated = " ".join(claims["demonstrated"]).lower()
    deferred = " ".join(claims["deferred"]).lower()

    assert "prescribed bottoms draw" not in demonstrated
    assert "pressure control" not in demonstrated
    assert "thermosyphon" not in demonstrated
    assert "pump-loop" not in demonstrated
    assert "enthalpy" not in demonstrated

    assert "pressure control" in deferred
    assert "enthalpy" in deferred
    assert "thermosyphon" in deferred or "pump-loop" in deferred
    assert "q/lambda" in deferred
    assert "modularsimulator-9tr.5.2" in deferred
    assert "passive product-flow readouts" in demonstrated
    assert "passive product-withdrawal readouts" in demonstrated


def test_plotting_helper_renders_expected_panels_and_disturbance_markers() -> None:
    report = run_backend_gas_starter_causal_proof(
        dt_s=0.2,
        baseline_steps=3,
        post_disturbance_steps=10,
    )

    proof = report["proof"]
    history = proof["history"]
    first_window = max(2, int(proof["post_disturbance_steps"]) // 2)

    figure = plot_backend_gas_starter_causal_proof(
        history=history,
        dt_s=0.2,
        baseline_steps=int(proof["baseline_steps"]),
        first_window=first_window,
        show=False,
    )

    axes = figure.axes
    assert len(axes) == 6

    expected_ylabels = [
        "Duty [W]",
        "Holdup [mol]",
        "Flow [mol/s]",
        "Flow [mol/s]",
        "Mole fraction [-]",
        "Mole fraction [-]",
    ]
    expected_titles = [
        "Duty requests",
        "Column holdups",
        "Product withdrawal readouts",
        "Realized internal flows",
        "Product composition indicators",
        "Stage 1 light-component composition",
    ]
    expected_series = [
        ["condenser_duty_request_W", "reboiler_duty_request_W"],
        ["reflux_drum_holdup_mol", "bottoms_sump_holdup_mol"],
        ["distillate_flow_mol_s", "bottoms_flow_mol_s"],
        ["realized_condensed_flow_mol_s", "realized_reboiler_boilup_flow_mol_s"],
        ["distillate_light_key_component_x", "bottoms_heavy_key_component_x"],
        ["feed_stage_light_component_x"],
    ]
    first_marker_time = int(proof["baseline_steps"]) * 0.2
    second_marker_time = (int(proof["baseline_steps"]) + first_window) * 0.2

    for axis, expected_ylabel, expected_title, expected_labels in zip(
        axes, expected_ylabels, expected_titles, expected_series, strict=True
    ):
        assert axis.get_ylabel() == expected_ylabel
        assert axis.get_title() == expected_title
        plotted_labels = [
            line.get_label() for line in axis.lines if not line.get_label().startswith("_")
        ]
        assert plotted_labels == expected_labels
        assert any(line.get_xdata()[0] == pytest.approx(first_marker_time) for line in axis.lines)
        assert any(line.get_xdata()[0] == pytest.approx(second_marker_time) for line in axis.lines)


def test_main_prints_summary_before_invoking_plotting_helper(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    plot_calls: list[dict[str, object]] = []

    def fake_plot(**kwargs: object) -> object:
        plot_calls.append(
            {
                "kwargs": kwargs,
                "printed_output": capsys.readouterr().out,
            }
        )
        return object()

    monkeypatch.setattr(proof_module, "plot_backend_gas_starter_causal_proof", fake_plot)

    proof_module.main()

    assert len(plot_calls) == 1
    plotted = plot_calls[0]
    printed_output = cast(str, plotted["printed_output"])
    assert "BACKEND GAS STARTER STAGEWISE CAUSAL PROOF" in printed_output
    assert "DEMONSTRATED" in printed_output
    assert "DEFERRED" in printed_output

    kwargs = cast(dict[str, object], plotted["kwargs"])
    assert kwargs["dt_s"] == pytest.approx(0.2)
    assert kwargs["baseline_steps"] == 100
    assert kwargs["first_window"] == 500

    history = cast(list[dict[str, float]], kwargs["history"])
    assert len(history) == 1100
