from __future__ import annotations

from math import isfinite
from types import MappingProxyType
from typing import Any

import numpy as np
import pytest

from modular_simulation.connection.hydraulics.hydraulic_element import (
    HydraulicElement,
    PipeHydraulicElement,
    PumpHydraulicElement,
    ValveHydraulicElement,
    resolve_hydraulic_element,
)
from modular_simulation.connection.hydraulics.hydraulic_solver import (
    ElementEquation,
    HydraulicSystemDefinition,
)
from modular_simulation.thermodynamics.hydraulic_adapters import (
    default_pipe_hydraulic_parameters,
    default_pipe_resistance_for_unit,
    default_pump_hydraulic_parameters,
    default_valve_hydraulic_parameters,
)
from modular_simulation.unit_processes import (
    CSTR,
    PFR,
    ComponentSeparator,
    ConversionReactor,
    FlashDrum,
    HeatExchanger,
    HeaterCooler,
    Mixer,
    Pump,
    ShortcutDistillation,
    Splitter,
    Valve,
)


def _single_flow_equation(
    *,
    name: str,
    element: HydraulicElement,
    upstream_pressure: float,
    downstream_pressure: float,
    flow_unknown_name: str,
    parameters: dict[str, float],
) -> ElementEquation:
    return ElementEquation(
        name=name,
        element=element,
        inputs=MappingProxyType(
            {
                "upstream_pressure": upstream_pressure,
                "downstream_pressure": downstream_pressure,
            }
        ),
        parameters=MappingProxyType(parameters),
        unknown_name_map=MappingProxyType({"flow_rate": flow_unknown_name}),
        residual_name_map=MappingProxyType({"head_balance": f"{name}_head_balance"}),
    )


def test_pump_hydraulic() -> None:
    pump = Pump(n_species=2, pump_speed=120_000.0)
    element = pump.to_hydraulic_element("outlet")

    assert isinstance(element, PumpHydraulicElement)

    residual = element.residuals(
        inputs=MappingProxyType(
            {
                "upstream_pressure": 100_000.0,
                "downstream_pressure": 220_000.0,
            }
        ),
        unknowns=MappingProxyType({"flow_rate": 1.25}),
        parameters=MappingProxyType(default_pump_hydraulic_parameters(pump_speed=pump.pump_speed)),
    )["head_balance"]
    jacobian = element.jacobian(
        inputs=MappingProxyType(
            {
                "upstream_pressure": 100_000.0,
                "downstream_pressure": 220_000.0,
            }
        ),
        unknowns=MappingProxyType({"flow_rate": 1.25}),
        parameters=MappingProxyType(default_pump_hydraulic_parameters(pump_speed=pump.pump_speed)),
    )[("head_balance", "flow_rate")]

    assert residual == pytest.approx(0.0, abs=1.0e-12)
    assert jacobian == pytest.approx(0.0, abs=1.0e-12)


def test_network_hydraulic_solve() -> None:
    heater = HeaterCooler(n_species=2)
    valve = Valve(n_species=2, Cv=0.01, open_fraction=0.8, delta=1.0e-6)
    mixer = Mixer(n_inlets=2, n_species=2)

    equations = (
        _single_flow_equation(
            name="heater_line",
            element=heater.to_hydraulic_element("outlet"),
            upstream_pressure=150_000.0,
            downstream_pressure=110_000.0,
            flow_unknown_name="heater_flow",
            parameters=default_pipe_hydraulic_parameters(
                resistance=default_pipe_resistance_for_unit(unit_name=type(heater).__name__)
            ),
        ),
        _single_flow_equation(
            name="valve_line",
            element=valve.to_hydraulic_element("outlet"),
            upstream_pressure=180_000.0,
            downstream_pressure=120_000.0,
            flow_unknown_name="valve_flow",
            parameters=default_valve_hydraulic_parameters(
                cv=valve.Cv,
                open_fraction=valve.open_fraction,
                minimum_open_fraction=valve.minimum_open_fraction,
                maximum_open_fraction=valve.maximum_open_fraction,
                min_relative_open_fraction=valve.min_relative_open_fraction,
                delta=valve.delta,
            ),
        ),
        _single_flow_equation(
            name="mixer_line",
            element=mixer.to_hydraulic_element("outlet"),
            upstream_pressure=130_000.0,
            downstream_pressure=100_000.0,
            flow_unknown_name="mixer_flow",
            parameters=default_pipe_hydraulic_parameters(
                resistance=default_pipe_resistance_for_unit(unit_name=type(mixer).__name__)
            ),
        ),
    )
    system = HydraulicSystemDefinition(equations=equations)

    result = system.solve(
        initial_unknowns=MappingProxyType(
            {
                "heater_flow": 0.0,
                "valve_flow": 0.0,
                "mixer_flow": 0.0,
            }
        ),
        tolerance=1.0e-10,
        max_iterations=25,
    )

    assert result.converged
    assert result.residual_norm <= 1.0e-8
    assert isfinite(result.unknowns["heater_flow"])
    assert isfinite(result.unknowns["valve_flow"])
    assert isfinite(result.unknowns["mixer_flow"])
    assert result.unknowns["heater_flow"] > 0.0
    assert result.unknowns["valve_flow"] > 0.0
    assert result.unknowns["mixer_flow"] > 0.0


@pytest.mark.parametrize(
    ("unit", "port_name", "expected_resistance"),
    [
        (HeaterCooler(n_species=2), "outlet", 5.0e3),
        (CSTR(n_species=2), "outlet", 1.0e4),
        (PFR(n_species=2), "outlet", 1.0e4),
        (ConversionReactor(n_species=2), "outlet", 1.0e4),
        (FlashDrum(n_species=2), "vapor_outlet", 5.0e3),
        (FlashDrum(n_species=2), "liquid_outlet", 5.0e3),
        (ShortcutDistillation(n_species=2), "distillate", 2.0e4),
        (ShortcutDistillation(n_species=2), "bottoms", 2.0e4),
        (
            ComponentSeparator(
                n_species=2,
                configured_split_fraction_targets=np.array([0.0, 0.0], dtype=np.float64),
            ),
            "outlet_1",
            5.0e3,
        ),
        (
            ComponentSeparator(
                n_species=2,
                configured_split_fraction_targets=np.array([0.0, 0.0], dtype=np.float64),
            ),
            "outlet_2",
            5.0e3,
        ),
        (HeatExchanger(n_species=2), "hot_outlet", 5.0e3),
        (HeatExchanger(n_species=2), "cold_outlet", 5.0e3),
        (Mixer(n_inlets=2, n_species=2), "outlet", 1.0e3),
        (Splitter(n_outlets=2, n_species=2), "outlet_1", 1.0e3),
        (Splitter(n_outlets=2, n_species=2), "outlet_2", 1.0e3),
    ],
)
def test_pipe_hydraulic_defaults_for_units(
    unit: Any,
    port_name: str,
    expected_resistance: float,
) -> None:
    element = unit.to_hydraulic_element(port_name)
    assert isinstance(element, PipeHydraulicElement)
    assert default_pipe_resistance_for_unit(unit_name=type(unit).__name__) == pytest.approx(
        expected_resistance
    )


def test_multi_outlet_port_validation_lists_allowed_ports() -> None:
    flash = FlashDrum(n_species=2)
    with pytest.raises(
        ValueError,
        match="Allowed outlet ports: vapor_outlet, liquid_outlet",
    ):
        _ = flash.to_hydraulic_element("outlet")


def test_pipe_hydraulic_element_owns_default_parameters_and_geometry_bootstrap() -> None:
    heater = HeaterCooler(n_species=2)
    element = heater.to_hydraulic_element("outlet")

    parameters = element.default_parameters(
        source_unit=heater,
        source_node_id="heater",
        source_port_name="outlet",
        target_unit=None,
        target_node_id="sink",
    )
    bootstrap = element.line_bootstrap(
        source_unit=heater,
        source_node_id="heater",
        source_port_name="outlet",
        line_id="heater_line",
    )

    assert parameters == MappingProxyType(default_pipe_hydraulic_parameters(resistance=5.0e3))
    assert bootstrap is None


def test_pump_hydraulic_element_owns_default_parameters_and_bootstrap() -> None:
    pump = Pump(n_species=2, pump_speed=120_000.0)
    element = pump.to_hydraulic_element("outlet")

    parameters = element.default_parameters(
        source_unit=pump,
        source_node_id="pump",
        source_port_name="outlet",
        target_unit=None,
        target_node_id="sink",
    )
    bootstrap = element.line_bootstrap(
        source_unit=pump,
        source_node_id="pump",
        source_port_name="outlet",
        line_id="pump_line",
    )

    assert parameters == MappingProxyType(default_pump_hydraulic_parameters(pump_speed=0.0))
    assert bootstrap is not None
    assert bootstrap.geometry is not None
    assert bootstrap.geometry.resistance_parameter_name == "pump_speed"
    assert bootstrap.pump is not None
    assert bootstrap.pump.pump_id == "pump_line__pump"
    assert bootstrap.pump.initial_pump_speed == pytest.approx(120_000.0)
    assert bootstrap.pump.pump_parameter_name == "pump_speed"
    assert bootstrap.valve is None


def test_valve_hydraulic_element_owns_default_parameters_and_bootstrap() -> None:
    element = ValveHydraulicElement()

    parameters = element.default_parameters(
        source_unit=None,
        source_node_id="feed",
        source_port_name="outlet",
        target_unit=None,
        target_node_id="sink",
    )
    bootstrap = element.line_bootstrap(
        source_unit=None,
        source_node_id="feed",
        source_port_name="outlet",
        line_id="valve_line",
    )

    assert parameters == MappingProxyType({"valve_resistance": 1.0, "delta": 1.0e-6})
    assert bootstrap is not None
    assert bootstrap.geometry is not None
    assert bootstrap.geometry.resistance_parameter_name == "valve_resistance"
    assert bootstrap.resistance is not None
    assert bootstrap.resistance.mode == "manual_override"
    assert bootstrap.resistance.manual_value == pytest.approx(1.0)
    assert bootstrap.valve is not None
    assert bootstrap.valve.valve_id == "valve_line__valve"
    assert bootstrap.valve.initial_open_fraction == pytest.approx(1.0)
    assert bootstrap.valve.minimum_open_fraction == pytest.approx(0.0)
    assert bootstrap.valve.maximum_open_fraction == pytest.approx(1.0)


def test_resolve_hydraulic_element_uses_pipe_family_for_boundary_sources() -> None:
    element = resolve_hydraulic_element(
        source_unit=None,
        source_node_id="feed",
        source_port_name="outlet",
    )

    assert isinstance(element, PipeHydraulicElement)
