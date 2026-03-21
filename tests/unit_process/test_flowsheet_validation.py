from __future__ import annotations

# pyright: reportMissingTypeStubs=false

import warnings

import numpy as np
import pytest

from modular_simulation.connection.domain.error_catalog import (
    DiagnosticPayload,
    extract_diagnostic_payload,
)
from modular_simulation.connection.hydraulics.hydraulic_element import (
    PumpHydraulicElement,
    ValveHydraulicElement,
)
from modular_simulation.flowsheet import Flowsheet, PumpInstall
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.thermodynamics.hydraulic_participation import (
    HydraulicBalancingGroupSpec,
    HydraulicElementCouplingSpec,
    HydraulicParticipationSpec,
    HydraulicPortSpec,
    HydraulicRelationSpec,
    HydraulicScalarStateRef,
)
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import ComponentSeparator, FlashDrum, HeaterCooler
from modular_simulation.unit_processes.thermal.heat_exchanger import HeatExchanger
from modular_simulation.unit_processes.reactors.cstr import CSTR
from modular_simulation.unit_processes.reactors.pfr import PFR


def _install_hydraulic_participation_property(
    monkeypatch: pytest.MonkeyPatch,
    cls: type[object],
    getter,
) -> None:
    monkeypatch.setattr(cls, "hydraulic_participation", property(getter), raising=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(n_species: int = 2) -> SimulationRuntimeContext:
    names = ["water", "ethanol", "methanol"][:n_species]
    return SimulationRuntimeContext.create(species_names=names)


def _build_single_recycle_loop(
    *,
    pump: PumpInstall | None = None,
    context: SimulationRuntimeContext | None = None,
) -> Flowsheet:
    """Canonical single recycle loop: feed → junction(fresh+recycle) → heater → separator → junction(split) → recycle back.

    Topology:
        fresh_feed ──► mix.fresh
                        mix.to_heater ──► heater ──► separator
                                                       ├─ separator.outlet_1 → product_sink
                                                       └─ separator.outlet_2 → split.feed
                        mix.recycle ◄── split.recycle  (with optional pump)
                                         split.purge → purge_sink
    """
    ctx = context or _make_context()
    flowsheet = Flowsheet(context=ctx)
    n = 2

    flowsheet.add_junction(
        "mix",
        inlet_ports=("fresh", "recycle"),
        outlet_ports=("to_heater",),
    )
    flowsheet.add_unit("heater", HeaterCooler(n_species=n))
    flowsheet.add_unit(
        "separator",
        ComponentSeparator(
            n_species=n,
            configured_split_fraction_targets=np.array([0.6, 0.4], dtype=np.float64),
        ),
    )
    flowsheet.add_junction(
        "split",
        inlet_ports=("feed",),
        outlet_ports=("recycle", "purge"),
    )
    flowsheet.add_sink("product_sink")
    flowsheet.add_sink("purge_sink")
    flowsheet.add_feed_from_values("fresh_feed", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)

    flowsheet.connect("fresh_feed", "mix.fresh")
    flowsheet.connect("mix.to_heater", "heater")
    flowsheet.connect("heater", "separator")
    flowsheet.connect("separator.outlet_1", "product_sink")
    flowsheet.connect("separator.outlet_2", "split.feed")
    flowsheet.connect(
        "split.recycle",
        "mix.recycle",
        line_id="recycle_line",
        pump=pump,
    )
    flowsheet.connect("split.purge", "purge_sink")

    return flowsheet


def _assert_recycle_diagnostic_schema(payload: DiagnosticPayload) -> None:
    """Assert that a recycle-loop diagnostic payload has the required shape.

    Contract (from plan lines 33-44):
      code:    "INVALID_RECYCLE_LOOP"
      path:    "Flowsheet.compile"
      hint:    starts with "Add a pump"
      message: contains ordered loop path text and "positive line-installed pressure boost"
    """
    assert set(payload) >= {"code", "message", "path", "hint", "revision"}
    assert payload["code"] == "INVALID_RECYCLE_LOOP"
    assert payload["path"] == "Flowsheet.compile"
    assert isinstance(payload["hint"], str)
    assert str(payload["hint"]).startswith("Add a pump")
    assert isinstance(payload["message"], str)
    assert "positive line-installed pressure boost" in str(payload["message"])


# ---------------------------------------------------------------------------
# Existing validation tests (pre-szt.3, preserved)
# ---------------------------------------------------------------------------


def test_unbound_inlet() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater_1", HeaterCooler(n_species=2))
    flowsheet.add_unit("heater_2", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed", "heater_1")

    with pytest.raises(ValueError, match=r"unbound mandatory inlet\(s\): heater_2\.inlet"):
        _ = flowsheet.compile()


def test_ambiguous_port() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("flash", FlashDrum(n_species=2, thermal_mode="isothermal"))
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))

    with pytest.raises(
        ValueError,
        match="ambiguous source endpoint 'flash': available source ports are vapor_outlet, liquid_outlet",
    ):
        flowsheet.connect("flash", "heater")


def test_species_mismatch_missing_species_named() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol", "methanol"])
    species_ids = context.species_registry.cas_list
    missing_species_id = species_ids[2]

    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=3))
    flowsheet.add_feed(
        "feed",
        StreamData(
            temperature=300.0,
            pressure=101325.0,
            mole_fractions=(0.5, 0.5),
            molar_flow_rate=1.0,
            species_ids=(species_ids[0], species_ids[1]),
        ),
    )
    flowsheet.connect("feed", "heater")

    with pytest.raises(ValueError, match="species mismatch") as exc:
        _ = flowsheet.compile()

    assert missing_species_id in str(exc.value)


def test_dangling_outlet_warns() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed", "heater")

    with pytest.warns(UserWarning, match="dangling outlet"):
        _ = flowsheet.compile()


def test_disconnected_subgraph_warns() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater_a", HeaterCooler(n_species=2))
    flowsheet.add_unit("heater_b", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed_a", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_feed_from_values("feed_b", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed_a", "heater_a")
    flowsheet.connect("feed_b", "heater_b")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = flowsheet.compile()

    messages = [str(item.message) for item in caught]
    assert any("disconnected topology detected" in message for message in messages)


def test_cycle_compiles_without_legacy_recycle_warning() -> None:
    """Recycle loop with supported positive pump boost compiles without the legacy cycle warning.

    Replaces the pre-szt.2 version that used illegal direct unit-port fan-in.
    Uses the canonical junction API: fresh feed + recycle merge through a junction.
    """
    flowsheet = _build_single_recycle_loop(
        pump=PumpInstall(initial_pump_speed=80_000.0),
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = flowsheet.compile()

    messages = [str(item.message) for item in caught]
    assert not any("recycle/cycle detected" in message for message in messages)


def test_compile_requires_pressure_boundary_feed() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater_a", HeaterCooler(n_species=2))
    flowsheet.add_unit("heater_b", HeaterCooler(n_species=2))
    flowsheet.connect("heater_a", "heater_b")
    flowsheet.connect("heater_b", "heater_a")

    with pytest.raises(ValueError, match="at least one feed boundary is required"):
        _ = flowsheet.compile()


def test_declared_single_path_balancing_group_emits_unit_flow_balance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        HeaterCooler,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "outlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(name="through_unit", ports=("inlet", "outlet")),
            ),
            relations=(
                HydraulicRelationSpec(
                    name="through_unit_equal_pressure",
                    kind="pressure_equal",
                    ports=("inlet", "outlet"),
                ),
            ),
        ),
    )

    flowsheet = Flowsheet(context=_make_context())
    flowsheet.add_unit("heater", HeaterCooler(n_species=2))
    flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_sink("product")
    flowsheet.connect("feed", "heater")
    flowsheet.connect("heater", "product")

    plant = flowsheet.compile()

    compiled = plant._network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    residuals = {
        equation.residual_name for equation in compiled.hydraulic.system.linear_residual_equations
    }
    assert "unit__heater__flow_balance__01" in residuals


def test_declared_paired_path_balancing_groups_emit_one_equation_per_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        HeatExchanger,
        lambda self: HydraulicParticipationSpec(
            ports={
                "hot_inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("hot_inlet_pressure"),
                ),
                "hot_outlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("hot_outlet_pressure"),
                ),
                "cold_inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("cold_inlet_pressure"),
                ),
                "cold_outlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("cold_outlet_pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(name="hot_side", ports=("hot_inlet", "hot_outlet")),
                HydraulicBalancingGroupSpec(name="cold_side", ports=("cold_inlet", "cold_outlet")),
            ),
            relations=(
                HydraulicRelationSpec(
                    name="hot_equal_pressure",
                    kind="pressure_equal",
                    ports=("hot_inlet", "hot_outlet"),
                ),
                HydraulicRelationSpec(
                    name="cold_equal_pressure",
                    kind="pressure_equal",
                    ports=("cold_inlet", "cold_outlet"),
                ),
            ),
        ),
    )

    flowsheet = Flowsheet(context=_make_context())
    flowsheet.add_unit("hx", HeatExchanger(n_species=2))
    flowsheet.add_feed_from_values("hot_feed", T=360.0, P=140_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_feed_from_values("cold_feed", T=290.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_sink("hot_product")
    flowsheet.add_sink("cold_product")
    flowsheet.connect("hot_feed", "hx.hot_inlet")
    flowsheet.connect("cold_feed", "hx.cold_inlet")
    flowsheet.connect("hx.hot_outlet", "hot_product")
    flowsheet.connect("hx.cold_outlet", "cold_product")

    plant = flowsheet.compile()

    compiled = plant._network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    residuals = {
        equation.residual_name for equation in compiled.hydraulic.system.linear_residual_equations
    }
    assert "unit__hx__flow_balance__01" in residuals
    assert "unit__hx__flow_balance__02" in residuals


@pytest.mark.parametrize("unit_cls", (CSTR, PFR))
def test_declared_fixed_pressure_anchor_emits_pressure_anchor_for_reactor_outlet(
    monkeypatch: pytest.MonkeyPatch,
    unit_cls,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        unit_cls,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "outlet": HydraulicPortSpec(
                    role="fixed_pressure_anchor",
                    pressure_state=HydraulicScalarStateRef("pressure"),
                    fixed_value_state=HydraulicScalarStateRef("pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(name="through_reactor", ports=("inlet", "outlet")),
            ),
        ),
    )

    flowsheet = Flowsheet(context=_make_context())
    if unit_cls is CSTR:
        reactor = CSTR(n_species=2, pressure=125_000.0)
    else:
        reactor = PFR(n_species=2, pressure=125_000.0)
    flowsheet.add_unit("reactor", reactor)
    flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_sink("product")
    flowsheet.connect("feed", "reactor")
    flowsheet.connect("reactor", "product")

    plant = flowsheet.compile()

    compiled = plant._network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    anchors = {
        anchor.topology_label: anchor.pressure_value
        for anchor in compiled.hydraulic.system.pressure_anchor_metadata
    }
    assert anchors["reactor.outlet"] == pytest.approx(125_000.0)


def test_declared_affine_pressure_relation_emits_pressure_drop_equation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        HeaterCooler,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "outlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(name="through_unit", ports=("inlet", "outlet")),
            ),
            relations=(
                HydraulicRelationSpec(
                    name="unit_drop",
                    kind="pressure_drop",
                    ports=("inlet", "outlet"),
                    parameter_state=HydraulicScalarStateRef("pressure_drop"),
                ),
            ),
        ),
    )

    flowsheet = Flowsheet(context=_make_context())
    flowsheet.add_unit("heater", HeaterCooler(n_species=2, pressure_drop=2_500.0))
    flowsheet.add_unit("cooler", HeaterCooler(n_species=2, inlet_pressure=118_000.0))
    flowsheet.add_feed_from_values("feed", T=300.0, P=120_500.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed", "heater")
    flowsheet.connect("heater", "cooler")

    plant = flowsheet.compile()

    compiled = plant._network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    residuals = {
        equation.residual_name: equation
        for equation in compiled.hydraulic.system.linear_residual_equations
    }
    relation = residuals["unit__heater__pressure_relation"]
    assert relation.constant == pytest.approx(-2_500.0)


def test_declared_element_coupling_uses_unit_owned_hydraulic_element(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _pressure_gain_curve(flow_rate: float, gain: float) -> float:
        del flow_rate
        return gain

    def _d_pressure_gain_curve(flow_rate: float, gain: float) -> float:
        del flow_rate, gain
        return 0.0

    for unit_id, expected_element_type, element_parameters in (
        ("gain_like", PumpHydraulicElement, {"pump_speed": 80_000.0}),
        (
            "throttle_like",
            ValveHydraulicElement,
            {"valve_resistance": 1.0e3, "delta": 1.0e-6},
        ),
    ):
        _install_hydraulic_participation_property(
            monkeypatch,
            HeaterCooler,
            lambda self: HydraulicParticipationSpec(
                ports={
                    "inlet": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                    ),
                    "outlet": HydraulicPortSpec(
                        role="pressure_state",
                        pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    ),
                },
                balancing_groups=(
                    HydraulicBalancingGroupSpec(name="through_unit", ports=("inlet", "outlet")),
                ),
                element_couplings=(
                    HydraulicElementCouplingSpec(
                        name="unit_element",
                        port="outlet",
                        ports=("inlet", "outlet"),
                    ),
                ),
            ),
        )

        if expected_element_type is PumpHydraulicElement:
            monkeypatch.setattr(
                HeaterCooler,
                "to_hydraulic_element",
                lambda self, port_name: PumpHydraulicElement(
                    dp_curve=_pressure_gain_curve,
                    d_dp_d_mdot=_d_pressure_gain_curve,
                ),
                raising=False,
            )
        else:
            monkeypatch.setattr(
                HeaterCooler,
                "to_hydraulic_element",
                lambda self, port_name: ValveHydraulicElement(),
                raising=False,
            )
        monkeypatch.setattr(
            HeaterCooler,
            "hydraulic_parameters_for_port",
            lambda self, port_name: element_parameters,
            raising=False,
        )

        flowsheet = Flowsheet(context=_make_context())
        flowsheet.add_unit(unit_id, HeaterCooler(n_species=2))
        flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
        flowsheet.add_sink("product")
        flowsheet.connect("feed", unit_id)
        flowsheet.connect(unit_id, "product")

        plant = flowsheet.compile()

        compiled = plant._network.compiled
        assert compiled is not None and compiled.hydraulic is not None
        equation = next(
            candidate
            for candidate in compiled.hydraulic.system.equations
            if candidate.name == f"unit__{unit_id}__element_coupling__unit_element"
        )
        wrapped_element = getattr(equation.element, "wrapped")
        assert isinstance(wrapped_element, expected_element_type)


def test_identical_declared_pressure_refs_share_one_hydraulic_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_hydraulic_participation_property(
        monkeypatch,
        FlashDrum,
        lambda self: HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef("inlet_pressure"),
                ),
                "vapor_outlet": HydraulicPortSpec(
                    role="fixed_pressure_anchor",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    fixed_value_state=HydraulicScalarStateRef("imposed_pressure"),
                ),
                "liquid_outlet": HydraulicPortSpec(
                    role="fixed_pressure_anchor",
                    pressure_state=HydraulicScalarStateRef("outlet_pressure"),
                    fixed_value_state=HydraulicScalarStateRef("imposed_pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(
                    name="flash_balance",
                    ports=("inlet", "vapor_outlet", "liquid_outlet"),
                ),
            ),
        ),
    )

    flowsheet = Flowsheet(context=_make_context())
    flowsheet.add_unit("flash", FlashDrum(n_species=2, thermal_mode="isothermal"))
    flowsheet.add_feed_from_values("feed", T=300.0, P=130_000.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.add_sink("vapor_product")
    flowsheet.add_sink("liquid_product")
    flowsheet.connect("feed", "flash")
    flowsheet.connect("flash.vapor_outlet", "vapor_product")
    flowsheet.connect("flash.liquid_outlet", "liquid_product")

    plant = flowsheet.compile()

    compiled = plant._network.compiled
    assert compiled is not None and compiled.hydraulic is not None
    lookup = compiled.hydraulic.system.topology_lookup
    assert (
        lookup.node_pressure_unknown_by_endpoint["flash.vapor_outlet"]
        == lookup.node_pressure_unknown_by_endpoint["flash.liquid_outlet"]
    )


# ---------------------------------------------------------------------------
# szt.3 recycle-loop rejection regression tests
#
# Diagnostic contract (approved plan lines 33-44, error_catalog.py):
#   - failure shape: DiagnosticValueError with payload via extract_diagnostic_payload
#   - payload["code"]:    "INVALID_RECYCLE_LOOP"
#   - payload["path"]:    "Flowsheet.compile"
#   - payload["hint"]:    starts with "Add a pump"
#   - payload["message"]: contains ordered loop path + "positive line-installed pressure boost"
#   - multiple loops: reported in normalized sorted order, identical across runs
#   - duplicate rotations: same cycle under different start-node reported only once
# ---------------------------------------------------------------------------


class TestRecycleLoopRejection:
    """Regression tests for compile-time rejection of invalid recycle loops.

    The topology constructions are canonical under szt.2 and exercise both
    accepted and rejected recycle configurations under the implemented szt.3
    validation rules.
    """

    def test_recycle_loop_without_pump_boost_fails_compile(self) -> None:
        """A recycle loop with no line-installed pump must fail at compile time
        with a diagnostic payload identifying the offending loop path."""
        flowsheet = _build_single_recycle_loop(pump=None)

        with pytest.raises(ValueError, match="positive line-installed pressure boost") as exc:
            _ = flowsheet.compile()

        payload = extract_diagnostic_payload(exc.value)
        assert payload is not None, "expected DiagnosticValueError with extractable payload"
        _assert_recycle_diagnostic_schema(payload)
        # The message must contain the ordered loop path through the cycle
        # (normalized to lexicographic-minimum rotation).
        assert "heater -> separator -> split -> mix -> heater" in str(payload["message"])

    def test_recycle_loop_with_zero_boost_pump_fails_compile(self) -> None:
        """A recycle loop with a zero-speed pump (no actual boost) must still fail."""
        flowsheet = _build_single_recycle_loop(
            pump=PumpInstall(initial_pump_speed=0.0),
        )

        with pytest.raises(ValueError, match="positive line-installed pressure boost") as exc:
            _ = flowsheet.compile()

        payload = extract_diagnostic_payload(exc.value)
        assert payload is not None, "expected DiagnosticValueError with extractable payload"
        _assert_recycle_diagnostic_schema(payload)

    def test_recycle_loop_with_positive_boost_pump_compiles(self) -> None:
        """A recycle loop with a positive-boost pump must compile successfully
        without emitting the legacy recycle warning."""
        flowsheet = _build_single_recycle_loop(
            pump=PumpInstall(initial_pump_speed=80_000.0),
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            plant = flowsheet.compile()

        assert plant is not None
        messages = [str(item.message) for item in caught]
        assert not any("recycle/cycle detected" in msg for msg in messages)

    def test_multiple_invalid_recycle_loops_report_deterministic_payloads(self) -> None:
        """When multiple invalid recycle loops exist, the diagnostic payload must
        be identical across repeated compilations of the same topology."""
        ctx = _make_context()
        n = 2

        def _build() -> Flowsheet:
            fs = Flowsheet(context=ctx)
            # Loop A: feed_a → mix_a(fresh+recycle) → heater_a → split_a(recycle+product) → back
            fs.add_junction("mix_a", inlet_ports=("fresh", "recycle"), outlet_ports=("out",))
            fs.add_unit("heater_a", HeaterCooler(n_species=n))
            fs.add_junction("split_a", inlet_ports=("in",), outlet_ports=("recycle", "product"))
            fs.add_sink("sink_a")
            fs.add_feed_from_values("feed_a", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)

            fs.connect("feed_a", "mix_a.fresh")
            fs.connect("mix_a.out", "heater_a")
            fs.connect("heater_a", "split_a.in")
            fs.connect("split_a.recycle", "mix_a.recycle", line_id="recycle_a")
            fs.connect("split_a.product", "sink_a")

            # Loop B: feed_b → mix_b(fresh+recycle) → heater_b → split_b(recycle+product) → back
            fs.add_junction("mix_b", inlet_ports=("fresh", "recycle"), outlet_ports=("out",))
            fs.add_unit("heater_b", HeaterCooler(n_species=n))
            fs.add_junction("split_b", inlet_ports=("in",), outlet_ports=("recycle", "product"))
            fs.add_sink("sink_b")
            fs.add_feed_from_values("feed_b", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)

            fs.connect("feed_b", "mix_b.fresh")
            fs.connect("mix_b.out", "heater_b")
            fs.connect("heater_b", "split_b.in")
            fs.connect("split_b.recycle", "mix_b.recycle", line_id="recycle_b")
            fs.connect("split_b.product", "sink_b")

            return fs

        # Build and compile twice — payloads must be identical.
        payloads: list[DiagnosticPayload] = []
        for _ in range(2):
            fs = _build()
            with pytest.raises(ValueError, match="positive line-installed pressure boost") as exc:
                _ = fs.compile()
            payload = extract_diagnostic_payload(exc.value)
            assert payload is not None, "expected DiagnosticValueError with extractable payload"
            payloads.append(payload)

        assert payloads[0] == payloads[1], "diagnostic payloads must be identical across runs"
        _assert_recycle_diagnostic_schema(payloads[0])

        # Both loop paths must appear in the message in stable sorted order.
        message = str(payloads[0]["message"])
        loop_a = "heater_a -> split_a -> mix_a -> heater_a"
        loop_b = "heater_b -> split_b -> mix_b -> heater_b"
        assert loop_a in message
        assert loop_b in message
        assert message.index(loop_a) < message.index(loop_b), (
            "invalid loops must be reported in normalized sorted order"
        )

    def test_duplicate_cycle_rotations_not_reported_twice(self) -> None:
        """The cycle heater_a→junc_ab→heater_b→junc_ba→heater_a is the same cycle
        regardless of which node is the entry point. Validation must report it
        exactly once under canonical rotation, not as separate errors."""
        ctx = _make_context()
        n = 2
        flowsheet = Flowsheet(context=ctx)

        flowsheet.add_unit("heater_a", HeaterCooler(n_species=n))
        flowsheet.add_unit("heater_b", HeaterCooler(n_species=n))
        flowsheet.add_junction("junc_ab", inlet_ports=("from_a",), outlet_ports=("to_b",))
        flowsheet.add_junction("junc_ba", inlet_ports=("from_b", "fresh"), outlet_ports=("to_a",))
        flowsheet.add_feed_from_values("feed", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)

        flowsheet.connect("feed", "junc_ba.fresh")
        flowsheet.connect("junc_ba.to_a", "heater_a")
        flowsheet.connect("heater_a", "junc_ab.from_a")
        flowsheet.connect("junc_ab.to_b", "heater_b")
        flowsheet.connect("heater_b", "junc_ba.from_b")

        with pytest.raises(ValueError, match="positive line-installed pressure boost") as exc:
            _ = flowsheet.compile()

        payload = extract_diagnostic_payload(exc.value)
        assert payload is not None, "expected DiagnosticValueError with extractable payload"
        _assert_recycle_diagnostic_schema(payload)

        # The normalized canonical loop path. Under lexicographic-minimum rotation
        # the cycle starting at "heater_a" should appear exactly once.
        message = str(payload["message"])
        canonical_loop = "heater_a -> junc_ab -> heater_b -> junc_ba -> heater_a"
        assert message.count(canonical_loop) == 1, (
            f"expected exactly 1 occurrence of canonical loop path, got "
            f"{message.count(canonical_loop)}"
        )

    def test_mixed_valid_and_invalid_loops_fails_on_invalid(self) -> None:
        """A flowsheet with one valid recycle loop (positive-boost pump) and one
        invalid recycle loop (no pump) must fail at compile time.

        Spec scenario: 'Mixed valid and invalid loops are reported deterministically'.
        """
        ctx = _make_context()
        n = 2
        flowsheet = Flowsheet(context=ctx)

        # Valid loop A: feed_a → mix_a → heater_a → split_a → recycle with pump → back
        flowsheet.add_junction("mix_a", inlet_ports=("fresh", "recycle"), outlet_ports=("out",))
        flowsheet.add_unit("heater_a", HeaterCooler(n_species=n))
        flowsheet.add_junction("split_a", inlet_ports=("in",), outlet_ports=("recycle", "product"))
        flowsheet.add_sink("sink_a")
        flowsheet.add_feed_from_values("feed_a", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)

        flowsheet.connect("feed_a", "mix_a.fresh")
        flowsheet.connect("mix_a.out", "heater_a")
        flowsheet.connect("heater_a", "split_a.in")
        flowsheet.connect(
            "split_a.recycle",
            "mix_a.recycle",
            line_id="recycle_valid",
            pump=PumpInstall(initial_pump_speed=80_000.0),
        )
        flowsheet.connect("split_a.product", "sink_a")

        # Invalid loop B: feed_b → mix_b → heater_b → split_b → recycle NO pump → back
        flowsheet.add_junction("mix_b", inlet_ports=("fresh", "recycle"), outlet_ports=("out",))
        flowsheet.add_unit("heater_b", HeaterCooler(n_species=n))
        flowsheet.add_junction("split_b", inlet_ports=("in",), outlet_ports=("recycle", "product"))
        flowsheet.add_sink("sink_b")
        flowsheet.add_feed_from_values("feed_b", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)

        flowsheet.connect("feed_b", "mix_b.fresh")
        flowsheet.connect("mix_b.out", "heater_b")
        flowsheet.connect("heater_b", "split_b.in")
        flowsheet.connect("split_b.recycle", "mix_b.recycle", line_id="recycle_invalid")
        flowsheet.connect("split_b.product", "sink_b")

        with pytest.raises(ValueError, match="positive line-installed pressure boost") as exc:
            _ = flowsheet.compile()

        payload = extract_diagnostic_payload(exc.value)
        assert payload is not None, "expected DiagnosticValueError with extractable payload"
        _assert_recycle_diagnostic_schema(payload)

        # Only the invalid loop B should appear in the error message.
        message = str(payload["message"])
        invalid_loop = "heater_b -> split_b -> mix_b -> heater_b"
        assert invalid_loop in message, f"expected invalid loop path in message, got: {message}"
        # The valid loop A must not appear as an error.
        valid_loop = "heater_a -> split_a -> mix_a -> heater_a"
        assert valid_loop not in message, (
            "valid loop with positive pump boost must not be reported as invalid"
        )

    def test_non_cyclic_topology_compiles_without_recycle_rejection(self) -> None:
        """A purely linear (acyclic) flowsheet must compile without recycle rejection,
        even when recycle-loop validation is active."""
        ctx = _make_context()
        n = 2
        flowsheet = Flowsheet(context=ctx)

        flowsheet.add_unit("heater", HeaterCooler(n_species=n))
        flowsheet.add_unit(
            "separator",
            ComponentSeparator(
                n_species=n,
                configured_split_fraction_targets=np.array([0.6, 0.4], dtype=np.float64),
            ),
        )
        flowsheet.add_sink("product_sink")
        flowsheet.add_sink("waste_sink")
        flowsheet.add_feed_from_values("feed", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)

        flowsheet.connect("feed", "heater")
        flowsheet.connect("heater", "separator")
        flowsheet.connect("separator.outlet_1", "product_sink")
        flowsheet.connect("separator.outlet_2", "waste_sink")

        # Must compile without error — no recycle loop present.
        plant = flowsheet.compile()
        assert plant is not None

    # -------------------------------------------------------------------
    # Regression: shared-node multi-cycle (topology A)
    # -------------------------------------------------------------------

    def test_shared_node_multi_cycle_detects_all_cycles(self) -> None:
        """Two cycles sharing nodes a and c must both be detected.

        Topology:
            feed -> a.fresh
            a.to_b -> b.from_a -> b.to_c -> c.from_b   (pump on a->b edge — valid)
            a.to_d -> d.from_a -> d.to_c -> c.from_d   (no pump — invalid)
            c.to_a -> a.from_c

        Cycles:
            a -> b -> c -> a  (pump on a.to_b -> b.from_a — valid)
            a -> d -> c -> a  (no pump — invalid)

        The pump is placed on the b-branch (which sorts first in DFS).
        A buggy algorithm that stops after finding the first cycle would
        only find a -> b -> c -> a (valid), miss a -> d -> c -> a (invalid),
        and incorrectly allow compile to succeed.

        Compile must fail because the d-branch cycle is invalid.
        """
        ctx = _make_context()
        flowsheet = Flowsheet(context=ctx)

        flowsheet.add_junction(
            "a",
            inlet_ports=("fresh", "from_c"),
            outlet_ports=("to_b", "to_d"),
        )
        flowsheet.add_junction("b", inlet_ports=("from_a",), outlet_ports=("to_c",))
        flowsheet.add_junction("d", inlet_ports=("from_a",), outlet_ports=("to_c",))
        flowsheet.add_junction(
            "c",
            inlet_ports=("from_b", "from_d"),
            outlet_ports=("to_a",),
        )

        flowsheet.add_feed_from_values("feed", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)

        flowsheet.connect("feed", "a.fresh")
        # The b-branch has a pump — this cycle (a -> b -> c -> a) is valid
        flowsheet.connect(
            "a.to_b",
            "b.from_a",
            pump=PumpInstall(initial_pump_speed=80_000.0),
        )
        flowsheet.connect("b.to_c", "c.from_b")
        flowsheet.connect("c.to_a", "a.from_c")
        # The d-branch has NO pump — this cycle (a -> d -> c -> a) is invalid
        flowsheet.connect("a.to_d", "d.from_a")
        flowsheet.connect("d.to_c", "c.from_d")

        with pytest.raises(ValueError, match="positive line-installed pressure boost") as exc:
            _ = flowsheet.compile()

        payload = extract_diagnostic_payload(exc.value)
        assert payload is not None, "expected DiagnosticValueError with extractable payload"
        _assert_recycle_diagnostic_schema(payload)

        # The invalid cycle a -> d -> c -> a must appear in the error.
        message = str(payload["message"])
        assert "a -> d -> c -> a" in message, (
            f"expected invalid cycle 'a -> d -> c -> a' in message, got: {message}"
        )
        # The valid cycle a -> b -> c -> a must NOT appear as invalid.
        assert "a -> b -> c -> a" not in message, (
            "valid cycle with pump must not be reported as invalid"
        )

    # -------------------------------------------------------------------
    # Regression: port-distinct parallel lines (topology B)
    # -------------------------------------------------------------------

    def test_parallel_lines_same_node_ids_preserve_line_identity(self) -> None:
        """Two parallel lines between split and merge with different ports
        must preserve line identity so pump semantics are not confused.

        Topology:
            feed -> split.fresh
            split.to_merge_a -> merge.from_split_a  (NO pump — invalid cycle)
            split.to_merge_b -> merge.from_split_b  (positive pump — valid cycle)
            merge.to_split -> split.recycle

        Two distinct port-level cycles exist over the same node pair:
            Cycle A: split -> merge -> split via to_merge_a / from_split_a (no pump)
            Cycle B: split -> merge -> split via to_merge_b / from_split_b (pumped)

        Compile must fail because cycle A is invalid. The pumped parallel
        edge must not mask the unpumped one.

        The diagnostic message must identify the concrete invalid edge combination
        (by line id) so the user knows which path lacks a pump boost. The pumped
        alternative (line_with_pump) must not be reported as the offender.
        """
        ctx = _make_context()
        flowsheet = Flowsheet(context=ctx)

        flowsheet.add_junction(
            "split",
            inlet_ports=("fresh", "recycle"),
            outlet_ports=("to_merge_a", "to_merge_b"),
        )
        flowsheet.add_junction(
            "merge",
            inlet_ports=("from_split_a", "from_split_b"),
            outlet_ports=("to_split",),
        )

        flowsheet.add_feed_from_values("feed", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)

        flowsheet.connect("feed", "split.fresh")
        # Line A: no pump (creates invalid cycle)
        flowsheet.connect("split.to_merge_a", "merge.from_split_a", line_id="line_no_pump")
        # Line B: positive pump (creates valid cycle)
        flowsheet.connect(
            "split.to_merge_b",
            "merge.from_split_b",
            line_id="line_with_pump",
            pump=PumpInstall(initial_pump_speed=80_000.0),
        )
        flowsheet.connect("merge.to_split", "split.recycle", line_id="recycle_line")

        with pytest.raises(ValueError, match="positive line-installed pressure boost") as exc:
            _ = flowsheet.compile()

        payload = extract_diagnostic_payload(exc.value)
        assert payload is not None, "expected DiagnosticValueError with extractable payload"
        _assert_recycle_diagnostic_schema(payload)

        # The diagnostic message must identify the concrete invalid edge path so the
        # user can distinguish the unpumped path from the pumped alternative.
        # The invalid combination includes line_no_pump (the unpumped edge); the
        # message must name it so the path is actionable.
        message = str(payload["message"])
        assert "line_no_pump" in message, (
            f"expected 'line_no_pump' (the invalid edge) to be named in the diagnostic "
            f"message so the user can distinguish it from the pumped alternative; got: {message}"
        )
        # The pumped alternative must NOT appear as the offender in the message.
        assert "line_with_pump" not in message, (
            f"expected 'line_with_pump' (a valid pumped edge) NOT to appear as an offender "
            f"in the diagnostic message; got: {message}"
        )

    # -------------------------------------------------------------------
    # Regression: blocked-set DFS misses cycle through shared internal node
    # -------------------------------------------------------------------

    def test_blocked_node_does_not_suppress_later_sibling_cycle(self) -> None:
        """An incomplete cycle enumerator (e.g. blocked-set DFS without
        proper cascading unblock) can miss cycles that share the same
        start node but pass through different intermediate nodes.

        Clean two-cycle topology with NO smaller invalid subcycle:

        Junctions:
            a0: inlet_ports=(from_feed, from_a1, from_a4),
                outlet_ports=(to_a1, to_a2)
            a1: inlet_ports=(from_a0,), outlet_ports=(to_a0,)
            a2: inlet_ports=(from_a0,), outlet_ports=(to_a3,)
            a3: inlet_ports=(from_a2,), outlet_ports=(to_a4,)
            a4: inlet_ports=(from_a3,), outlet_ports=(to_a0,)

        Directed edges:
            feed  → a0
            a0 → a1,  a1 → a0  (pump on a1→a0 — valid cycle a0→a1→a0)
            a0 → a2,  a2 → a3,  a3 → a4,  a4 → a0  (no pump — invalid cycle)

        Elementary cycles:
            a0 → a1 → a0                (valid — has pump)
            a0 → a2 → a3 → a4 → a0     (INVALID — no pump)

        No smaller invalid subcycle exists (a1 has no edge to a2/a3/a4;
        a2/a3/a4 form a chain back to a0, not back to each other).

        A correct enumerator must find both cycles. Compile must fail
        because the second cycle has no positive pump boost.
        """
        ctx = _make_context()
        flowsheet = Flowsheet(context=ctx)

        flowsheet.add_junction(
            "a0",
            inlet_ports=("from_feed", "from_a1", "from_a4"),
            outlet_ports=("to_a1", "to_a2"),
        )
        flowsheet.add_junction("a1", inlet_ports=("from_a0",), outlet_ports=("to_a0",))
        flowsheet.add_junction("a2", inlet_ports=("from_a0",), outlet_ports=("to_a3",))
        flowsheet.add_junction("a3", inlet_ports=("from_a2",), outlet_ports=("to_a4",))
        flowsheet.add_junction("a4", inlet_ports=("from_a3",), outlet_ports=("to_a0",))

        flowsheet.add_feed_from_values("feed", T=300.0, P=120_000.0, z=(0.5, 0.5), flow=1.0)

        flowsheet.connect("feed", "a0.from_feed")
        # a0 → a1 (no pump on this direction)
        flowsheet.connect("a0.to_a1", "a1.from_a0")
        # a1 → a0 with pump — makes cycle a0→a1→a0 valid
        flowsheet.connect(
            "a1.to_a0",
            "a0.from_a1",
            pump=PumpInstall(initial_pump_speed=80_000.0),
        )
        # a0 → a2 (no pump)
        flowsheet.connect("a0.to_a2", "a2.from_a0")
        # a2 → a3 (no pump)
        flowsheet.connect("a2.to_a3", "a3.from_a2")
        # a3 → a4 (no pump)
        flowsheet.connect("a3.to_a4", "a4.from_a3")
        # a4 → a0 (no pump — closes the invalid cycle)
        flowsheet.connect("a4.to_a0", "a0.from_a4")

        # The invalid cycle a0→a2→a3→a4→a0 must be detected.
        with pytest.raises(ValueError, match="positive line-installed pressure boost") as exc:
            _ = flowsheet.compile()

        payload = extract_diagnostic_payload(exc.value)
        assert payload is not None, "expected DiagnosticValueError with extractable payload"
        _assert_recycle_diagnostic_schema(payload)

        message = str(payload["message"])
        # The invalid cycle must appear in the diagnostic message.
        # Under canonical lex-min rotation, "a0" is smallest, so it stays at front.
        assert "a0 -> a2 -> a3 -> a4 -> a0" in message, (
            f"expected the invalid cycle path in message, got: {message}"
        )
