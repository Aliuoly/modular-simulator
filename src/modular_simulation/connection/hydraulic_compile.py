from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Literal, Protocol, cast

import numpy as np
from numpy.typing import NDArray

import modular_simulation.connection.hydraulic_solver as hydraulic_solver
from modular_simulation.connection.domain_contracts import ResistanceConfig, ValveConfig
from modular_simulation.connection.hydraulic_solver import (
    HydraulicSolveResult,
    HydraulicSystemDefinition,
    build_index_maps,
    solve_hydraulic_system,
)


@dataclass(frozen=True)
class GraphCompileDiagnostic:
    code: str
    message: str
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        ordered_details = tuple(sorted((str(key), str(value)) for key, value in self.details))
        object.__setattr__(self, "details", ordered_details)


class GraphCompileError(ValueError):
    diagnostics: tuple[GraphCompileDiagnostic, ...]

    def __init__(self, diagnostics: tuple[GraphCompileDiagnostic, ...]):
        if not diagnostics:
            raise ValueError("GraphCompileError requires at least one diagnostic")
        self.diagnostics = tuple(
            sorted(diagnostics, key=lambda item: (item.code, item.message, item.details))
        )
        super().__init__(_format_diagnostic_message(self.diagnostics))


@dataclass(frozen=True)
class CompiledValveHydraulicState:
    line_id: str
    valve_id: str
    equation_name: str
    resistance_parameter_name: str
    resistance_when_open: float
    minimum_open_fraction: float
    maximum_open_fraction: float
    current_open_fraction: float


def _empty_valve_state_mapping() -> Mapping[str, CompiledValveHydraulicState]:
    return MappingProxyType({})


@dataclass(frozen=True)
class CompiledHydraulicGraph:
    graph_revision: str
    system: HydraulicSystemDefinition
    unknown_order: tuple[str, ...]
    residual_order: tuple[str, ...]
    valve_state_by_line: Mapping[str, CompiledValveHydraulicState] = field(
        default_factory=_empty_valve_state_mapping
    )

    def build_solver_inputs(self) -> HydraulicSolverInputs:
        system = HydraulicSystemDefinition(
            equations=self.system.equations,
            linear_residual_equations=self.system.linear_residual_equations,
            unknown_order=self.unknown_order,
            residual_order=self.residual_order,
        )
        unknown_index_map, residual_index_map = build_index_maps(system)
        unknown_order = tuple(sorted(unknown_index_map, key=unknown_index_map.__getitem__))
        residual_order = tuple(sorted(residual_index_map, key=residual_index_map.__getitem__))
        return HydraulicSolverInputs(
            graph_revision=self.graph_revision,
            system=system,
            unknown_order=unknown_order,
            residual_order=residual_order,
            unknown_index_map=unknown_index_map,
            residual_index_map=residual_index_map,
        )

    def solve(
        self,
        *,
        initial_unknowns: Mapping[str, float] | None = None,
        warm_start: NDArray[np.float64] | None = None,
        valve_commands: Mapping[str, float] | None = None,
        tolerance: float = 1.0e-8,
        max_iterations: int = 25,
        min_damping: float = 1.0e-6,
    ) -> HydraulicSolveResult:
        compiled_for_solve = self
        if valve_commands:
            compiled_for_solve = self.with_valve_commands(valve_commands)

        solver_inputs = compiled_for_solve.build_solver_inputs()
        return solve_hydraulic_system(
            solver_inputs.system,
            initial_unknowns=initial_unknowns,
            warm_start=warm_start,
            tolerance=tolerance,
            max_iterations=max_iterations,
            min_damping=min_damping,
        )

    def with_valve_commands(self, valve_commands: Mapping[str, float]) -> CompiledHydraulicGraph:
        if not valve_commands:
            return self

        normalized_valve_state_by_line = _normalize_compiled_valve_states(
            valve_state_by_line=self.valve_state_by_line
        )
        next_valve_state_by_line: dict[str, CompiledValveHydraulicState] = dict(
            normalized_valve_state_by_line
        )

        for line_id in sorted(valve_commands):
            command_open_fraction = float(valve_commands[line_id])
            state = normalized_valve_state_by_line.get(line_id)
            if state is None:
                known_lines = tuple(sorted(normalized_valve_state_by_line.keys()))
                raise ValueError(
                    "unknown valve command line_id {!r}; known valve lines are {!r}".format(
                        line_id,
                        known_lines,
                    )
                )
            _validate_valve_open_fraction_command(
                line_id=line_id,
                open_fraction=command_open_fraction,
                state=state,
            )
            next_valve_state_by_line[line_id] = CompiledValveHydraulicState(
                line_id=state.line_id,
                valve_id=state.valve_id,
                equation_name=state.equation_name,
                resistance_parameter_name=state.resistance_parameter_name,
                resistance_when_open=state.resistance_when_open,
                minimum_open_fraction=state.minimum_open_fraction,
                maximum_open_fraction=state.maximum_open_fraction,
                current_open_fraction=command_open_fraction,
            )

        normalized_next_valve_state_by_line = _normalize_compiled_valve_states(
            valve_state_by_line=next_valve_state_by_line
        )
        system = _apply_compiled_valve_states_to_system(
            system=self.system,
            valve_state_by_line=normalized_next_valve_state_by_line,
        )
        return CompiledHydraulicGraph(
            graph_revision=self.graph_revision,
            system=system,
            unknown_order=self.unknown_order,
            residual_order=self.residual_order,
            valve_state_by_line=normalized_next_valve_state_by_line,
        )


@dataclass(frozen=True)
class HydraulicSolverInputs:
    graph_revision: str
    system: HydraulicSystemDefinition
    unknown_order: tuple[str, ...]
    residual_order: tuple[str, ...]
    unknown_index_map: Mapping[str, int]
    residual_index_map: Mapping[str, int]


@dataclass(frozen=True)
class ResolvedLineResistance:
    line_id: str
    active_value: float
    derived_value: float
    provenance: Literal["derived", "manual_override"]


class _SolvabilityValidator(Protocol):
    def __call__(
        self,
        system: HydraulicSystemDefinition,
        *,
        unknown_index_map: Mapping[str, int],
        residual_index_map: Mapping[str, int],
    ) -> None: ...


class HydraulicCompileLifecycle:
    def __init__(self, active_compiled: CompiledHydraulicGraph | None = None):
        self._active_compiled: CompiledHydraulicGraph | None
        self._active_compiled = active_compiled

    @property
    def active_compiled(self) -> CompiledHydraulicGraph | None:
        return self._active_compiled

    @property
    def active_graph_revision(self) -> str | None:
        if self._active_compiled is None:
            return None
        return self._active_compiled.graph_revision

    def compile(
        self,
        *,
        system: HydraulicSystemDefinition,
        graph_revision: str,
        valve_state_by_line: Mapping[str, CompiledValveHydraulicState] | None = None,
    ) -> CompiledHydraulicGraph:
        return compile_hydraulic_graph(
            system=system,
            graph_revision=graph_revision,
            valve_state_by_line=valve_state_by_line,
        )

    def compile_candidate(
        self,
        *,
        system: HydraulicSystemDefinition,
        graph_revision: str,
        valve_state_by_line: Mapping[str, CompiledValveHydraulicState] | None = None,
    ) -> CompiledHydraulicGraph:
        return compile_hydraulic_graph(
            system=system,
            graph_revision=graph_revision,
            valve_state_by_line=valve_state_by_line,
        )

    def activate(self, compiled: CompiledHydraulicGraph) -> None:
        self._active_compiled = compiled


def validate_hydraulic_graph(
    *,
    system: HydraulicSystemDefinition,
) -> tuple[GraphCompileDiagnostic, ...]:
    try:
        unknown_index_map, residual_index_map = build_index_maps(system)
    except ValueError as error:
        return (
            GraphCompileDiagnostic(
                code="index_definition_invalid",
                message=str(error),
            ),
        )

    unknown_count = len(unknown_index_map)
    residual_count = len(residual_index_map)
    if unknown_count != residual_count:
        return (
            GraphCompileDiagnostic(
                code="invalid_cardinality",
                message="hydraulic system must be square for compile validation",
                details=(
                    ("unknown_count", str(unknown_count)),
                    ("residual_count", str(residual_count)),
                ),
            ),
        )

    if unknown_count == 0:
        return (
            GraphCompileDiagnostic(
                code="invalid_topology",
                message="hydraulic system has no unknowns",
            ),
        )

    solvability_validator = cast(
        _SolvabilityValidator,
        getattr(hydraulic_solver, "_validate_solvability"),
    )
    try:
        solvability_validator(
            system,
            unknown_index_map=unknown_index_map,
            residual_index_map=residual_index_map,
        )
    except ValueError as error:
        return (_solvability_error_to_diagnostic(message=str(error)),)

    return ()


def compile_hydraulic_graph(
    *,
    system: HydraulicSystemDefinition,
    graph_revision: str,
    valve_state_by_line: Mapping[str, CompiledValveHydraulicState] | None = None,
) -> CompiledHydraulicGraph:
    diagnostics = validate_hydraulic_graph(system=system)
    if diagnostics:
        raise GraphCompileError(diagnostics)

    normalized_valve_state_by_line = _normalize_compiled_valve_states(
        valve_state_by_line=valve_state_by_line
    )
    system_for_compile = _apply_compiled_valve_states_to_system(
        system=system,
        valve_state_by_line=normalized_valve_state_by_line,
    )

    unknown_index_map, residual_index_map = build_index_maps(system_for_compile)
    unknown_order = tuple(sorted(unknown_index_map, key=unknown_index_map.__getitem__))
    residual_order = tuple(sorted(residual_index_map, key=residual_index_map.__getitem__))
    return CompiledHydraulicGraph(
        graph_revision=graph_revision,
        system=system_for_compile,
        unknown_order=unknown_order,
        residual_order=residual_order,
        valve_state_by_line=normalized_valve_state_by_line,
    )


def build_hydraulic_solver_inputs(compiled: CompiledHydraulicGraph) -> HydraulicSolverInputs:
    return compiled.build_solver_inputs()


def solve_compiled_hydraulic_graph(
    compiled: CompiledHydraulicGraph,
    *,
    initial_unknowns: Mapping[str, float] | None = None,
    warm_start: NDArray[np.float64] | None = None,
    valve_commands: Mapping[str, float] | None = None,
    tolerance: float = 1.0e-8,
    max_iterations: int = 25,
    min_damping: float = 1.0e-6,
) -> HydraulicSolveResult:
    return compiled.solve(
        initial_unknowns=initial_unknowns,
        warm_start=warm_start,
        valve_commands=valve_commands,
        tolerance=tolerance,
        max_iterations=max_iterations,
        min_damping=min_damping,
    )


def resolve_line_resistance(
    *,
    line_id: str,
    resistance: ResistanceConfig,
    fluid_factor: float | None = None,
) -> ResolvedLineResistance:
    diagnostics = _validate_line_resistance_inputs(
        line_id=line_id,
        resistance=resistance,
        fluid_factor=fluid_factor,
    )
    if diagnostics:
        raise GraphCompileError(diagnostics)

    radius_m = resistance.radius_m
    length_m = resistance.length_m
    if radius_m is None or length_m is None:
        raise RuntimeError("line resistance validation must ensure geometry exists")
    fluid_scale = 1.0 if fluid_factor is None else fluid_factor

    derived_value = fluid_scale * (length_m / (radius_m**4))
    if not isfinite(derived_value):
        raise GraphCompileError(
            (
                GraphCompileDiagnostic(
                    code="line_resistance_not_finite",
                    message="resolved line resistance is not finite",
                    details=(
                        ("line_id", line_id),
                        ("radius_m", str(radius_m)),
                        ("length_m", str(length_m)),
                        ("fluid_factor", str(fluid_scale)),
                    ),
                ),
            )
        )

    if resistance.manual_value is not None:
        return ResolvedLineResistance(
            line_id=line_id,
            active_value=resistance.manual_value,
            derived_value=derived_value,
            provenance="manual_override",
        )

    return ResolvedLineResistance(
        line_id=line_id,
        active_value=derived_value,
        derived_value=derived_value,
        provenance="derived",
    )


def compile_valve_hydraulic_state(
    *,
    line_id: str,
    equation_name: str,
    resolved_resistance: ResolvedLineResistance,
    valve: ValveConfig,
    resistance_parameter_name: str = "valve_resistance",
) -> CompiledValveHydraulicState:
    diagnostics = _validate_valve_hydraulic_inputs(
        line_id=line_id,
        equation_name=equation_name,
        resolved_resistance=resolved_resistance,
        valve=valve,
        resistance_parameter_name=resistance_parameter_name,
    )
    if diagnostics:
        raise GraphCompileError(diagnostics)

    return CompiledValveHydraulicState(
        line_id=line_id,
        valve_id=valve.valve_id,
        equation_name=equation_name,
        resistance_parameter_name=resistance_parameter_name,
        resistance_when_open=resolved_resistance.active_value,
        minimum_open_fraction=valve.minimum_open_fraction,
        maximum_open_fraction=valve.maximum_open_fraction,
        current_open_fraction=valve.initial_open_fraction,
    )


def calculate_effective_valve_resistance(
    *,
    resistance_when_open: float,
    open_fraction: float,
    minimum_open_fraction: float,
    maximum_open_fraction: float,
    min_relative_open_fraction: float = 1.0e-3,
) -> float:
    if not isfinite(resistance_when_open) or resistance_when_open < 0.0:
        raise ValueError("valve resistance_when_open must be a finite non-negative value")
    if not isfinite(open_fraction):
        raise ValueError("valve open_fraction must be finite")
    if not isfinite(minimum_open_fraction) or not isfinite(maximum_open_fraction):
        raise ValueError("valve open range must be finite")
    if minimum_open_fraction > maximum_open_fraction:
        raise ValueError("valve open range is invalid: minimum must be <= maximum")
    if open_fraction < minimum_open_fraction or open_fraction > maximum_open_fraction:
        raise ValueError("valve open_fraction must be within configured min/max bounds")
    if not isfinite(min_relative_open_fraction) or min_relative_open_fraction <= 0.0:
        raise ValueError("min_relative_open_fraction must be finite and positive")

    open_span = maximum_open_fraction - minimum_open_fraction
    if open_span <= 0.0:
        normalized_open_fraction = 1.0
    else:
        normalized_open_fraction = (open_fraction - minimum_open_fraction) / open_span

    throttling_fraction = max(normalized_open_fraction, min_relative_open_fraction)
    effective_resistance = resistance_when_open / (throttling_fraction * throttling_fraction)
    if not isfinite(effective_resistance):
        raise ValueError("effective valve resistance is not finite")
    return effective_resistance


def apply_valve_commands_to_compiled_graph(
    *,
    compiled: CompiledHydraulicGraph,
    valve_commands: Mapping[str, float],
) -> CompiledHydraulicGraph:
    return compiled.with_valve_commands(valve_commands)


def _solvability_error_to_diagnostic(*, message: str) -> GraphCompileDiagnostic:
    normalized = message.lower()
    if "missing pressure reference" in normalized:
        code = "missing_pressure_reference"
    elif "dof mismatch" in normalized:
        code = "invalid_topology"
    else:
        code = "invalid_topology"
    return GraphCompileDiagnostic(code=code, message=message)


def _format_diagnostic_message(diagnostics: tuple[GraphCompileDiagnostic, ...]) -> str:
    formatted: list[str] = []
    for diagnostic in diagnostics:
        if diagnostic.details:
            detail_payload = ", ".join(f"{key}={value}" for key, value in diagnostic.details)
            formatted.append(f"{diagnostic.code}: {diagnostic.message} ({detail_payload})")
        else:
            formatted.append(f"{diagnostic.code}: {diagnostic.message}")
    return "graph compile validation failed: " + " | ".join(formatted)


def _validate_line_resistance_inputs(
    *,
    line_id: str,
    resistance: ResistanceConfig,
    fluid_factor: float | None,
) -> tuple[GraphCompileDiagnostic, ...]:
    diagnostics: list[GraphCompileDiagnostic] = []

    radius_m = resistance.radius_m
    length_m = resistance.length_m
    if radius_m is None or not isfinite(radius_m) or radius_m <= 0.0:
        diagnostics.append(
            GraphCompileDiagnostic(
                code="invalid_line_geometry",
                message="line resistance radius must be a positive finite value",
                details=(("line_id", line_id), ("radius_m", str(radius_m))),
            )
        )
    if length_m is None or not isfinite(length_m) or length_m <= 0.0:
        diagnostics.append(
            GraphCompileDiagnostic(
                code="invalid_line_geometry",
                message="line resistance length must be a positive finite value",
                details=(("line_id", line_id), ("length_m", str(length_m))),
            )
        )

    manual_value = resistance.manual_value
    if manual_value is not None and (not isfinite(manual_value) or manual_value < 0.0):
        diagnostics.append(
            GraphCompileDiagnostic(
                code="invalid_manual_override",
                message="line resistance manual override must be a finite non-negative value",
                details=(("line_id", line_id), ("manual_value", str(manual_value))),
            )
        )

    if fluid_factor is not None and (not isfinite(fluid_factor) or fluid_factor <= 0.0):
        diagnostics.append(
            GraphCompileDiagnostic(
                code="invalid_fluid_factor",
                message="line resistance fluid_factor must be a positive finite value when provided",
                details=(("line_id", line_id), ("fluid_factor", str(fluid_factor))),
            )
        )

    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message, item.details)))


def _normalize_compiled_valve_states(
    *, valve_state_by_line: Mapping[str, CompiledValveHydraulicState] | None
) -> Mapping[str, CompiledValveHydraulicState]:
    if valve_state_by_line is None:
        return MappingProxyType({})

    normalized: dict[str, CompiledValveHydraulicState] = {}
    for line_id in sorted(valve_state_by_line):
        normalized[line_id] = valve_state_by_line[line_id]
    return MappingProxyType(normalized)


def _apply_compiled_valve_states_to_system(
    *,
    system: HydraulicSystemDefinition,
    valve_state_by_line: Mapping[str, CompiledValveHydraulicState],
) -> HydraulicSystemDefinition:
    if not valve_state_by_line:
        return system

    equations = list(system.equations)
    equation_name_to_index: dict[str, int] = {}
    for index, equation in enumerate(equations):
        if equation.name in equation_name_to_index:
            raise ValueError(
                "valve integration requires unique equation names; duplicate {!r}".format(
                    equation.name
                )
            )
        equation_name_to_index[equation.name] = index

    for line_id in sorted(valve_state_by_line):
        state = valve_state_by_line[line_id]
        equation_index = equation_name_to_index.get(state.equation_name)
        if equation_index is None:
            raise ValueError(
                "valve mapping for line {!r} references unknown equation {!r}".format(
                    line_id,
                    state.equation_name,
                )
            )
        equation = equations[equation_index]
        parameter_name = state.resistance_parameter_name
        if parameter_name not in equation.element.parameter_spec.names:
            raise ValueError(
                "valve mapping for line {!r} references unsupported parameter {!r} for equation {!r}".format(
                    line_id,
                    parameter_name,
                    equation.name,
                )
            )

        effective_resistance = calculate_effective_valve_resistance(
            resistance_when_open=state.resistance_when_open,
            open_fraction=state.current_open_fraction,
            minimum_open_fraction=state.minimum_open_fraction,
            maximum_open_fraction=state.maximum_open_fraction,
        )
        updated_parameters = dict(equation.parameters)
        updated_parameters[parameter_name] = effective_resistance
        equations[equation_index] = hydraulic_solver.ElementEquation(
            name=equation.name,
            element=equation.element,
            inputs=equation.inputs,
            parameters=MappingProxyType(updated_parameters),
            unknown_name_map=equation.unknown_name_map,
            residual_name_map=equation.residual_name_map,
        )

    return HydraulicSystemDefinition(
        equations=tuple(equations),
        linear_residual_equations=system.linear_residual_equations,
        unknown_order=system.unknown_order,
        residual_order=system.residual_order,
    )


def _validate_valve_open_fraction_command(
    *,
    line_id: str,
    open_fraction: float,
    state: CompiledValveHydraulicState,
) -> None:
    if not isfinite(open_fraction):
        raise ValueError("valve command for line {!r} must be finite".format(line_id))
    if open_fraction < state.minimum_open_fraction or open_fraction > state.maximum_open_fraction:
        raise ValueError(
            "valve command for line {!r} must be within [{}, {}], got {}".format(
                line_id,
                state.minimum_open_fraction,
                state.maximum_open_fraction,
                open_fraction,
            )
        )


def _validate_valve_hydraulic_inputs(
    *,
    line_id: str,
    equation_name: str,
    resolved_resistance: ResolvedLineResistance,
    valve: ValveConfig,
    resistance_parameter_name: str,
) -> tuple[GraphCompileDiagnostic, ...]:
    diagnostics: list[GraphCompileDiagnostic] = []
    if not equation_name.strip():
        diagnostics.append(
            GraphCompileDiagnostic(
                code="invalid_valve_mapping",
                message="valve equation_name must be a non-empty string",
                details=(("line_id", line_id), ("equation_name", equation_name)),
            )
        )
    if not resistance_parameter_name.strip():
        diagnostics.append(
            GraphCompileDiagnostic(
                code="invalid_valve_mapping",
                message="valve resistance parameter name must be a non-empty string",
                details=(("line_id", line_id),),
            )
        )
    if not isfinite(resolved_resistance.active_value) or resolved_resistance.active_value < 0.0:
        diagnostics.append(
            GraphCompileDiagnostic(
                code="invalid_valve_mapping",
                message="valve resistance_when_open must be a finite non-negative value",
                details=(
                    ("line_id", line_id),
                    ("active_value", str(resolved_resistance.active_value)),
                ),
            )
        )
    if not isfinite(valve.minimum_open_fraction) or not isfinite(valve.maximum_open_fraction):
        diagnostics.append(
            GraphCompileDiagnostic(
                code="invalid_valve_mapping",
                message="valve open bounds must be finite",
                details=(
                    ("line_id", line_id),
                    ("minimum_open_fraction", str(valve.minimum_open_fraction)),
                    ("maximum_open_fraction", str(valve.maximum_open_fraction)),
                ),
            )
        )
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message, item.details)))


__all__ = [
    "CompiledValveHydraulicState",
    "CompiledHydraulicGraph",
    "calculate_effective_valve_resistance",
    "compile_valve_hydraulic_state",
    "GraphCompileDiagnostic",
    "GraphCompileError",
    "HydraulicSolverInputs",
    "HydraulicCompileLifecycle",
    "ResolvedLineResistance",
    "resolve_line_resistance",
    "validate_hydraulic_graph",
]
