from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from typing import Annotated, ClassVar, override

import numpy as np
from numpy.typing import NDArray

from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import UnitProcessPorts
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
_NEAR_EMPTY_HOLDUP_FLOOR_MOL = 1.0e-9
_MIN_STEP_SECONDS = 1.0e-12


class HoldingTank(ProcessModel):
    """Conserved-holdup tank with runtime-owned outlet demand latching.

    The tank integrates conserved component holdup as a differential model.
    Runtime coupling latches solved outlet demand through
    ``apply_requested_outlet_through_flow_demand`` for consumption on the
    next macro step.
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
            flow="resolved_outlet_flow_mol_s",
            temperature="outlet_temperature",
            pressure="outlet_pressure",
            composition="outlet_composition",
        )
    }

    holdup_component_moles: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="mol", description="component holdup moles"),
    ] = np.asarray([0.0], dtype=np.float64)
    holdup_temperature: Annotated[
        float,
        M(type=T.DIFFERENTIAL, unit="K", description="holdup mixed temperature"),
    ] = 298.15
    holdup_pressure: Annotated[
        float,
        M(type=T.DIFFERENTIAL, unit="Pa", description="holdup pressure state"),
    ] = 101325.0

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
    ] = np.asarray([1.0], dtype=np.float64)

    requested_outlet_flow_mol_s: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="mol/s",
            description="runtime-latched requested outlet through-flow demand",
        ),
    ] = 0.0
    imposed_outlet_flow_mol_s: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="mol/s",
            description="step-frozen outlet draw used by ODE integration",
        ),
    ] = 0.0

    resolved_outlet_flow_mol_s: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="resolved outlet molar flow"),
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
    ] = np.asarray([1.0], dtype=np.float64)

    _holdup_species_ids: tuple[str, ...] | None = None
    _inlet_species_ids: tuple[str, ...] | None = None
    _outlet_species_ids: tuple[str, ...] | None = None

    @override
    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        self.holdup_component_moles = np.asarray(
            self.holdup_component_moles, dtype=np.float64
        ).reshape(-1)
        if self.holdup_component_moles.size == 0:
            self.holdup_component_moles = np.asarray([0.0], dtype=np.float64)
        self.inlet_composition = self._normalize_composition(
            np.asarray(self.inlet_composition, dtype=np.float64).reshape(-1),
            expected_size=self.holdup_component_moles.size,
            fallback=self.holdup_component_moles,
        )
        self.outlet_composition = self._normalize_composition(
            np.asarray(self.outlet_composition, dtype=np.float64).reshape(-1),
            expected_size=self.holdup_component_moles.size,
            fallback=self.holdup_component_moles,
        )

        self._solver_options = {
            "method": "RK45",
            "rtol": 1.0e-6,
            "atol": 1.0e-9,
        }
        self._construct_params()
        initial_algebraic_array = self._params.algebraic_values_function(
            y=self.differential_view.to_array(),
            u=self.boundary_view.to_array(),
            k=self._params.k,
            y_map=self._params.y_map,
            u_map=self._params.boundary_map,
            k_map=self._params.k_map,
            algebraic_map=self._params.algebraic_map,
            algebraic_size=self._params.algebraic_size,
        )
        self.algebraic_view.update_from_array(initial_algebraic_array)

    @property
    def ports(self) -> UnitProcessPorts:
        return _PORTS

    @property
    def holdup_mol(self) -> float:
        return float(np.sum(np.clip(self.holdup_component_moles, 0.0, None)))

    @property
    def outlet_flow(self) -> float:
        return float(self.resolved_outlet_flow_mol_s)

    @outlet_flow.setter
    def outlet_flow(self, value: float) -> None:
        self.resolved_outlet_flow_mol_s = float(value)

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

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        if port_name not in self.ports.inlets:
            valid_ports = ", ".join(self.ports.inlets)
            raise ValueError(
                f"Invalid inlet port '{port_name}' for {type(self).__name__}. "
                f"Valid inlet ports: {valid_ports}."
            )

        composition = np.asarray(stream.mole_fractions, dtype=np.float64).reshape(-1)
        current_size = int(self.holdup_component_moles.size)
        if (
            composition.size != current_size
            and self.holdup_mol > _NEAR_EMPTY_HOLDUP_FLOOR_MOL
            and float(stream.molar_flow_rate) <= 0.0
        ):
            composition = np.asarray(self.outlet_composition, dtype=np.float64).reshape(-1)
        self._ensure_species_dimension(composition.size)
        composition = self._normalize_composition(
            composition,
            expected_size=self.holdup_component_moles.size,
            fallback=self.holdup_component_moles,
        )

        port_map = self._INLET_MAP[port_name]
        setattr(self, port_map.flow, float(stream.molar_flow_rate))
        setattr(self, port_map.temperature, float(stream.temperature))
        setattr(self, port_map.pressure, float(stream.pressure))
        setattr(self, port_map.composition, composition)
        self._inlet_species_ids = (
            tuple(str(species_id) for species_id in stream.species_ids)
            if stream.species_ids is not None
            else None
        )

    def apply_requested_outlet_through_flow_demand(
        self, port_name: str, through_molar_flow_rate: float
    ) -> None:
        if port_name not in self.ports.outlets:
            valid_ports = ", ".join(self.ports.outlets)
            raise ValueError(
                f"Invalid outlet port '{port_name}' for {type(self).__name__}. "
                f"Valid outlet ports: {valid_ports}."
            )
        self.requested_outlet_flow_mol_s = max(0.0, float(through_molar_flow_rate))

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

    def resolve_outlet_condition(self, port_name: str):
        return self.get_outlet_stream(port_name).to_port_condition()

    def to_hydraulic_element(self, port_name: str):
        return pipe_hydraulic_element_for_outlet(
            unit_name=type(self).__name__,
            port_name=port_name,
            allowed_outlet_ports=self.ports.outlets,
        )

    @override
    def step(self, dt: Seconds) -> None:
        dt_s = max(float(dt), _MIN_STEP_SECONDS)
        requested_flow = max(0.0, float(self.requested_outlet_flow_mol_s))
        if requested_flow > 0.0:
            # An explicit demand was set by the runtime (hydraulic solve).
            # Realized withdrawal cannot exceed physically available moles over
            # this step: start-of-step withdrawable holdup + same-step inflow.
            holdup_start = self.holdup_mol
            withdrawable_moles = max(0.0, holdup_start - _NEAR_EMPTY_HOLDUP_FLOOR_MOL)
            inlet_moles = max(0.0, float(self.inlet_flow)) * dt_s
            max_realizable_flow = (withdrawable_moles + inlet_moles) / dt_s
            self.imposed_outlet_flow_mol_s = min(requested_flow, max_realizable_flow)
        else:
            # No explicit demand: drain all available holdup (legacy free-discharge
            # behaviour for stand-alone / unconnected use).
            holdup_start = self.holdup_mol
            withdrawable_moles = max(0.0, holdup_start - _NEAR_EMPTY_HOLDUP_FLOOR_MOL)
            self.imposed_outlet_flow_mol_s = withdrawable_moles / dt_s

        super().step(float(dt))

        holdup_after = self.holdup_mol
        if holdup_after <= _NEAR_EMPTY_HOLDUP_FLOOR_MOL:
            self.holdup_component_moles = np.zeros_like(self.holdup_component_moles)
            self._holdup_species_ids = None
        elif self._inlet_species_ids is not None:
            self._holdup_species_ids = self._inlet_species_ids
        self._outlet_species_ids = self._holdup_species_ids

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
        del k, k_map
        holdup_component_moles = np.asarray(y[y_map["holdup_component_moles"]], dtype=np.float64)
        inlet_composition = np.asarray(u[u_map["inlet_composition"]], dtype=np.float64)

        total_holdup = float(np.sum(np.clip(holdup_component_moles, 0.0, None)))
        if total_holdup > _NEAR_EMPTY_HOLDUP_FLOOR_MOL:
            outlet_composition = np.clip(holdup_component_moles, 0.0, None) / total_holdup
        else:
            outlet_composition = HoldingTank._normalize_composition(
                inlet_composition,
                expected_size=inlet_composition.size,
                fallback=holdup_component_moles,
            )

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["resolved_outlet_flow_mol_s"]] = max(
            0.0,
            float(u[u_map["imposed_outlet_flow_mol_s"]]),
        )
        if total_holdup > _NEAR_EMPTY_HOLDUP_FLOOR_MOL:
            result[algebraic_map["outlet_temperature"]] = float(y[y_map["holdup_temperature"]])
            result[algebraic_map["outlet_pressure"]] = float(y[y_map["holdup_pressure"]])
        else:
            result[algebraic_map["outlet_temperature"]] = float(u[u_map["inlet_temperature"]])
            result[algebraic_map["outlet_pressure"]] = float(u[u_map["inlet_pressure"]])
        result[algebraic_map["outlet_composition"]] = outlet_composition
        return result

    @staticmethod
    @override
    def differential_rhs(
        t: float,
        y: NDArray[np.float64],
        u: NDArray[np.float64],
        k: NDArray[np.float64],
        algebraic: NDArray[np.float64],
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
    ) -> NDArray[np.float64]:
        del t, k, k_map
        holdup_component_moles = np.asarray(y[y_map["holdup_component_moles"]], dtype=np.float64)
        inlet_flow = max(0.0, float(u[u_map["inlet_flow"]]))
        inlet_composition = np.asarray(u[u_map["inlet_composition"]], dtype=np.float64)
        outlet_flow = max(0.0, float(algebraic[algebraic_map["resolved_outlet_flow_mol_s"]]))
        outlet_composition = np.asarray(
            algebraic[algebraic_map["outlet_composition"]], dtype=np.float64
        )

        inlet_component_flows = inlet_flow * inlet_composition
        outlet_component_flows = outlet_flow * outlet_composition
        d_component_moles_dt = inlet_component_flows - outlet_component_flows

        total_holdup = float(np.sum(np.clip(holdup_component_moles, 0.0, None)))
        incoming_holdup_rate = inlet_flow
        incoming_temperature = float(u[u_map["inlet_temperature"]])
        incoming_pressure = float(u[u_map["inlet_pressure"]])
        holdup_temperature = float(y[y_map["holdup_temperature"]])
        holdup_pressure = float(y[y_map["holdup_pressure"]])

        if total_holdup <= _NEAR_EMPTY_HOLDUP_FLOOR_MOL:
            # When the tank is near-empty, temperature and pressure are not
            # meaningful stored quantities.  Zeroing these derivatives avoids
            # a numerical singularity: the blending formula
            #   dT/dt = F_in * (T_in - T_hold) / total
            # diverges as total → 0 and makes the ODE extremely stiff.
            # Temperature/pressure for any outlet during an empty-tank step
            # are taken from inlet conditions via the algebraic map.
            d_temperature_dt = 0.0
            d_pressure_dt = 0.0
        else:
            d_temperature_dt = (
                incoming_holdup_rate * (incoming_temperature - holdup_temperature)
            ) / total_holdup
            d_pressure_dt = (
                incoming_holdup_rate * (incoming_pressure - holdup_pressure)
            ) / total_holdup

        dy = np.zeros_like(y)
        dy[y_map["holdup_component_moles"]] = d_component_moles_dt
        dy[y_map["holdup_temperature"]] = d_temperature_dt
        dy[y_map["holdup_pressure"]] = d_pressure_dt
        return dy

    @staticmethod
    def _normalize_composition(
        values: NDArray[np.float64], *, expected_size: int, fallback: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        vector = np.asarray(values, dtype=np.float64).reshape(-1)
        if expected_size <= 0:
            return np.asarray([1.0], dtype=np.float64)
        if vector.size != expected_size:
            vector = np.asarray(fallback, dtype=np.float64).reshape(-1)
            if vector.size != expected_size:
                vector = np.zeros(expected_size, dtype=np.float64)
        vector = np.clip(vector, 0.0, None)
        total = float(np.sum(vector))
        if total <= 1.0e-12:
            return np.full(expected_size, 1.0 / float(expected_size), dtype=np.float64)
        return vector / total

    def _ensure_species_dimension(self, size: int) -> None:
        if size <= 0:
            raise ValueError("HoldingTank inlet composition must contain at least one species")
        current_size = int(self.holdup_component_moles.size)
        if current_size == size:
            return
        if self.holdup_mol > _NEAR_EMPTY_HOLDUP_FLOOR_MOL:
            raise ValueError(
                "HoldingTank cannot change species dimension while non-empty holdup is present"
            )
        self.holdup_component_moles = np.zeros(size, dtype=np.float64)
        self.inlet_composition = np.full(size, 1.0 / float(size), dtype=np.float64)
        self.outlet_composition = np.full(size, 1.0 / float(size), dtype=np.float64)
        self._rebuild_cached_state_views()

    def _rebuild_cached_state_views(self) -> None:
        for cached_attr in (
            "differential_view",
            "algebraic_view",
            "boundary_view",
            "constant_view",
            "state_list",
        ):
            if cached_attr in self.__dict__:
                del self.__dict__[cached_attr]
        self._construct_params()
        initial_algebraic_array = self._params.algebraic_values_function(
            y=self.differential_view.to_array(),
            u=self.boundary_view.to_array(),
            k=self._params.k,
            y_map=self._params.y_map,
            u_map=self._params.boundary_map,
            k_map=self._params.k_map,
            algebraic_map=self._params.algebraic_map,
            algebraic_size=self._params.algebraic_size,
        )
        self.algebraic_view.update_from_array(initial_algebraic_array)


__all__ = ["HoldingTank"]
