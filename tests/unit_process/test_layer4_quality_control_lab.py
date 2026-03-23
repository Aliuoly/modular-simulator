from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportMissingImports=false, reportUnknownMemberType=false

"""Red tests for QualityControlLab — Wave 1, Task 1.4.

All tests in this module are expected to FAIL before the QualityControlLab
implementation exists (import error or AttributeError on unimplemented
attributes).  They define the observable boundaries that the implementation
must satisfy.
"""

import pytest
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes.analysis.quality_control_lab import (  # type: ignore[import]
    QualityControlLab,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_COMPONENT = "methane"
_DEFAULT_PURITY = 0.95


def _make_lab(
    *,
    tracked_component_id: str = _DEFAULT_COMPONENT,
    minimum_purity_mol_fraction: float = _DEFAULT_PURITY,
    **kwargs: object,
) -> QualityControlLab:
    return QualityControlLab(  # type: ignore[call-arg]
        tracked_component_id=tracked_component_id,
        minimum_purity_mol_fraction=minimum_purity_mol_fraction,
        **kwargs,
    )


def _send_stream(
    lab: QualityControlLab,
    *,
    inlet_flow: float,
    tracked_mol_fraction: float,
    dt: float = 1.0,
) -> None:
    """Drive the lab with a simple two-species stream where the first species
    is the tracked component.

    The stream composition is (tracked_mol_fraction, 1 - tracked_mol_fraction).
    """
    lab.inlet_flow = inlet_flow  # type: ignore[assignment]
    lab.inlet_temperature = 300.0  # type: ignore[assignment]
    lab.inlet_pressure = 101325.0  # type: ignore[assignment]
    lab.inlet_composition = (tracked_mol_fraction, 1.0 - tracked_mol_fraction)  # type: ignore[assignment]
    lab.step(dt)


# ---------------------------------------------------------------------------
# Port shape contract
# ---------------------------------------------------------------------------


def test_quality_control_lab_has_exactly_one_inlet() -> None:
    """QualityControlLab must expose exactly one inlet port named 'inlet'."""
    lab = _make_lab()
    assert lab.ports.inlets == ("inlet",)


def test_quality_control_lab_has_exactly_one_reject_outlet() -> None:
    """QualityControlLab must expose exactly one outlet port named 'reject_outlet'."""
    lab = _make_lab()
    assert lab.ports.outlets == ("reject_outlet",)


# ---------------------------------------------------------------------------
# Configuration inputs
# ---------------------------------------------------------------------------


def test_quality_control_lab_stores_tracked_component_id() -> None:
    """tracked_component_id must be accessible and match the constructor value."""
    lab = _make_lab(tracked_component_id="propane", minimum_purity_mol_fraction=0.90)
    assert lab.tracked_component_id == "propane"  # type: ignore[attr-defined]


def test_quality_control_lab_stores_minimum_purity_mol_fraction() -> None:
    """minimum_purity_mol_fraction must be accessible and match the constructor value."""
    lab = _make_lab(tracked_component_id="ethane", minimum_purity_mol_fraction=0.80)
    assert lab.minimum_purity_mol_fraction == pytest.approx(0.80)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Progress tracking: initial state
# ---------------------------------------------------------------------------


def test_quality_control_lab_accepted_progress_mol_starts_at_zero() -> None:
    """accepted_progress_mol must be 0.0 before any stream is processed."""
    lab = _make_lab()
    assert float(lab.accepted_progress_mol) == pytest.approx(0.0)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Threshold-met stream: whole-stream credit
# ---------------------------------------------------------------------------


def test_quality_control_lab_threshold_met_adds_full_stream_moles() -> None:
    """A stream that meets the purity threshold must add its entire molar
    amount to accepted_progress_mol.

    Stream: 10 mol/s at exactly minimum_purity_mol_fraction for 1.0 s.
    Expected credit: 10.0 mol.
    """
    lab = _make_lab(tracked_component_id="methane", minimum_purity_mol_fraction=0.90)
    _send_stream(lab, inlet_flow=10.0, tracked_mol_fraction=0.90, dt=1.0)

    assert float(lab.accepted_progress_mol) == pytest.approx(10.0)  # type: ignore[attr-defined]


def test_quality_control_lab_threshold_exceeded_adds_full_stream_moles_no_bonus() -> None:
    """A stream with purity above the threshold must add *only* the full incoming
    stream molar amount — no bonus for higher-than-minimum purity.

    Two streams at the same flow rate but different purity levels must
    produce the same incremental progress when both are above threshold.
    """
    lab_exact = _make_lab(tracked_component_id="methane", minimum_purity_mol_fraction=0.80)
    lab_high = _make_lab(tracked_component_id="methane", minimum_purity_mol_fraction=0.80)

    _send_stream(
        lab_exact, inlet_flow=5.0, tracked_mol_fraction=0.80, dt=1.0
    )  # exactly at threshold
    _send_stream(
        lab_high, inlet_flow=5.0, tracked_mol_fraction=0.99, dt=1.0
    )  # well above threshold

    # Both must credit the same 5.0 mol — no bonus for higher purity.
    assert float(lab_exact.accepted_progress_mol) == pytest.approx(5.0)  # type: ignore[attr-defined]
    assert float(lab_high.accepted_progress_mol) == pytest.approx(5.0)  # type: ignore[attr-defined]


def test_quality_control_lab_accumulates_credit_across_multiple_accepted_steps() -> None:
    """accepted_progress_mol must accumulate across multiple accepted steps."""
    lab = _make_lab(tracked_component_id="methane", minimum_purity_mol_fraction=0.95)

    _send_stream(lab, inlet_flow=4.0, tracked_mol_fraction=0.95, dt=1.0)
    progress_after_first = float(lab.accepted_progress_mol)  # type: ignore[attr-defined]
    _send_stream(lab, inlet_flow=6.0, tracked_mol_fraction=0.98, dt=1.0)
    progress_after_second = float(lab.accepted_progress_mol)  # type: ignore[attr-defined]

    assert progress_after_first == pytest.approx(4.0)
    assert progress_after_second == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Threshold-failing stream: zero credit
# ---------------------------------------------------------------------------


def test_quality_control_lab_below_threshold_adds_zero_credit() -> None:
    """A stream that falls below the purity threshold must add zero to
    accepted_progress_mol.
    """
    lab = _make_lab(tracked_component_id="methane", minimum_purity_mol_fraction=0.90)
    _send_stream(lab, inlet_flow=8.0, tracked_mol_fraction=0.89, dt=1.0)

    assert float(lab.accepted_progress_mol) == pytest.approx(0.0)  # type: ignore[attr-defined]


def test_quality_control_lab_rejected_stream_does_not_affect_prior_credit() -> None:
    """A rejected stream must not reduce previously accumulated credit."""
    lab = _make_lab(tracked_component_id="methane", minimum_purity_mol_fraction=0.90)

    _send_stream(lab, inlet_flow=5.0, tracked_mol_fraction=0.95, dt=1.0)  # accepted
    credit_after_accepted = float(lab.accepted_progress_mol)  # type: ignore[attr-defined]

    _send_stream(lab, inlet_flow=7.0, tracked_mol_fraction=0.85, dt=1.0)  # rejected
    credit_after_rejected = float(lab.accepted_progress_mol)  # type: ignore[attr-defined]

    assert credit_after_accepted == pytest.approx(5.0)
    assert credit_after_rejected == pytest.approx(5.0)  # unchanged


# ---------------------------------------------------------------------------
# Outlet routing: accepted and rejected streams both leave through reject_outlet
# ---------------------------------------------------------------------------


def test_quality_control_lab_accepted_stream_routes_through_reject_outlet() -> None:
    """In this first pack, accepted material must still leave through the sole
    reject_outlet port.

    After an accepted step the reject_outlet_flow must equal the full inlet flow
    (no material vanishes; the lab physically has only one outlet).
    """
    lab = _make_lab(tracked_component_id="methane", minimum_purity_mol_fraction=0.90)
    _send_stream(lab, inlet_flow=6.0, tracked_mol_fraction=0.95, dt=1.0)

    assert float(lab.reject_outlet_flow) == pytest.approx(6.0)  # type: ignore[attr-defined]


def test_quality_control_lab_rejected_stream_routes_through_reject_outlet() -> None:
    """A below-threshold stream must also leave through reject_outlet."""
    lab = _make_lab(tracked_component_id="methane", minimum_purity_mol_fraction=0.90)
    _send_stream(lab, inlet_flow=4.0, tracked_mol_fraction=0.80, dt=1.0)

    assert float(lab.reject_outlet_flow) == pytest.approx(4.0)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Hydraulic participation
# ---------------------------------------------------------------------------


def test_quality_control_lab_declares_explicit_hydraulic_participation() -> None:
    """QualityControlLab must expose a non-None hydraulic_participation with
    pressure_state ports for both 'inlet' and 'reject_outlet', and at least one
    balancing group covering both.
    """
    lab = _make_lab()
    hp = lab.hydraulic_participation

    assert hp is not None
    assert "inlet" in hp.ports
    assert "reject_outlet" in hp.ports
    assert hp.ports["inlet"].role == "pressure_state"
    assert hp.ports["reject_outlet"].role == "pressure_state"
    assert hp.ports["inlet"].pressure_state is not None
    assert hp.ports["reject_outlet"].pressure_state is not None


def test_quality_control_lab_hydraulic_participation_has_inlet_reject_outlet_balancing_group() -> (
    None
):
    """The balancing group must span both 'inlet' and 'reject_outlet'."""
    lab = _make_lab()
    hp = lab.hydraulic_participation

    assert hp is not None
    group_port_sets = [set(g.ports) for g in hp.balancing_groups]
    assert {"inlet", "reject_outlet"} in group_port_sets


def test_quality_control_lab_hydraulic_participation_has_exactly_one_balancing_group() -> None:
    """The spec freezes exactly one balancing group over (inlet, reject_outlet).

    No additional groups are permitted: exactly one group, and it must span
    both 'inlet' and 'reject_outlet'.
    """
    lab = _make_lab()
    hp = lab.hydraulic_participation

    assert hp is not None
    groups = hp.balancing_groups
    assert len(groups) == 1
    assert set(groups[0].ports) == {"inlet", "reject_outlet"}


# ---------------------------------------------------------------------------
# Behavior depends on tracked_component_id, not just attribute storage
# ---------------------------------------------------------------------------


def test_quality_control_lab_purity_decision_uses_tracked_component_id() -> None:
    """The pass/fail decision must be applied to the component identified by
    tracked_component_id, not to a fixed composition slot.

    Both labs receive an identical two-species stream whose composition is
    (methane_fraction=0.95, ethane_fraction=0.05).  The two labs differ only
    in their tracked_component_id:

    - lab_methane tracks "methane" (the first slot, purity 0.95 >= 0.90) → accepted
    - lab_ethane tracks "ethane" (the second slot, purity 0.05 < 0.90) → rejected

    If the lab ignores tracked_component_id and always reads the same fixed
    slot, both labs would produce the same accepted_progress_mol.  The test
    asserts they differ, which is only possible if the lab correctly resolves
    the tracked component ID to the appropriate fraction.
    """
    threshold = 0.90

    # Build identical stream state for both labs:
    # composition = (0.95 methane, 0.05 ethane)
    def _drive_with_named_stream(lab: QualityControlLab) -> None:
        lab.inlet_flow = 10.0  # type: ignore[assignment]
        lab.inlet_temperature = 300.0  # type: ignore[assignment]
        lab.inlet_pressure = 101325.0  # type: ignore[assignment]
        # species order: [methane, ethane] — same as the canonical test context
        lab.inlet_composition = (0.95, 0.05)  # type: ignore[assignment]
        lab.step(1.0)

    lab_methane = _make_lab(
        tracked_component_id="methane",
        minimum_purity_mol_fraction=threshold,
    )
    lab_ethane = _make_lab(
        tracked_component_id="ethane",
        minimum_purity_mol_fraction=threshold,
    )

    _drive_with_named_stream(lab_methane)
    _drive_with_named_stream(lab_ethane)

    # lab_methane: tracked purity 0.95 >= 0.90 → stream accepted
    assert float(lab_methane.accepted_progress_mol) == pytest.approx(10.0)  # type: ignore[attr-defined]

    # lab_ethane: tracked purity 0.05 < 0.90 → stream rejected
    assert float(lab_ethane.accepted_progress_mol) == pytest.approx(0.0)  # type: ignore[attr-defined]


def test_quality_control_lab_apply_inlet_uses_stream_species_ids_for_tracked_component() -> None:
    """When stream metadata supplies species order, it must drive purity lookup.

    Here tracked component is methane, but methane appears in slot 1 rather than
    slot 0. Without using species_ids metadata, purity decision would read slot 0
    and incorrectly reject the stream.
    """
    lab = _make_lab(tracked_component_id="methane", minimum_purity_mol_fraction=0.90)

    lab.apply_inlet(
        "inlet",
        StreamData(
            temperature=300.0,
            pressure=101_325.0,
            mole_fractions=(0.05, 0.95),
            molar_flow_rate=10.0,
            species_ids=("ethane", "methane"),
        ),
    )
    lab.step(1.0)

    assert float(lab.accepted_progress_mol) == pytest.approx(10.0)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Connected-network compile proof
# ---------------------------------------------------------------------------


def test_quality_control_lab_compiles_as_ordinary_connected_process_node() -> None:
    """QualityControlLab must compile as an ordinary two-port process node in a
    minimal feed → lab → sink flowsheet.

    The reject_outlet port is the sole outlet; the flowsheet connect call must
    use the explicit 'lab.reject_outlet' endpoint syntax because the port name
    differs from the default 'outlet'.
    """
    from modular_simulation.connection.runtime.connected_plant_orchestrator import (
        ConnectedPlantOrchestrator,
    )
    from modular_simulation.flowsheet import Flowsheet
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext

    context = SimulationRuntimeContext.create(species_names=["methane", "ethane"])
    flowsheet = Flowsheet(context=context, dt=0.5)

    lab = QualityControlLab(  # type: ignore[call-arg]
        tracked_component_id="methane",
        minimum_purity_mol_fraction=0.90,
    )
    flowsheet.add_unit("lab", lab)
    flowsheet.add_feed_from_values("feed", T=300.0, P=150_000.0, z=(0.8, 0.2), flow=3.0)
    flowsheet.add_sink("disposal")

    flowsheet.connect("feed", "lab")
    flowsheet.connect("lab.reject_outlet", "disposal")

    plant = flowsheet.compile()

    assert isinstance(plant, ConnectedPlantOrchestrator)


# ---------------------------------------------------------------------------
# Outlet stream metadata: species_ids preservation
# ---------------------------------------------------------------------------


def test_quality_control_lab_outlet_stream_preserves_species_ids_non_canonical_order() -> None:
    """get_outlet_stream() must carry forward the inlet species_ids so downstream
    units can correctly interpret composition order.

    Here methane is in slot 1 (non-canonical).  The outlet StreamData must report
    species_ids=("ethane", "methane"), not None or any other ordering.
    Without this fix, a downstream unit would silently misread slot 0 as methane.
    """
    lab = _make_lab(tracked_component_id="methane", minimum_purity_mol_fraction=0.90)

    lab.apply_inlet(
        "inlet",
        StreamData(
            temperature=310.0,
            pressure=200_000.0,
            mole_fractions=(0.05, 0.95),
            molar_flow_rate=8.0,
            species_ids=("ethane", "methane"),
        ),
    )
    lab.step(1.0)

    outlet = lab.get_outlet_stream("reject_outlet")

    assert outlet.species_ids == ("ethane", "methane"), (
        f"Expected species_ids=('ethane', 'methane') on outlet stream, got {outlet.species_ids!r}"
    )
