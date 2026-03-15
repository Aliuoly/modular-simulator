from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import sqrt
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from modular_simulation.measurables.process_model import ProcessModel

ElementValues = Mapping[str, float]
JacobianKey = tuple[str, str]
JacobianValues = Mapping[JacobianKey, float]


@dataclass(frozen=True)
class ElementParameterSpec:
    names: tuple[str, ...]


@dataclass(frozen=True)
class ElementUnknownSpec:
    names: tuple[str, ...]


@dataclass(frozen=True)
class ElementOutputSpec:
    residual_names: tuple[str, ...]


@dataclass(frozen=True)
class HydraulicLineGeometryBootstrap:
    radius_m: float
    length_m: float
    resistance_parameter_name: str


@dataclass(frozen=True)
class HydraulicLineResistanceBootstrap:
    mode: Literal["derived", "manual_override"]
    manual_value: float | None = None


@dataclass(frozen=True)
class HydraulicValveAttachmentBootstrap:
    valve_id: str
    minimum_open_fraction: float
    maximum_open_fraction: float
    initial_open_fraction: float
    resistance_parameter_name: str


@dataclass(frozen=True)
class HydraulicPumpAttachmentBootstrap:
    pump_id: str
    initial_pump_speed: float
    pump_parameter_name: str


@dataclass(frozen=True)
class HydraulicLineBootstrap:
    geometry: HydraulicLineGeometryBootstrap | None = None
    resistance: HydraulicLineResistanceBootstrap | None = None
    valve: HydraulicValveAttachmentBootstrap | None = None
    pump: HydraulicPumpAttachmentBootstrap | None = None


class HydraulicElement(ABC):
    """Thin nominal hydraulic family root exposing solver and ownership hooks only."""

    @property
    @abstractmethod
    def parameter_spec(self) -> ElementParameterSpec: ...

    @property
    @abstractmethod
    def unknown_spec(self) -> ElementUnknownSpec: ...

    @property
    @abstractmethod
    def output_spec(self) -> ElementOutputSpec: ...

    @abstractmethod
    def residuals(
        self,
        *,
        inputs: Mapping[str, float],
        unknowns: Mapping[str, float],
        parameters: Mapping[str, float],
    ) -> ElementValues: ...

    @abstractmethod
    def jacobian(
        self,
        *,
        inputs: Mapping[str, float],
        unknowns: Mapping[str, float],
        parameters: Mapping[str, float],
    ) -> JacobianValues: ...

    def default_parameters(
        self,
        *,
        source_unit: ProcessModel | None,
        source_node_id: str,
        source_port_name: str,
        target_unit: ProcessModel | None,
        target_node_id: str,
    ) -> Mapping[str, float]:
        """Family hook: return default hydraulic parameters for this element.

        Default implementation returns an empty, read-only mapping. Specific
        hydraulic families may override to provide meaningful defaults.
        """
        del source_unit, source_node_id, source_port_name, target_unit, target_node_id
        return MappingProxyType({})

    def line_bootstrap(
        self,
        *,
        source_unit: ProcessModel | None,
        source_node_id: str,
        source_port_name: str,
        line_id: str,
    ) -> HydraulicLineBootstrap | None:
        """Family hook: provide line bootstrap information for this element.

        Default implementation returns None. Families (pipe/valve/pump) may
        override to supply geometry, attachment or resistance bootstrap data.
        """
        del source_unit, source_node_id, source_port_name, line_id
        return None


def smooth_signed_quadratic_flow_term(*, m_dot: float, delta: float) -> float:
    if delta <= 0.0:
        raise ValueError("delta must be positive")
    return m_dot * sqrt(m_dot * m_dot + delta * delta)


def smooth_signed_quadratic_flow_term_derivative(*, m_dot: float, delta: float) -> float:
    if delta <= 0.0:
        raise ValueError("delta must be positive")
    denominator = sqrt(m_dot * m_dot + delta * delta)
    return (2.0 * m_dot * m_dot + delta * delta) / denominator


@dataclass(frozen=True)
class _SmoothHydraulicResistanceElement(HydraulicElement):
    """Shared pipe/valve base for smooth-loss defaults and resistance-line hooks."""

    resistance_parameter_name: str

    @property
    def parameter_spec(self) -> ElementParameterSpec:
        return ElementParameterSpec(names=(self.resistance_parameter_name, "delta"))

    @property
    def unknown_spec(self) -> ElementUnknownSpec:
        return ElementUnknownSpec(names=("flow_rate",))

    @property
    def output_spec(self) -> ElementOutputSpec:
        return ElementOutputSpec(residual_names=("head_balance",))

    def residuals(
        self,
        *,
        inputs: Mapping[str, float],
        unknowns: Mapping[str, float],
        parameters: Mapping[str, float],
    ) -> ElementValues:
        m_dot = unknowns["flow_rate"]
        resistance = parameters[self.resistance_parameter_name]
        delta = parameters["delta"]
        smooth_loss_term = smooth_signed_quadratic_flow_term(m_dot=m_dot, delta=delta)

        return {
            "head_balance": (
                inputs["upstream_pressure"]
                - inputs["downstream_pressure"]
                - resistance * smooth_loss_term
            )
        }

    def jacobian(
        self,
        *,
        inputs: Mapping[str, float],
        unknowns: Mapping[str, float],
        parameters: Mapping[str, float],
    ) -> JacobianValues:
        del inputs
        m_dot = unknowns["flow_rate"]
        resistance = parameters[self.resistance_parameter_name]
        delta = parameters["delta"]
        d_loss_dm_dot = smooth_signed_quadratic_flow_term_derivative(m_dot=m_dot, delta=delta)

        return {("head_balance", "flow_rate"): -resistance * d_loss_dm_dot}

    def default_parameters(
        self,
        *,
        source_unit: ProcessModel | None,
        source_node_id: str,
        source_port_name: str,
        target_unit: ProcessModel | None,
        target_node_id: str,
    ) -> Mapping[str, float]:
        del source_node_id, source_port_name, target_node_id
        from modular_simulation.thermodynamics.hydraulic_adapters import DEFAULT_HYDRAULIC_DELTA

        return MappingProxyType(
            {
                self.resistance_parameter_name: self._default_resistance(
                    source_unit=source_unit,
                    target_unit=target_unit,
                ),
                "delta": DEFAULT_HYDRAULIC_DELTA,
            }
        )

    def line_bootstrap(
        self,
        *,
        source_unit: ProcessModel | None,
        source_node_id: str,
        source_port_name: str,
        line_id: str,
    ) -> HydraulicLineBootstrap | None:
        del source_unit, source_node_id, source_port_name, line_id
        return None

    def _default_geometry_bootstrap(self) -> HydraulicLineGeometryBootstrap:
        return HydraulicLineGeometryBootstrap(
            radius_m=1.0,
            length_m=1.0,
            resistance_parameter_name=self.resistance_parameter_name,
        )

    @abstractmethod
    def _default_resistance(
        self,
        *,
        source_unit: ProcessModel | None,
        target_unit: ProcessModel | None,
    ) -> float: ...


@dataclass(frozen=True)
class PipeHydraulicElement(_SmoothHydraulicResistanceElement):
    """Pipe-family element owning passive default resistance selection."""

    resistance_parameter_name: str = "pipe_resistance"

    def _default_resistance(
        self,
        *,
        source_unit: ProcessModel | None,
        target_unit: ProcessModel | None,
    ) -> float:
        from modular_simulation.thermodynamics.hydraulic_adapters import (
            default_pipe_resistance_for_unit,
        )

        fallback_unit = source_unit if source_unit is not None else target_unit
        if fallback_unit is None:
            return 5.0e3
        return default_pipe_resistance_for_unit(unit_name=type(fallback_unit).__name__)


@dataclass(frozen=True)
class ValveHydraulicElement(_SmoothHydraulicResistanceElement):
    """Valve-family element owning valve defaults and actuator bootstrap policy."""

    resistance_parameter_name: str = "valve_resistance"

    def _default_resistance(
        self,
        *,
        source_unit: ProcessModel | None,
        target_unit: ProcessModel | None,
    ) -> float:
        del source_unit, target_unit
        return 1.0

    def line_bootstrap(
        self,
        *,
        source_unit: ProcessModel | None,
        source_node_id: str,
        source_port_name: str,
        line_id: str,
    ) -> HydraulicLineBootstrap:
        valve_parameters = _resolve_valve_hydraulic_seed_values(
            source_unit=source_unit,
            source_node_id=source_node_id,
            source_port_name=source_port_name,
        )
        resistance_when_open = 1.0 / (valve_parameters["cv"] * valve_parameters["cv"])
        return HydraulicLineBootstrap(
            geometry=self._default_geometry_bootstrap(),
            resistance=HydraulicLineResistanceBootstrap(
                mode="manual_override",
                manual_value=resistance_when_open,
            ),
            valve=HydraulicValveAttachmentBootstrap(
                valve_id=f"{line_id}__valve",
                minimum_open_fraction=valve_parameters["minimum_open_fraction"],
                maximum_open_fraction=valve_parameters["maximum_open_fraction"],
                initial_open_fraction=valve_parameters["open_fraction"],
                resistance_parameter_name=self.resistance_parameter_name,
            ),
        )


@dataclass(frozen=True)
class PumpHydraulicElement(HydraulicElement):
    """Pump-family element owning callback math plus pump bootstrap/default policy."""

    dp_curve: Callable[[float, float], float] | None = None
    d_dp_d_mdot: Callable[[float, float], float] | None = None

    @property
    def parameter_spec(self) -> ElementParameterSpec:
        return ElementParameterSpec(names=("pump_speed",))

    @property
    def unknown_spec(self) -> ElementUnknownSpec:
        return ElementUnknownSpec(names=("flow_rate",))

    @property
    def output_spec(self) -> ElementOutputSpec:
        return ElementOutputSpec(residual_names=("head_balance",))

    def __post_init__(self) -> None:
        if self.dp_curve is None:
            raise ValueError("dp_curve callback is required")
        if not callable(self.dp_curve):
            raise TypeError("dp_curve must be callable")

        if self.d_dp_d_mdot is None:
            raise ValueError("d_dp_d_mdot callback is required")
        if not callable(self.d_dp_d_mdot):
            raise TypeError("d_dp_d_mdot must be callable")

    def residuals(
        self,
        *,
        inputs: Mapping[str, float],
        unknowns: Mapping[str, float],
        parameters: Mapping[str, float],
    ) -> ElementValues:
        dp_curve = self.dp_curve
        if dp_curve is None:
            raise RuntimeError("dp_curve callback must be set")
        m_dot = unknowns["flow_rate"]
        pump_speed = parameters["pump_speed"]
        pump_head = dp_curve(m_dot, pump_speed)

        return {
            "head_balance": (
                inputs["upstream_pressure"] - inputs["downstream_pressure"] + pump_head
            )
        }

    def jacobian(
        self,
        *,
        inputs: Mapping[str, float],
        unknowns: Mapping[str, float],
        parameters: Mapping[str, float],
    ) -> JacobianValues:
        del inputs
        d_dp_d_mdot = self.d_dp_d_mdot
        if d_dp_d_mdot is None:
            raise RuntimeError("d_dp_d_mdot callback must be set")
        m_dot = unknowns["flow_rate"]
        pump_speed = parameters["pump_speed"]
        derivative = d_dp_d_mdot(m_dot, pump_speed)

        return {("head_balance", "flow_rate"): derivative}

    def default_parameters(
        self,
        *,
        source_unit: ProcessModel | None,
        source_node_id: str,
        source_port_name: str,
        target_unit: ProcessModel | None,
        target_node_id: str,
    ) -> Mapping[str, float]:
        del source_unit, source_node_id, source_port_name, target_unit, target_node_id
        from modular_simulation.thermodynamics.hydraulic_adapters import (
            default_pump_hydraulic_parameters,
        )

        return MappingProxyType(default_pump_hydraulic_parameters(pump_speed=0.0))

    def line_bootstrap(
        self,
        *,
        source_unit: ProcessModel | None,
        source_node_id: str,
        source_port_name: str,
        line_id: str,
    ) -> HydraulicLineBootstrap:
        pump_speed = _resolve_pump_hydraulic_seed_value(
            source_unit=source_unit,
            source_node_id=source_node_id,
            source_port_name=source_port_name,
        )
        return HydraulicLineBootstrap(
            geometry=HydraulicLineGeometryBootstrap(
                radius_m=1.0,
                length_m=1.0,
                resistance_parameter_name="pump_speed",
            ),
            pump=HydraulicPumpAttachmentBootstrap(
                pump_id=f"{line_id}__pump",
                initial_pump_speed=pump_speed,
                pump_parameter_name="pump_speed",
            ),
        )


def resolve_hydraulic_element(
    *,
    source_unit: ProcessModel | None,
    source_node_id: str,
    source_port_name: str,
) -> HydraulicElement:
    if source_unit is None:
        del source_node_id, source_port_name
        return PipeHydraulicElement()

    to_hydraulic_element = getattr(source_unit, "to_hydraulic_element", None)
    if not callable(to_hydraulic_element):
        raise ValueError(
            f"unit '{source_node_id}' does not implement to_hydraulic_element(port_name)"
        )
    element = to_hydraulic_element(source_port_name)
    if not isinstance(element, HydraulicElement):
        raise ValueError(
            f"unit '{source_node_id}' returned non-HydraulicElement for port '{source_port_name}'"
        )
    return element


def _try_resolve_hydraulic_parameter_getter(
    *, source_unit: ProcessModel | None
) -> Callable[[str], Mapping[str, float]] | None:
    if source_unit is None:
        return None
    parameter_getter = getattr(source_unit, "hydraulic_parameters_for_port", None)
    if not callable(parameter_getter):
        return None
    return lambda port_name: cast("Mapping[str, float]", parameter_getter(port_name))


def _resolve_pump_hydraulic_seed_value(
    *,
    source_unit: ProcessModel | None,
    source_node_id: str,
    source_port_name: str,
) -> float:
    parameter_getter = _try_resolve_hydraulic_parameter_getter(source_unit=source_unit)
    if parameter_getter is None:
        raise ValueError(
            f"unit '{source_node_id}' must implement hydraulic_parameters_for_port(port_name) "
            + "for pump hydraulic elements"
        )

    parameters = parameter_getter(source_port_name)
    if isinstance(parameters, Mapping) and "pump_speed" in parameters:
        return float(parameters["pump_speed"])
    raise ValueError(
        f"unit '{source_node_id}' returned invalid pump hydraulic parameters for port '{source_port_name}'"
    )


def _resolve_valve_hydraulic_seed_values(
    *,
    source_unit: ProcessModel | None,
    source_node_id: str,
    source_port_name: str,
) -> dict[str, float]:
    parameter_getter = _try_resolve_hydraulic_parameter_getter(source_unit=source_unit)
    if parameter_getter is None:
        return {
            "cv": 1.0,
            "open_fraction": 1.0,
            "minimum_open_fraction": 0.0,
            "maximum_open_fraction": 1.0,
        }

    parameters = parameter_getter(source_port_name)
    if not isinstance(parameters, Mapping):
        raise ValueError(
            f"unit '{source_node_id}' returned invalid valve hydraulic parameters for port '{source_port_name}'"
        )
    cv_raw = parameters.get("cv", parameters.get("Cv", 1.0))
    open_fraction_raw = parameters.get("open_fraction", 1.0)
    minimum_open_fraction_raw = parameters.get("minimum_open_fraction", 0.0)
    maximum_open_fraction_raw = parameters.get("maximum_open_fraction", 1.0)
    return {
        "cv": float(cv_raw),
        "open_fraction": float(open_fraction_raw),
        "minimum_open_fraction": float(minimum_open_fraction_raw),
        "maximum_open_fraction": float(maximum_open_fraction_raw),
    }


__all__ = [
    "ElementParameterSpec",
    "ElementUnknownSpec",
    "ElementOutputSpec",
    "HydraulicLineGeometryBootstrap",
    "HydraulicLineResistanceBootstrap",
    "HydraulicValveAttachmentBootstrap",
    "HydraulicPumpAttachmentBootstrap",
    "HydraulicLineBootstrap",
    "HydraulicElement",
    "smooth_signed_quadratic_flow_term",
    "smooth_signed_quadratic_flow_term_derivative",
    "PipeHydraulicElement",
    "ValveHydraulicElement",
    "PumpHydraulicElement",
    "resolve_hydraulic_element",
]
