from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportMissingImports=false

from typing import Annotated, Any, ClassVar, override

import numpy as np
from numpy.typing import NDArray
from pydantic import PrivateAttr

from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import (
    AlgebraicProcessModel,
    UnitProcessPorts,
)
from modular_simulation.thermodynamics.hydraulic_adapters import pipe_hydraulic_element_for_outlet
from modular_simulation.thermodynamics.hydraulic_participation import (
    HydraulicBalancingGroupSpec,
    HydraulicParticipationSpec,
    HydraulicPortSpec,
    HydraulicRelationSpec,
    HydraulicScalarStateRef,
)
from modular_simulation.thermodynamics.stream import PortAttributeMap, StreamData
from modular_simulation.utils.typing import ArrayIndex, Seconds

_PORTS = UnitProcessPorts(inlets=("inlet",), outlets=("reject_outlet",))

# Canonical default species ordering used by standalone tests.
# This default matches SimulationRuntimeContext.create(species_names=["methane","ethane"]).
_DEFAULT_SPECIES_NAMES: tuple[str, ...] = ("methane", "ethane")


class QualityControlLab(AlgebraicProcessModel):
    """A quality-control inspection unit that tracks cumulative accepted progress.

    Material enters through ``inlet`` and exits through ``reject_outlet``
    regardless of whether it passes the purity check.  When the tracked
    component's mole fraction meets or exceeds ``minimum_purity_mol_fraction``,
    the entire incoming molar feed for that step is credited to
    ``accepted_progress_mol``.

    Constructor parameters
    ----------------------
    tracked_component_id : str
        Name of the species whose purity drives the pass/fail decision.
    minimum_purity_mol_fraction : float
        Minimum mole fraction (0 < value ≤ 1) required to accept the stream.
    species_names : tuple[str, ...], optional
        Ordered tuple of species names matching the inlet composition vector.
        Defaults to ``("methane", "ethane")`` for backward compatibility with
        the canonical test context.  Override via the constructor or
        ``set_species_context``.
    """

    _INLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "inlet": PortAttributeMap(
            flow="inlet_flow",
            temperature="inlet_temperature",
            pressure="inlet_pressure",
            composition="inlet_composition",
        )
    }
    _OUTLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "reject_outlet": PortAttributeMap(
            flow="reject_outlet_flow",
            temperature="reject_outlet_temperature",
            pressure="reject_outlet_pressure",
            composition="reject_outlet_composition",
        )
    }

    # --- BOUNDARY states ---
    inlet_flow: Annotated[
        float,
        M(type=T.BOUNDARY, unit="mol/s", description="inlet molar flow rate"),
    ] = 0.0
    inlet_temperature: Annotated[
        float,
        M(type=T.BOUNDARY, unit="K", description="inlet temperature"),
    ] = 298.15
    inlet_pressure: Annotated[
        float,
        M(type=T.BOUNDARY, unit="Pa", description="inlet pressure"),
    ] = 101325.0
    inlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="", description="inlet mole fractions"),
    ] = np.zeros(0, dtype=np.float64)

    # --- ALGEBRAIC states ---
    reject_outlet_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="reject outlet molar flow rate"),
    ] = 0.0
    reject_outlet_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="reject outlet temperature"),
    ] = 298.15
    reject_outlet_pressure: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="reject outlet pressure"),
    ] = 101325.0
    reject_outlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="reject outlet mole fractions"),
    ] = np.zeros(0, dtype=np.float64)

    # --- Configuration fields ---
    # minimum_purity_mol_fraction is numeric → can use StateMetadata T.CONSTANT safely.
    # tracked_component_id is a string → must NOT be a pydantic field (framework requires all
    # pydantic fields to be numeric state vectors via StateMetadata). Store as PrivateAttr.
    minimum_purity_mol_fraction: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="",
            description="minimum mole fraction required to accept the stream",
        ),
    ] = 0.95

    # --- Private configuration state (not pydantic fields) ---
    _tracked_component_id: str = PrivateAttr(default="methane")
    _accepted_progress_mol: float = PrivateAttr(default=0.0)
    _species_names: tuple[str, ...] = PrivateAttr(default_factory=lambda: _DEFAULT_SPECIES_NAMES)
    _inlet_species_ids: tuple[str, ...] | None = PrivateAttr(default=None)

    def __init__(self, **data: Any) -> None:
        # Pop non-field kwargs before passing to pydantic.
        species_names_raw = data.pop("species_names", None)
        tracked_component_id_raw = data.pop("tracked_component_id", "methane")
        super().__init__(**data)
        self._tracked_component_id = str(tracked_component_id_raw).strip()
        if species_names_raw is not None:
            self._species_names = tuple(str(name).strip() for name in species_names_raw)

    # --- Ports ---

    @property
    def ports(self) -> UnitProcessPorts:
        return _PORTS

    # --- Public properties ---

    @property
    def tracked_component_id(self) -> str:
        """Species name used to drive the pass/fail decision."""
        return self._tracked_component_id

    @property
    def accepted_progress_mol(self) -> float:
        """Cumulative molar progress from accepted streams (mol)."""
        return self._accepted_progress_mol

    # --- Species context injection (called by flowsheet or tests) ---

    def set_species_context(self, species_names: tuple[str, ...]) -> None:
        """Update the ordered species name list for tracked-component resolution."""
        self._species_names = tuple(str(name).strip() for name in species_names)

    # --- Hydraulic participation ---

    @property
    @override
    def hydraulic_participation(self) -> HydraulicParticipationSpec:
        return HydraulicParticipationSpec(
            ports={
                "inlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef(state="inlet_pressure"),
                ),
                "reject_outlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef(state="reject_outlet_pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(
                    name="quality_control_lab_flow_balance",
                    ports=("inlet", "reject_outlet"),
                ),
            ),
            relations=(
                HydraulicRelationSpec(
                    name="quality_control_lab_pressure_equal",
                    kind="pressure_equal",
                    ports=("inlet", "reject_outlet"),
                ),
            ),
        )

    # --- Stream I/O ---

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        if port_name not in self.ports.inlets:
            valid_ports = ", ".join(self.ports.inlets)
            raise ValueError(
                f"Invalid inlet port '{port_name}' for {type(self).__name__}. "
                f"Valid inlet ports: {valid_ports}."
            )
        port_map = self._INLET_MAP[port_name]
        setattr(self, port_map.flow, float(stream.molar_flow_rate))
        setattr(self, port_map.temperature, float(stream.temperature))
        setattr(self, port_map.pressure, float(stream.pressure))
        setattr(self, port_map.composition, np.asarray(stream.mole_fractions, dtype=np.float64))
        self._inlet_species_ids = (
            tuple(str(species_id).strip() for species_id in stream.species_ids)
            if stream.species_ids is not None
            else None
        )

    def get_outlet_stream(self, port_name: str) -> StreamData:
        if port_name not in self.ports.outlets:
            valid_ports = ", ".join(self.ports.outlets)
            raise ValueError(
                f"Invalid outlet port '{port_name}' for {type(self).__name__}. "
                f"Valid outlet ports: {valid_ports}."
            )
        port_map = self._OUTLET_MAP[port_name]
        composition_array = np.asarray(getattr(self, port_map.composition), dtype=np.float64)
        composition: tuple[float, ...]
        if composition_array.size > 0:
            composition = tuple(float(v) for v in composition_array)
        else:
            composition = (1.0,)
        return StreamData(
            temperature=float(getattr(self, port_map.temperature)),
            pressure=float(getattr(self, port_map.pressure)),
            mole_fractions=composition,
            molar_flow_rate=float(getattr(self, port_map.flow)),
            species_ids=self._inlet_species_ids,
        )

    def to_hydraulic_element(self, port_name: str):
        return pipe_hydraulic_element_for_outlet(
            unit_name=type(self).__name__,
            port_name=port_name,
            allowed_outlet_ports=self.ports.outlets,
        )

    # --- Step: self-contained progress tracking ---

    @override
    def step(self, dt: Seconds) -> None:
        """Advance the lab by one simulation step.

        1. Determine the tracked-component mole fraction from ``inlet_composition``.
        2. If fraction >= minimum_purity_mol_fraction: credit the entire incoming
           molar amount to ``accepted_progress_mol``.
        3. Route ALL material through ``reject_outlet`` (the lab has a single outlet).
        """
        inlet_flow = max(0.0, float(self.inlet_flow))
        dt_scalar = float(dt)

        # Resolve the index for the tracked component.
        tracked_index = self._resolve_tracked_index()

        # Determine tracked purity.
        inlet_comp = np.asarray(self.inlet_composition, dtype=np.float64).reshape(-1)
        if tracked_index is not None and inlet_comp.size > tracked_index:
            tracked_purity = float(inlet_comp[tracked_index])
        else:
            # No species context available; cannot resolve — purity unknown → reject.
            tracked_purity = 0.0

        # Credit decision: whole-stream credit only (no bonus above threshold).
        if tracked_purity >= float(self.minimum_purity_mol_fraction):
            incoming_mol = inlet_flow * dt_scalar
            self._accepted_progress_mol += incoming_mol

        # Route all material through reject_outlet (no material is destroyed).
        self.reject_outlet_flow = inlet_flow
        self.reject_outlet_temperature = float(self.inlet_temperature)
        self.reject_outlet_pressure = float(self.inlet_pressure)
        if inlet_comp.size > 0:
            self.reject_outlet_composition = inlet_comp.copy()

        self.t += dt_scalar

    def _resolve_tracked_index(self) -> int | None:
        """Return the composition vector index for tracked_component_id, or None."""
        component_id = str(self.tracked_component_id).strip()
        names = self._inlet_species_ids or self._species_names
        for index, name in enumerate(names):
            if name.strip() == component_id:
                return index
        # Fallback: try integer parsing.
        if component_id.isdigit():
            return int(component_id)
        return None

    # --- Required abstract stubs ---

    @staticmethod
    @override
    def calculate_algebraic_values(
        y: NDArray[np.float64],
        u: NDArray[np.float64],
        k: NDArray[np.float64],
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
        algebraic_size: int,
    ) -> NDArray[np.float64]:
        # Algebraic computation is handled in step(); this stub satisfies
        # the abstract method contract for the AlgebraicProcessModel framework.
        return np.zeros(algebraic_size, dtype=np.float64)


__all__ = ["QualityControlLab"]
