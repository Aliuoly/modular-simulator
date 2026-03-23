from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportMissingImports=false

from typing import Annotated, ClassVar, override

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

_PORTS = UnitProcessPorts(inlets=("inlet",), outlets=("outlet",))


class HoldingTank(AlgebraicProcessModel):
    """A simple storage tank that accumulates molar holdup.

    Outlet flow comes only from stored holdup; no material is invented.
    Each step, the entire holdup is discharged over dt seconds, then
    new incoming material is accumulated.
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
        "outlet": PortAttributeMap(
            flow="outlet_flow",
            temperature="outlet_temperature",
            pressure="outlet_pressure",
            composition="outlet_composition",
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
    outlet_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="outlet molar flow rate"),
    ] = 0.0
    outlet_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="outlet temperature"),
    ] = 298.15
    outlet_pressure: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="outlet pressure"),
    ] = 101325.0
    outlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="outlet mole fractions"),
    ] = np.zeros(0, dtype=np.float64)

    # Internal holdup: stored as a private attr, exposed via property.
    _holdup_mol: float = PrivateAttr(default=0.0)
    _holdup_temperature: float = PrivateAttr(default=298.15)
    _holdup_pressure: float = PrivateAttr(default=101325.0)
    _holdup_composition: NDArray[np.float64] = PrivateAttr(
        default_factory=lambda: np.zeros(0, dtype=np.float64)
    )
    _holdup_species_ids: tuple[str, ...] | None = PrivateAttr(default=None)
    _inlet_species_ids: tuple[str, ...] | None = PrivateAttr(default=None)
    _outlet_species_ids: tuple[str, ...] | None = PrivateAttr(default=None)

    # --- Ports ---

    @property
    def ports(self) -> UnitProcessPorts:
        return _PORTS

    # --- Holdup property ---

    @property
    def holdup_mol(self) -> float:
        """Current molar holdup in the tank (mol)."""
        return self._holdup_mol

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
                "outlet": HydraulicPortSpec(
                    role="pressure_state",
                    pressure_state=HydraulicScalarStateRef(state="outlet_pressure"),
                ),
            },
            balancing_groups=(
                HydraulicBalancingGroupSpec(
                    name="holding_tank_flow_balance",
                    ports=("inlet", "outlet"),
                ),
            ),
            relations=(
                HydraulicRelationSpec(
                    name="holding_tank_pressure_equal",
                    kind="pressure_equal",
                    ports=("inlet", "outlet"),
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
            tuple(str(species_id) for species_id in stream.species_ids)
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
            species_ids=self._outlet_species_ids,
        )

    def to_hydraulic_element(self, port_name: str):
        return pipe_hydraulic_element_for_outlet(
            unit_name=type(self).__name__,
            port_name=port_name,
            allowed_outlet_ports=self.ports.outlets,
        )

    # --- Step: self-contained holdup arithmetic ---

    @override
    def step(self, dt: Seconds) -> None:
        """Advance holdup by one step.

        Discharge rule: the entire holdup present at the START of the step
        is drained uniformly over dt seconds (outlet_flow = holdup / dt).
        Then, new material from the inlet is accumulated for the next step.

        Invariants:
        - outlet_flow comes only from existing holdup (cannot invent material).
        - zero holdup + zero inlet → zero outlet.
        - outlet_flow * dt ≤ holdup_at_step_start.
        """
        dt_safe = max(dt, 1e-300)
        holdup_start = self._holdup_mol
        discharge_temperature = float(self._holdup_temperature)
        discharge_pressure = float(self._holdup_pressure)
        discharge_composition = self._holdup_composition.copy()
        discharge_species_ids = self._holdup_species_ids
        if holdup_start <= 0.0:
            discharge_temperature = float(self.inlet_temperature)
            discharge_pressure = float(self.inlet_pressure)
            discharge_composition = (
                np.asarray(self.inlet_composition, dtype=np.float64).reshape(-1).copy()
            )
            discharge_species_ids = self._inlet_species_ids

        # Discharge all available holdup over this step.
        self.outlet_flow = holdup_start / dt_safe

        # Accumulate new inlet material.
        inlet_amount = max(0.0, float(self.inlet_flow)) * float(dt)
        self._holdup_mol = inlet_amount
        if inlet_amount > 0.0:
            self._holdup_temperature = float(self.inlet_temperature)
            self._holdup_pressure = float(self.inlet_pressure)
            self._holdup_composition = (
                np.asarray(self.inlet_composition, dtype=np.float64).reshape(-1).copy()
            )
            self._holdup_species_ids = self._inlet_species_ids
        else:
            self._holdup_composition = np.zeros(0, dtype=np.float64)
            self._holdup_species_ids = None

        # Outlet carries the state of discharged holdup.
        self.outlet_temperature = discharge_temperature
        self.outlet_pressure = discharge_pressure
        self.outlet_composition = discharge_composition
        self._outlet_species_ids = discharge_species_ids

        self.t += float(dt)

    # --- Required abstract stubs (not used; step() is fully overridden) ---

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


__all__ = ["HoldingTank"]
