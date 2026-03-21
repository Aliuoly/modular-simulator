from __future__ import annotations

from collections.abc import Sequence

from modular_simulation.connection.hydraulics.hydraulic_compile import (
    calculate_effective_valve_resistance,
)
from modular_simulation.connection.hydraulics.hydraulic_element import PipeHydraulicElement

DEFAULT_HYDRAULIC_DELTA = 1.0e-6

_PIPE_RESISTANCE_BY_UNIT_NAME: dict[str, float] = {
    "HeaterCooler": 5.0e3,
    "CSTR": 1.0e4,
    "PFR": 1.0e4,
    "ConversionReactor": 1.0e4,
    "FlashDrum": 5.0e3,
    "ShortcutDistillation": 2.0e4,
    "ComponentSeparator": 5.0e3,
    "HeatExchanger": 5.0e3,
}


def validate_outlet_port(
    *, unit_name: str, port_name: str, allowed_outlet_ports: Sequence[str]
) -> None:
    if port_name in allowed_outlet_ports:
        return
    allowed_ports_text = ", ".join(allowed_outlet_ports)
    raise ValueError(
        f"Invalid outlet port '{port_name}' for {unit_name}. "
        + f"Allowed outlet ports: {allowed_ports_text}."
    )


def pipe_hydraulic_element_for_outlet(
    *,
    unit_name: str,
    port_name: str,
    allowed_outlet_ports: Sequence[str],
) -> PipeHydraulicElement:
    validate_outlet_port(
        unit_name=unit_name,
        port_name=port_name,
        allowed_outlet_ports=allowed_outlet_ports,
    )
    return PipeHydraulicElement()


def default_pipe_hydraulic_parameters(
    *, resistance: float, delta: float = DEFAULT_HYDRAULIC_DELTA
) -> dict[str, float]:
    return {"pipe_resistance": float(resistance), "delta": float(delta)}


def default_pipe_resistance_for_unit(*, unit_name: str) -> float:
    resistance = _PIPE_RESISTANCE_BY_UNIT_NAME.get(unit_name)
    if resistance is None:
        allowed_names = ", ".join(sorted(_PIPE_RESISTANCE_BY_UNIT_NAME.keys()))
        raise ValueError(
            f"No default pipe resistance configured for unit '{unit_name}'. "
            + f"Supported unit names: {allowed_names}."
        )
    return float(resistance)


def default_valve_hydraulic_parameters(
    *,
    cv: float,
    open_fraction: float,
    minimum_open_fraction: float,
    maximum_open_fraction: float,
    min_relative_open_fraction: float,
    delta: float = DEFAULT_HYDRAULIC_DELTA,
) -> dict[str, float]:
    resistance_when_open = 1.0 / (float(cv) * float(cv))
    effective_resistance = calculate_effective_valve_resistance(
        resistance_when_open=resistance_when_open,
        open_fraction=float(open_fraction),
        minimum_open_fraction=float(minimum_open_fraction),
        maximum_open_fraction=float(maximum_open_fraction),
        min_relative_open_fraction=float(min_relative_open_fraction),
    )
    return {"valve_resistance": effective_resistance, "delta": float(delta)}


def default_pump_hydraulic_parameters(*, pump_speed: float) -> dict[str, float]:
    return {"pump_speed": float(pump_speed)}


__all__ = [
    "DEFAULT_HYDRAULIC_DELTA",
    "default_pipe_hydraulic_parameters",
    "default_pipe_resistance_for_unit",
    "default_pump_hydraulic_parameters",
    "default_valve_hydraulic_parameters",
    "pipe_hydraulic_element_for_outlet",
    "validate_outlet_port",
]
