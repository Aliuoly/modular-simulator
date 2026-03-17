from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from ..domain.domain_contracts import ResistanceConfig, ValveConfig
from .hydraulic_compile import (
    CompiledValveHydraulicState,
    compile_valve_hydraulic_state,
    resolve_line_resistance,
)
from .hydraulic_solver import (
    ElementEquation,
    HydraulicSystemDefinition,
)


_VALVE_ACTUATOR_NAMESPACE_PREFIX = "actuator/valve/"
_PUMP_ACTUATOR_NAMESPACE_PREFIX = "actuator/pump/"
_HEAT_ACTUATOR_NAMESPACE_PREFIX = "actuator/heat/"


@dataclass(frozen=True)
class LinePumpConfig:
    """Small value object describing an attached pump on a line.

    Responsibility:
        Store identification and the initial parameter choice for a pump
        overlay attached to a hydraulic line. This is a small, storage-only
        value object used by LineHydraulicConfig to record pump attachment
        metadata; behavior and validation belong to the manager.
    """

    pump_id: str
    initial_pump_speed: float
    pump_parameter_name: str


@dataclass(frozen=True)
class LineHydraulicConfig:
    """Container describing the hydraulic overlay configuration for a line.

    Responsibility:
        Record the chosen hydraulic equation, the resistance parameter name,
        and any attached valve or pump overlays. This class is a pure data
        holder; mutation and higher-level validation are the responsibility of
        LineHydraulicConfigManager.
    """

    line_id: str
    equation_name: str
    resistance_parameter_name: str
    resistance: ResistanceConfig
    valve: ValveConfig | None
    pump: LinePumpConfig | None


@dataclass(frozen=True)
class LineHydraulicConfigManagerSnapshot:
    """Snapshot of manager-owned line-hydraulic configuration and pending commands.

    Responsibility:
        Capture only the configuration and staged command state owned by
        LineHydraulicConfigManager so ConnectionNetwork (or other callers)
        can embed and restore manager state without reaching into manager
        internals.
    """

    line_hydraulic_configs: dict[str, LineHydraulicConfig]
    pending_valve_open_fractions: dict[str, float]
    pending_pump_speeds: dict[str, float]
    line_heat_actuator_ids: dict[str, str]
    heat_actuator_rates: dict[str, float]
    pending_heat_actuator_rates: dict[str, float]


class LineHydraulicConfigManager:
    """Manager that owns line-specific hydraulic configuration and staged commands.

    Responsibility:
        Own the line-hydraulic configuration cluster (geometry/resistance,
        attached valve/pump overlays, heat-actuator mapping) and staged
        command queues (valve/pump/heat actuator commands). This manager
        provides snapshot capture/restore and compile-time overlay projection
        but does not own graph compilation or network topology.
    """

    def __init__(self) -> None:
        self._line_hydraulic_configs: dict[str, LineHydraulicConfig] = {}
        self._pending_valve_open_fractions: dict[str, float] = {}
        self._pending_pump_speeds: dict[str, float] = {}
        self._line_heat_actuator_ids: dict[str, str] = {}
        self._heat_actuator_rates: dict[str, float] = {}
        self._pending_heat_actuator_rates: dict[str, float] = {}

    def list_line_hydraulic_configs(self) -> tuple[LineHydraulicConfig, ...]:
        return tuple(sorted(self._line_hydraulic_configs.values(), key=lambda item: item.line_id))

    def list_pending_valve_open_fractions(self) -> tuple[tuple[str, float], ...]:
        return tuple(
            (line_id, self._pending_valve_open_fractions[line_id])
            for line_id in sorted(self._pending_valve_open_fractions)
        )

    def list_pending_pump_speeds(self) -> tuple[tuple[str, float], ...]:
        return tuple(
            (line_id, self._pending_pump_speeds[line_id])
            for line_id in sorted(self._pending_pump_speeds)
        )

    def list_line_heat_actuator_ids(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (line_id, self._line_heat_actuator_ids[line_id])
            for line_id in sorted(self._line_heat_actuator_ids)
        )

    def list_heat_actuator_rates(self) -> tuple[tuple[str, float], ...]:
        return tuple(
            (line_id, self._heat_actuator_rates[line_id])
            for line_id in sorted(self._heat_actuator_rates)
        )

    def list_pending_heat_actuator_rates(self) -> tuple[tuple[str, float], ...]:
        return tuple(
            (line_id, self._pending_heat_actuator_rates[line_id])
            for line_id in sorted(self._pending_heat_actuator_rates)
        )

    def get_line_hydraulic_config(self, line_id: str) -> LineHydraulicConfig | None:
        return self._line_hydraulic_configs.get(line_id)

    def has_line_hydraulic_configs(self) -> bool:
        return bool(self._line_hydraulic_configs)

    def capture_snapshot(self) -> LineHydraulicConfigManagerSnapshot:
        return LineHydraulicConfigManagerSnapshot(
            line_hydraulic_configs=dict(self._line_hydraulic_configs),
            pending_valve_open_fractions=dict(self._pending_valve_open_fractions),
            pending_pump_speeds=dict(self._pending_pump_speeds),
            line_heat_actuator_ids=dict(self._line_heat_actuator_ids),
            heat_actuator_rates=dict(self._heat_actuator_rates),
            pending_heat_actuator_rates=dict(self._pending_heat_actuator_rates),
        )

    def restore_snapshot(self, snapshot: LineHydraulicConfigManagerSnapshot) -> None:
        self._line_hydraulic_configs = dict(snapshot.line_hydraulic_configs)
        self._pending_valve_open_fractions = dict(snapshot.pending_valve_open_fractions)
        self._pending_pump_speeds = dict(snapshot.pending_pump_speeds)
        self._line_heat_actuator_ids = dict(snapshot.line_heat_actuator_ids)
        self._heat_actuator_rates = dict(snapshot.heat_actuator_rates)
        self._pending_heat_actuator_rates = dict(snapshot.pending_heat_actuator_rates)

    def apply_compile_overlays(
        self,
        *,
        system: HydraulicSystemDefinition,
        assert_line_exists: Callable[[str], None],
    ) -> tuple[HydraulicSystemDefinition, Mapping[str, CompiledValveHydraulicState]]:
        if not self.has_line_hydraulic_configs():
            return system, {}

        equations = list(system.equations)
        equation_name_to_index: dict[str, int] = {}
        for index, equation in enumerate(equations):
            if equation.name in equation_name_to_index:
                raise ValueError(
                    "line configuration requires unique equation names; duplicate {!r}".format(
                        equation.name
                    )
                )
            equation_name_to_index[equation.name] = index

        valve_state_by_line: dict[str, CompiledValveHydraulicState] = {}
        for config in self.list_line_hydraulic_configs():
            line_id = config.line_id
            assert_line_exists(line_id)
            resolved_resistance = resolve_line_resistance(
                line_id=line_id,
                resistance=config.resistance,
            )

            equation_index = equation_name_to_index.get(config.equation_name)
            if equation_index is None:
                raise ValueError(
                    "line {!r} references unknown hydraulic equation {!r}".format(
                        line_id,
                        config.equation_name,
                    )
                )
            equation = equations[equation_index]
            parameter_name = config.resistance_parameter_name
            supported_parameter_names = equation.element.parameter_spec.names
            if parameter_name not in supported_parameter_names:
                raise ValueError(
                    "line {!r} references unsupported resistance parameter {!r} for equation {!r}".format(
                        line_id,
                        parameter_name,
                        equation.name,
                    )
                )

            if config.valve is not None and config.pump is not None:
                raise ValueError(
                    "line {!r} cannot attach both valve and pump hydraulic overlays".format(line_id)
                )

            if config.valve is not None:
                valve_state_by_line[line_id] = compile_valve_hydraulic_state(
                    line_id=line_id,
                    equation_name=config.equation_name,
                    resolved_resistance=resolved_resistance,
                    valve=config.valve,
                    resistance_parameter_name=parameter_name,
                )
                continue

            if config.pump is not None:
                pump_parameter_name = config.pump.pump_parameter_name
                if pump_parameter_name not in supported_parameter_names:
                    raise ValueError(
                        "line {!r} references unsupported pump parameter {!r} for equation {!r}".format(
                            line_id,
                            pump_parameter_name,
                            equation.name,
                        )
                    )
                equations[equation_index] = self._replace_equation_parameter(
                    equation=equation,
                    parameter_name=pump_parameter_name,
                    parameter_value=config.pump.initial_pump_speed,
                )
                continue

            equations[equation_index] = self._replace_equation_parameter(
                equation=equation,
                parameter_name=parameter_name,
                parameter_value=resolved_resistance.active_value,
            )

        return (
            HydraulicSystemDefinition(
                equations=tuple(equations),
                linear_residual_equations=system.linear_residual_equations,
                unknown_order=system.unknown_order,
                residual_order=system.residual_order,
                topology_lookup=system.topology_lookup,
                pressure_anchor_metadata=system.pressure_anchor_metadata,
            ),
            valve_state_by_line,
        )

    def configure_line_geometry(
        self,
        *,
        line_id: str,
        radius_m: float,
        length_m: float,
        equation_name: str | None,
        resistance_parameter_name: str | None,
        default_equation_name: str,
    ) -> None:
        previous = self._line_hydraulic_configs.get(line_id)
        resolved_equation_name = (
            previous.equation_name if previous is not None else default_equation_name
        )
        resolved_parameter_name = (
            previous.resistance_parameter_name if previous is not None else "pipe_resistance"
        )
        resistance_mode: Literal["derived", "manual_override"] = "derived"
        manual_value: float | None = None
        valve: ValveConfig | None = None
        if previous is not None:
            resistance_mode = previous.resistance.mode
            manual_value = previous.resistance.manual_value
            valve = previous.valve

        if equation_name is not None:
            resolved_equation_name = equation_name
        if resistance_parameter_name is not None:
            resolved_parameter_name = resistance_parameter_name

        self._line_hydraulic_configs[line_id] = LineHydraulicConfig(
            line_id=line_id,
            equation_name=resolved_equation_name,
            resistance_parameter_name=resolved_parameter_name,
            resistance=ResistanceConfig(
                mode=resistance_mode,
                radius_m=radius_m,
                length_m=length_m,
                manual_value=manual_value,
            ),
            valve=valve,
            pump=None if previous is None else previous.pump,
        )

    def configure_line_resistance(
        self,
        *,
        line_id: str,
        mode: Literal["derived", "manual_override"],
        manual_value: float | None,
    ) -> None:
        previous = self._line_hydraulic_configs.get(line_id)
        if previous is None:
            raise ValueError(
                "configure_line_resistance requires line geometry to be configured first"
            )

        self._line_hydraulic_configs[line_id] = LineHydraulicConfig(
            line_id=line_id,
            equation_name=previous.equation_name,
            resistance_parameter_name=previous.resistance_parameter_name,
            resistance=ResistanceConfig(
                mode=mode,
                radius_m=previous.resistance.radius_m,
                length_m=previous.resistance.length_m,
                manual_value=manual_value,
            ),
            valve=previous.valve,
            pump=previous.pump,
        )

    def attach_line_valve(
        self,
        *,
        line_id: str,
        valve_id: str,
        minimum_open_fraction: float,
        maximum_open_fraction: float,
        initial_open_fraction: float,
        equation_name: str | None,
        resistance_parameter_name: str | None,
    ) -> None:
        previous = self._line_hydraulic_configs.get(line_id)
        if previous is None:
            raise ValueError("attach_line_valve requires line geometry to be configured first")

        resolved_equation_name = previous.equation_name if equation_name is None else equation_name
        resolved_parameter_name = previous.resistance_parameter_name
        if resistance_parameter_name is not None:
            resolved_parameter_name = resistance_parameter_name
        elif previous.valve is None:
            resolved_parameter_name = "valve_resistance"

        self._line_hydraulic_configs[line_id] = LineHydraulicConfig(
            line_id=line_id,
            equation_name=resolved_equation_name,
            resistance_parameter_name=resolved_parameter_name,
            resistance=previous.resistance,
            valve=ValveConfig(
                valve_id=valve_id,
                minimum_open_fraction=minimum_open_fraction,
                maximum_open_fraction=maximum_open_fraction,
                initial_open_fraction=initial_open_fraction,
            ),
            pump=previous.pump,
        )

    def attach_line_pump(
        self,
        *,
        line_id: str,
        pump_id: str,
        initial_pump_speed: float,
        equation_name: str | None,
        pump_parameter_name: str | None,
    ) -> None:
        previous = self._line_hydraulic_configs.get(line_id)
        if previous is None:
            raise ValueError("attach_line_pump requires line geometry to be configured first")

        resolved_equation_name = previous.equation_name if equation_name is None else equation_name
        resolved_parameter_name = (
            previous.pump.pump_parameter_name if previous.pump is not None else "pump_speed"
        )
        if pump_parameter_name is not None:
            resolved_parameter_name = pump_parameter_name

        self._line_hydraulic_configs[line_id] = LineHydraulicConfig(
            line_id=line_id,
            equation_name=resolved_equation_name,
            resistance_parameter_name=previous.resistance_parameter_name,
            resistance=previous.resistance,
            valve=previous.valve,
            pump=LinePumpConfig(
                pump_id=pump_id,
                initial_pump_speed=initial_pump_speed,
                pump_parameter_name=resolved_parameter_name,
            ),
        )

    def attach_line_heat_actuator(
        self,
        *,
        line_id: str,
        heat_actuator_id: str,
        initial_heat_rate: float,
    ) -> None:
        self._line_heat_actuator_ids[line_id] = heat_actuator_id
        self._heat_actuator_rates[line_id] = initial_heat_rate

    def stage_valve_open_fraction_command(self, *, line_id: str, open_fraction: float) -> None:
        self._pending_valve_open_fractions[line_id] = open_fraction

    def stage_pump_speed_command(self, *, line_id: str, pump_speed: float) -> None:
        self._pending_pump_speeds[line_id] = pump_speed

    def stage_heat_actuator_rate_command(self, *, line_id: str, heat_rate: float) -> None:
        self._pending_heat_actuator_rates[line_id] = heat_rate

    def consume_pending_valve_open_fraction_commands(self) -> Mapping[str, float]:
        pending = dict(self.list_pending_valve_open_fractions())
        self._pending_valve_open_fractions = {}
        return pending

    def consume_pending_pump_speed_commands(self) -> Mapping[str, float]:
        pending = dict(self.list_pending_pump_speeds())
        self._pending_pump_speeds = {}
        return pending

    def consume_pending_heat_actuator_rate_commands(self) -> Mapping[str, float]:
        pending = dict(self.list_pending_heat_actuator_rates())
        self._pending_heat_actuator_rates = {}
        return pending

    def apply_heat_actuator_rate_commands(
        self,
        heat_rate_commands: Mapping[str, float],
        *,
        normalize_line_id: Callable[[object], str],
        assert_line_exists: Callable[[str], None],
    ) -> None:
        for line_id in sorted(heat_rate_commands):
            line_id_scalar = normalize_line_id(line_id)
            assert_line_exists(line_id_scalar)
            if line_id_scalar not in self._line_heat_actuator_ids:
                raise ValueError(f"line '{line_id_scalar}' does not have an attached heat actuator")
            self._heat_actuator_rates[line_id_scalar] = float(heat_rate_commands[line_id])

    def resolve_valve_command_line_id(
        self,
        *,
        line_id: str | None,
        valve_id: str | None,
        actuator_tag: str | None,
        normalize_line_id: Callable[[object], str],
        assert_line_exists: Callable[[str], None],
        compiled_valve_line_ids: Collection[str],
    ) -> str:
        selector_count = (
            int(line_id is not None) + int(valve_id is not None) + int(actuator_tag is not None)
        )
        if selector_count != 1:
            raise ValueError(
                "set_valve_open_fraction requires exactly one selector: 'line_id', 'valve_id', or 'actuator_tag'"
            )

        if actuator_tag is not None:
            return self._resolve_line_id_for_valve_id(
                self._parse_valve_id_from_actuator_tag(actuator_tag)
            )
        if valve_id is not None:
            return self._resolve_line_id_for_valve_id(
                self._require_non_empty_string_value(
                    value=valve_id,
                    error_message="valve_id must be a non-empty string",
                )
            )
        if line_id is None:
            raise RuntimeError("line_id selector is required")

        resolved_line_id = normalize_line_id(line_id)
        line_config = self._line_hydraulic_configs.get(resolved_line_id)
        if line_config is None:
            if resolved_line_id in compiled_valve_line_ids:
                return resolved_line_id
            assert_line_exists(resolved_line_id)
            line_config = self._line_hydraulic_configs.get(resolved_line_id)
        if line_config is None or line_config.valve is None:
            raise ValueError(f"line '{resolved_line_id}' does not have an attached valve")
        return resolved_line_id

    def resolve_pump_command_line_id(
        self,
        *,
        line_id: str | None,
        pump_id: str | None,
        actuator_tag: str | None,
        normalize_line_id: Callable[[object], str],
        assert_line_exists: Callable[[str], None],
    ) -> str:
        selector_count = (
            int(line_id is not None) + int(pump_id is not None) + int(actuator_tag is not None)
        )
        if selector_count != 1:
            raise ValueError(
                "set_pump_speed requires exactly one selector: 'line_id', 'pump_id', or 'actuator_tag'"
            )

        if actuator_tag is not None:
            return self._resolve_line_id_for_pump_id(
                self._parse_pump_id_from_actuator_tag(actuator_tag)
            )
        if pump_id is not None:
            return self._resolve_line_id_for_pump_id(
                self._require_non_empty_string_value(
                    value=pump_id,
                    error_message="pump_id must be a non-empty string",
                )
            )
        if line_id is None:
            raise RuntimeError("line_id selector is required")

        resolved_line_id = normalize_line_id(line_id)
        assert_line_exists(resolved_line_id)
        line_config = self._line_hydraulic_configs.get(resolved_line_id)
        if line_config is None or line_config.pump is None:
            raise ValueError(f"line '{resolved_line_id}' does not have an attached pump")
        return resolved_line_id

    def resolve_heat_command_line_id(
        self,
        *,
        line_id: str | None,
        heat_actuator_id: str | None,
        actuator_tag: str | None,
        normalize_line_id: Callable[[object], str],
        assert_line_exists: Callable[[str], None],
    ) -> str:
        selector_count = (
            int(line_id is not None)
            + int(heat_actuator_id is not None)
            + int(actuator_tag is not None)
        )
        if selector_count != 1:
            raise ValueError(
                "set_heat_actuator_rate requires exactly one selector: 'line_id', 'heat_actuator_id', or 'actuator_tag'"
            )

        if actuator_tag is not None:
            return self._resolve_line_id_for_heat_actuator_id(
                self._parse_heat_actuator_id_from_actuator_tag(actuator_tag)
            )
        if heat_actuator_id is not None:
            return self._resolve_line_id_for_heat_actuator_id(
                self._require_non_empty_string_value(
                    value=heat_actuator_id,
                    error_message="heat_actuator_id must be a non-empty string",
                )
            )
        if line_id is None:
            raise RuntimeError("line_id selector is required")

        resolved_line_id = normalize_line_id(line_id)
        assert_line_exists(resolved_line_id)
        if resolved_line_id not in self._line_heat_actuator_ids:
            raise ValueError(f"line '{resolved_line_id}' does not have an attached heat actuator")
        return resolved_line_id

    def remove_line(self, line_id: str) -> None:
        _ = self._line_hydraulic_configs.pop(line_id, None)
        _ = self._pending_valve_open_fractions.pop(line_id, None)
        _ = self._pending_pump_speeds.pop(line_id, None)
        _ = self._line_heat_actuator_ids.pop(line_id, None)
        _ = self._heat_actuator_rates.pop(line_id, None)
        _ = self._pending_heat_actuator_rates.pop(line_id, None)

    def _replace_equation_parameter(
        self,
        *,
        equation: ElementEquation,
        parameter_name: str,
        parameter_value: float,
    ) -> ElementEquation:
        updated_parameters = dict(equation.parameters)
        updated_parameters[parameter_name] = parameter_value
        return ElementEquation(
            name=equation.name,
            element=equation.element,
            inputs=equation.inputs,
            parameters=MappingProxyType(updated_parameters),
            unknown_name_map=equation.unknown_name_map,
            residual_name_map=equation.residual_name_map,
        )

    def _resolve_line_id_for_valve_id(self, valve_id: str) -> str:
        line_ids = tuple(
            sorted(
                line_key
                for line_key, config in self._line_hydraulic_configs.items()
                if config.valve is not None and config.valve.valve_id == valve_id
            )
        )
        if not line_ids:
            raise ValueError(f"unknown valve '{valve_id}'")
        if len(line_ids) > 1:
            raise ValueError(
                f"valve '{valve_id}' is attached to multiple lines {line_ids!r}; use line_id selector"
            )
        resolved_line_id = line_ids[0] if line_ids else None
        if resolved_line_id is None:
            raise RuntimeError(f"failed to resolve line for valve '{valve_id}'")
        return resolved_line_id

    def _resolve_line_id_for_pump_id(self, pump_id: str) -> str:
        line_ids = tuple(
            sorted(
                line_key
                for line_key, config in self._line_hydraulic_configs.items()
                if config.pump is not None and config.pump.pump_id == pump_id
            )
        )
        if not line_ids:
            raise ValueError(f"unknown pump '{pump_id}'")
        if len(line_ids) > 1:
            raise ValueError(
                f"pump '{pump_id}' is attached to multiple lines {line_ids!r}; use line_id selector"
            )
        resolved_line_id = line_ids[0] if line_ids else None
        if resolved_line_id is None:
            raise RuntimeError(f"failed to resolve line for pump '{pump_id}'")
        return resolved_line_id

    def _resolve_line_id_for_heat_actuator_id(self, heat_actuator_id: str) -> str:
        line_ids = tuple(
            sorted(
                line_key
                for line_key, configured_heat_actuator_id in self._line_heat_actuator_ids.items()
                if configured_heat_actuator_id == heat_actuator_id
            )
        )
        if not line_ids:
            raise ValueError(f"unknown heat actuator '{heat_actuator_id}'")
        if len(line_ids) > 1:
            raise ValueError(
                "heat actuator '{}' is attached to multiple lines {!r}; use line_id selector".format(
                    heat_actuator_id,
                    line_ids,
                )
            )
        resolved_line_id = line_ids[0] if line_ids else None
        if resolved_line_id is None:
            raise RuntimeError(f"failed to resolve line for heat actuator '{heat_actuator_id}'")
        return resolved_line_id

    def _parse_valve_id_from_actuator_tag(self, actuator_tag: object) -> str:
        return self._parse_namespaced_id(
            actuator_tag=actuator_tag,
            namespace_prefix=_VALVE_ACTUATOR_NAMESPACE_PREFIX,
            error_message=(
                "set_valve_open_fraction field 'actuator_tag' must match canonical "
                + "valve actuator tag 'actuator/valve/<id>'"
            ),
        )

    def _parse_pump_id_from_actuator_tag(self, actuator_tag: object) -> str:
        return self._parse_namespaced_id(
            actuator_tag=actuator_tag,
            namespace_prefix=_PUMP_ACTUATOR_NAMESPACE_PREFIX,
            error_message=(
                "set_pump_speed field 'actuator_tag' must match canonical "
                + "pump actuator tag 'actuator/pump/<id>'"
            ),
        )

    def _parse_heat_actuator_id_from_actuator_tag(self, actuator_tag: object) -> str:
        return self._parse_namespaced_id(
            actuator_tag=actuator_tag,
            namespace_prefix=_HEAT_ACTUATOR_NAMESPACE_PREFIX,
            error_message=(
                "set_heat_actuator_rate field 'actuator_tag' must match canonical "
                + "heat actuator tag 'actuator/heat/<id>'"
            ),
        )

    def _parse_namespaced_id(
        self,
        *,
        actuator_tag: object,
        namespace_prefix: str,
        error_message: str,
    ) -> str:
        normalized = self._require_non_empty_string_value(
            value=actuator_tag,
            error_message=error_message,
        )
        if not normalized.startswith(namespace_prefix):
            raise ValueError(error_message)
        namespaced_id = normalized.removeprefix(namespace_prefix).strip()
        if not namespaced_id:
            raise ValueError(error_message)
        return namespaced_id

    def _require_non_empty_string_value(self, *, value: object, error_message: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(error_message)
        return value.strip()


__all__ = [
    "LineHydraulicConfig",
    "LineHydraulicConfigManager",
    "LineHydraulicConfigManagerSnapshot",
    "LinePumpConfig",
]
