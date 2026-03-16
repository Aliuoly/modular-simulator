from __future__ import annotations

import importlib
from collections.abc import Mapping
from types import MappingProxyType

import pytest

hydraulic_element = importlib.import_module(
    "modular_simulation.connection.hydraulics.hydraulic_element"
)
hydraulic_solver = importlib.import_module(
    "modular_simulation.connection.hydraulics.hydraulic_solver"
)
ElementOutputSpec = hydraulic_element.ElementOutputSpec
ElementParameterSpec = hydraulic_element.ElementParameterSpec
ElementUnknownSpec = hydraulic_element.ElementUnknownSpec
HydraulicElement = hydraulic_element.HydraulicElement
ElementEquation = hydraulic_solver.ElementEquation
PipeHydraulicElement = hydraulic_element.PipeHydraulicElement
PumpHydraulicElement = hydraulic_element.PumpHydraulicElement
ValveHydraulicElement = hydraulic_element.ValveHydraulicElement


def _pump_curve(flow_rate: float, pump_speed: float) -> float:
    return pump_speed - flow_rate


def _pump_curve_derivative(flow_rate: float, pump_speed: float) -> float:
    del flow_rate, pump_speed
    return -1.0


class DemoHydraulicElement(HydraulicElement):
    @property
    def parameter_spec(self) -> ElementParameterSpec:
        return ElementParameterSpec(names=("resistance", "pump_gain"))

    @property
    def unknown_spec(self) -> ElementUnknownSpec:
        return ElementUnknownSpec(names=("flow_rate",))

    @property
    def output_spec(self) -> ElementOutputSpec:
        return ElementOutputSpec(residual_names=("mass_balance", "head_balance"))

    def residuals(
        self,
        *,
        inputs: Mapping[str, float],
        unknowns: Mapping[str, float],
        parameters: Mapping[str, float],
    ) -> Mapping[str, float]:
        return {
            "mass_balance": unknowns["flow_rate"] - inputs["target_flow_rate"],
            "head_balance": (
                inputs["upstream_pressure"]
                - inputs["downstream_pressure"]
                - parameters["resistance"] * unknowns["flow_rate"]
                + parameters["pump_gain"] * inputs["pump_speed"]
            ),
        }

    def jacobian(
        self,
        *,
        inputs: Mapping[str, float],
        unknowns: Mapping[str, float],
        parameters: Mapping[str, float],
    ) -> Mapping[tuple[str, str], float]:
        del inputs, unknowns
        return {
            ("mass_balance", "flow_rate"): 1.0,
            ("head_balance", "flow_rate"): -parameters["resistance"],
        }


class IncompleteHydraulicElement(HydraulicElement):
    @property
    def parameter_spec(self) -> ElementParameterSpec:
        return ElementParameterSpec(names=("resistance",))

    @property
    def unknown_spec(self) -> ElementUnknownSpec:
        return ElementUnknownSpec(names=("flow_rate",))

    @property
    def output_spec(self) -> ElementOutputSpec:
        return ElementOutputSpec(residual_names=("head_balance",))


def test_hydraulic_element_requires_nominal_subclassing() -> None:
    element = DemoHydraulicElement()
    pipe = PipeHydraulicElement()
    valve = ValveHydraulicElement()
    pump = PumpHydraulicElement(dp_curve=_pump_curve, d_dp_d_mdot=_pump_curve_derivative)

    assert isinstance(element, HydraulicElement)
    assert isinstance(pipe, HydraulicElement)
    assert isinstance(valve, HydraulicElement)
    assert isinstance(pump, HydraulicElement)
    assert element.parameter_spec.names == ("resistance", "pump_gain")
    assert element.unknown_spec.names == ("flow_rate",)
    assert element.output_spec.residual_names == ("mass_balance", "head_balance")


def test_hydraulic_element_abc_requires_full_nominal_contract() -> None:
    with pytest.raises(TypeError, match="abstract"):
        IncompleteHydraulicElement()


def test_element_equation_rejects_non_nominal_element_instances() -> None:
    with pytest.raises(TypeError, match="must be a HydraulicElement"):
        ElementEquation(
            name="demo",
            element=object(),
            inputs=MappingProxyType({}),
            parameters=MappingProxyType({}),
            unknown_name_map=MappingProxyType({}),
            residual_name_map=MappingProxyType({}),
        )


def test_residual_and_jacobian_accept_generic_mapping_inputs() -> None:
    element = DemoHydraulicElement()

    inputs = MappingProxyType(
        {
            "upstream_pressure": 200_000.0,
            "downstream_pressure": 150_000.0,
            "target_flow_rate": 2.0,
            "pump_speed": 1_200.0,
        }
    )
    unknowns = MappingProxyType({"flow_rate": 3.0})
    parameters = MappingProxyType({"resistance": 10_000.0, "pump_gain": 40.0})

    residuals = element.residuals(inputs=inputs, unknowns=unknowns, parameters=parameters)
    jacobian = element.jacobian(inputs=inputs, unknowns=unknowns, parameters=parameters)

    assert residuals["mass_balance"] == 1.0
    assert residuals["head_balance"] == 68_000.0
    assert jacobian[("mass_balance", "flow_rate")] == 1.0
    assert jacobian[("head_balance", "flow_rate")] == -10_000.0


def test_jacobian_contract_uses_residual_and_unknown_name_pairs() -> None:
    element = DemoHydraulicElement()

    jacobian = element.jacobian(
        inputs=MappingProxyType(
            {
                "upstream_pressure": 200_000.0,
                "downstream_pressure": 150_000.0,
                "target_flow_rate": 2.0,
                "pump_speed": 1_200.0,
            }
        ),
        unknowns=MappingProxyType({"flow_rate": 3.0}),
        parameters=MappingProxyType({"resistance": 10_000.0, "pump_gain": 40.0}),
    )

    assert set(jacobian.keys()) == {
        ("mass_balance", "flow_rate"),
        ("head_balance", "flow_rate"),
    }
    assert all(isinstance(value, float) for value in jacobian.values())
