from __future__ import annotations

from typing import Annotated

import numpy as np
from numpy.typing import NDArray

from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import UnitProcessPorts
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.utils.typing import ArrayIndex

_MIN_SUM = 1.0e-12


def _normalize_composition(raw: NDArray[np.float64], *, n_species: int) -> NDArray[np.float64]:
    values = np.asarray(raw, dtype=np.float64).reshape(-1)
    if values.size != n_species:
        raise ValueError(f"composition length mismatch: expected {n_species}, got {values.size}.")
    values = np.clip(values, 0.0, None)
    total = float(np.sum(values))
    if total <= _MIN_SUM:
        return np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
    return values / total


def _realized_withdrawal_flow(*, requested_flow: float, owner_moles: NDArray[np.float64]) -> float:
    request = max(0.0, float(requested_flow))
    inventory = max(0.0, float(np.sum(owner_moles)))
    return min(request, inventory / 4.0)


class Gani1986DistillationColumn(ProcessModel):
    plate_component_holdup: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="mol", description="plate component holdup (flattened)"),
    ] = np.zeros(0, dtype=np.float64)
    reflux_drum_component_moles: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="mol", description="reflux drum component holdup"),
    ] = np.zeros(0, dtype=np.float64)
    reboiler_component_moles: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="mol", description="reboiler component holdup"),
    ] = np.zeros(0, dtype=np.float64)
    plate_energy_holdup_j: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="J", description="plate total-energy holdup"),
    ] = np.zeros(0, dtype=np.float64)

    feed_1_flow: Annotated[float, M(type=T.BOUNDARY, unit="mol/s", description="feed flow")] = 0.0
    feed_1_temperature: Annotated[
        float, M(type=T.BOUNDARY, unit="K", description="feed temperature")
    ] = 298.15
    feed_1_pressure: Annotated[
        float, M(type=T.BOUNDARY, unit="Pa", description="feed pressure")
    ] = 101325.0
    feed_1_composition: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="", description="feed composition"),
    ] = np.zeros(0, dtype=np.float64)

    reflux_return_flow: Annotated[
        float, M(type=T.BOUNDARY, unit="mol/s", description="external reflux-return flow")
    ] = 0.0
    reflux_return_temperature: Annotated[
        float, M(type=T.BOUNDARY, unit="K", description="external reflux-return temperature")
    ] = 298.15
    reflux_return_pressure: Annotated[
        float, M(type=T.BOUNDARY, unit="Pa", description="external reflux-return pressure")
    ] = 101325.0
    reflux_return_composition: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="", description="external reflux-return composition"),
    ] = np.zeros(0, dtype=np.float64)

    distillate_withdrawal_flow: Annotated[
        float,
        M(type=T.BOUNDARY, unit="mol/s", description="requested distillate withdrawal"),
    ] = 0.0
    bottoms_withdrawal_flow: Annotated[
        float,
        M(type=T.BOUNDARY, unit="mol/s", description="requested bottoms withdrawal"),
    ] = 0.0

    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2
    n_plates: Annotated[int, M(type=T.CONSTANT, unit="", description="number of plates")] = 4
    murphree_efficiency: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="Murphree efficiency closure for first slice"),
    ] = 0.75
    nominal_vapor_flow_mol_s: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol/s", description="nominal internal vapor flow"),
    ] = 6.0
    nominal_liquid_flow_mol_s: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol/s", description="nominal internal liquid flow"),
    ] = 5.0
    hydraulic_pressure_drop_pa: Annotated[
        float,
        M(type=T.CONSTANT, unit="Pa", description="nominal per-plate pressure drop"),
    ] = 1500.0
    equilibrium_reference_K: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="", description="component K-values for equilibrium closure"),
    ] = np.zeros(0, dtype=np.float64)
    species_molecular_weight_kg_mol: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="kg/mol", description="species molecular weights"),
    ] = np.zeros(0, dtype=np.float64)
    species_liquid_heat_capacity_j_mol_k: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/mol/K", description="species liquid heat capacities"),
    ] = np.zeros(0, dtype=np.float64)
    species_vapor_heat_capacity_j_mol_k: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/mol/K", description="species vapor heat capacities"),
    ] = np.zeros(0, dtype=np.float64)
    species_vaporization_enthalpy_j_mol: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/mol", description="species vaporization enthalpies"),
    ] = np.zeros(0, dtype=np.float64)
    thermo_reference_temperature_k: Annotated[
        float,
        M(type=T.CONSTANT, unit="K", description="reference temperature for enthalpy closures"),
    ] = 298.15
    thermo_k_temperature_sensitivity: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="temperature sensitivity for equilibrium K"),
    ] = 0.45
    thermo_k_pressure_sensitivity: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="pressure sensitivity for equilibrium K"),
    ] = 0.08

    distillate_flow: Annotated[
        float, M(type=T.ALGEBRAIC, unit="mol/s", description="distillate product flow")
    ] = 0.0
    bottoms_flow: Annotated[
        float, M(type=T.ALGEBRAIC, unit="mol/s", description="bottoms product flow")
    ] = 0.0
    distillate_temperature: Annotated[
        float, M(type=T.ALGEBRAIC, unit="K", description="distillate temperature")
    ] = 298.15
    bottoms_temperature: Annotated[
        float, M(type=T.ALGEBRAIC, unit="K", description="bottoms temperature")
    ] = 298.15
    distillate_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="distillate composition"),
    ] = np.zeros(0, dtype=np.float64)
    bottoms_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="bottoms composition"),
    ] = np.zeros(0, dtype=np.float64)
    plate_liquid_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="plate liquid compositions (flattened)"),
    ] = np.zeros(0, dtype=np.float64)
    plate_vapor_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="plate vapor compositions (flattened)"),
    ] = np.zeros(0, dtype=np.float64)
    plate_vapor_flow_mol_s: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="plate vapor flows"),
    ] = np.zeros(0, dtype=np.float64)
    plate_liquid_flow_mol_s: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="plate liquid flows"),
    ] = np.zeros(0, dtype=np.float64)
    plate_liquid_entrainment_mol_s: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="plate liquid entrainment flows"),
    ] = np.zeros(0, dtype=np.float64)
    plate_vapor_entrainment_mol_s: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="plate vapor entrainment flows"),
    ] = np.zeros(0, dtype=np.float64)
    plate_total_mass_balance_rhs_mol_s: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="GE-G86-3 plate total-mass RHS"),
    ] = np.zeros(0, dtype=np.float64)
    plate_pressure_drop_pa: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="Pa", description="plate pressure-drop closures"),
    ] = np.zeros(0, dtype=np.float64)
    reflux_to_column_flow_mol_s: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="mol/s",
            description="realized reflux flow from drum to top plate",
        ),
    ] = 0.0
    reboiler_vapor_flow_mol_s: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="reboiler vapor boilup flow"),
    ] = 0.0
    reboiler_vapor_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="reboiler vapor composition"),
    ] = np.zeros(0, dtype=np.float64)
    plate_temperature_k: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="K", description="plate liquid temperatures"),
    ] = np.zeros(0, dtype=np.float64)
    plate_liquid_enthalpy_j_mol: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="J/mol", description="plate liquid enthalpy closures"),
    ] = np.zeros(0, dtype=np.float64)
    plate_vapor_enthalpy_j_mol: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="J/mol", description="plate vapor enthalpy closures"),
    ] = np.zeros(0, dtype=np.float64)
    plate_equilibrium_K_values: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="plate K-value closures (flattened)"),
    ] = np.zeros(0, dtype=np.float64)
    plate_liquid_density_kg_m3: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="kg/m3", description="plate liquid density closures"),
    ] = np.zeros(0, dtype=np.float64)
    plate_vapor_density_kg_m3: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="kg/m3", description="plate vapor density closures"),
    ] = np.zeros(0, dtype=np.float64)
    plate_liquid_molecular_weight_kg_mol: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="kg/mol", description="plate liquid molecular weights"),
    ] = np.zeros(0, dtype=np.float64)
    plate_vapor_molecular_weight_kg_mol: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="kg/mol", description="plate vapor molecular weights"),
    ] = np.zeros(0, dtype=np.float64)
    plate_bubblecap_crest_height_m: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="m", description="Appendix A.1 crest height over weir"),
    ] = np.zeros(0, dtype=np.float64)
    plate_bubblecap_dry_tray_drop_m: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="m", description="Appendix A.2 dry tray pressure drop"),
    ] = np.zeros(0, dtype=np.float64)
    plate_bubblecap_total_holdup_mol: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol", description="Appendix A.3 total holdup closure"),
    ] = np.zeros(0, dtype=np.float64)
    plate_bubblecap_liquid_height_m: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="m", description="Appendix A.6 liquid height"),
    ] = np.zeros(0, dtype=np.float64)
    plate_bubblecap_active_liquid_height_m: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="m", description="Appendix A.7 active liquid height"),
    ] = np.zeros(0, dtype=np.float64)
    plate_bubblecap_weeping_flow_m3_s: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="m3/s", description="Appendix A.8 weeping flow rate"),
    ] = np.zeros(0, dtype=np.float64)

    _ports: UnitProcessPorts = UnitProcessPorts(
        ("feed_1", "reflux_return"),
        ("distillate", "bottoms"),
    )

    @property
    def ports(self) -> UnitProcessPorts:
        return self._ports

    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        if self.n_species <= 1:
            raise ValueError("n_species must be at least 2 for Gani1986DistillationColumn.")
        if self.n_plates <= 0:
            raise ValueError("n_plates must be positive.")

        plate_size = self.n_species * self.n_plates
        if self.plate_component_holdup.size != plate_size:
            self.plate_component_holdup = np.full(
                plate_size,
                12.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.reflux_drum_component_moles.size != self.n_species:
            self.reflux_drum_component_moles = np.full(
                self.n_species,
                5.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.reboiler_component_moles.size != self.n_species:
            self.reboiler_component_moles = np.full(
                self.n_species,
                6.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.plate_energy_holdup_j.size != self.n_plates:
            self.plate_energy_holdup_j = np.full(self.n_plates, 3.2e5, dtype=np.float64)

        if self.feed_1_composition.size != self.n_species:
            self.feed_1_composition = np.full(
                self.n_species, 1.0 / float(self.n_species), dtype=np.float64
            )
        self.feed_1_composition = _normalize_composition(
            self.feed_1_composition, n_species=self.n_species
        )

        if self.reflux_return_composition.size != self.n_species:
            self.reflux_return_composition = np.full(
                self.n_species,
                1.0 / float(self.n_species),
                dtype=np.float64,
            )
        self.reflux_return_composition = _normalize_composition(
            self.reflux_return_composition, n_species=self.n_species
        )

        if self.distillate_composition.size != self.n_species:
            self.distillate_composition = np.full(
                self.n_species,
                1.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.bottoms_composition.size != self.n_species:
            self.bottoms_composition = np.full(
                self.n_species,
                1.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.equilibrium_reference_K.size != self.n_species:
            if self.n_species == 2:
                self.equilibrium_reference_K = np.array([1.8, 0.7], dtype=np.float64)
            else:
                self.equilibrium_reference_K = np.linspace(
                    1.8, 0.6, self.n_species, dtype=np.float64
                )
        if self.species_molecular_weight_kg_mol.size != self.n_species:
            self.species_molecular_weight_kg_mol = np.linspace(
                0.030,
                0.080,
                self.n_species,
                dtype=np.float64,
            )
        if self.species_liquid_heat_capacity_j_mol_k.size != self.n_species:
            self.species_liquid_heat_capacity_j_mol_k = np.linspace(
                80.0,
                140.0,
                self.n_species,
                dtype=np.float64,
            )
        if self.species_vapor_heat_capacity_j_mol_k.size != self.n_species:
            self.species_vapor_heat_capacity_j_mol_k = np.linspace(
                35.0,
                65.0,
                self.n_species,
                dtype=np.float64,
            )
        if self.species_vaporization_enthalpy_j_mol.size != self.n_species:
            self.species_vaporization_enthalpy_j_mol = np.linspace(
                2.2e4,
                3.6e4,
                self.n_species,
                dtype=np.float64,
            )

        plate_size = self.n_plates * self.n_species
        if self.plate_liquid_composition.size != plate_size:
            self.plate_liquid_composition = np.full(
                plate_size,
                1.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.plate_vapor_composition.size != plate_size:
            self.plate_vapor_composition = np.full(
                plate_size,
                1.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.plate_vapor_flow_mol_s.size != self.n_plates:
            self.plate_vapor_flow_mol_s = np.full(self.n_plates, self.nominal_vapor_flow_mol_s)
        if self.plate_liquid_flow_mol_s.size != self.n_plates:
            self.plate_liquid_flow_mol_s = np.full(self.n_plates, self.nominal_liquid_flow_mol_s)
        if self.plate_liquid_entrainment_mol_s.size != self.n_plates:
            self.plate_liquid_entrainment_mol_s = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_vapor_entrainment_mol_s.size != self.n_plates:
            self.plate_vapor_entrainment_mol_s = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_total_mass_balance_rhs_mol_s.size != self.n_plates:
            self.plate_total_mass_balance_rhs_mol_s = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_pressure_drop_pa.size != self.n_plates:
            self.plate_pressure_drop_pa = np.full(
                self.n_plates,
                self.hydraulic_pressure_drop_pa,
                dtype=np.float64,
            )
        if self.reboiler_vapor_composition.size != self.n_species:
            self.reboiler_vapor_composition = np.full(
                self.n_species,
                1.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.plate_temperature_k.size != self.n_plates:
            self.plate_temperature_k = np.full(
                self.n_plates, self.feed_1_temperature, dtype=np.float64
            )
        if self.plate_liquid_enthalpy_j_mol.size != self.n_plates:
            self.plate_liquid_enthalpy_j_mol = np.full(self.n_plates, 2.5e4, dtype=np.float64)
        if self.plate_vapor_enthalpy_j_mol.size != self.n_plates:
            self.plate_vapor_enthalpy_j_mol = np.full(self.n_plates, 4.2e4, dtype=np.float64)
        if self.plate_equilibrium_K_values.size != plate_size:
            self.plate_equilibrium_K_values = np.tile(self.equilibrium_reference_K, self.n_plates)
        if self.plate_liquid_density_kg_m3.size != self.n_plates:
            self.plate_liquid_density_kg_m3 = np.full(self.n_plates, 750.0, dtype=np.float64)
        if self.plate_vapor_density_kg_m3.size != self.n_plates:
            self.plate_vapor_density_kg_m3 = np.full(self.n_plates, 2.5, dtype=np.float64)
        if self.plate_liquid_molecular_weight_kg_mol.size != self.n_plates:
            self.plate_liquid_molecular_weight_kg_mol = np.full(
                self.n_plates, 0.055, dtype=np.float64
            )
        if self.plate_vapor_molecular_weight_kg_mol.size != self.n_plates:
            self.plate_vapor_molecular_weight_kg_mol = np.full(
                self.n_plates, 0.045, dtype=np.float64
            )
        if self.plate_bubblecap_crest_height_m.size != self.n_plates:
            self.plate_bubblecap_crest_height_m = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_bubblecap_dry_tray_drop_m.size != self.n_plates:
            self.plate_bubblecap_dry_tray_drop_m = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_bubblecap_total_holdup_mol.size != self.n_plates:
            self.plate_bubblecap_total_holdup_mol = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_bubblecap_liquid_height_m.size != self.n_plates:
            self.plate_bubblecap_liquid_height_m = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_bubblecap_active_liquid_height_m.size != self.n_plates:
            self.plate_bubblecap_active_liquid_height_m = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_bubblecap_weeping_flow_m3_s.size != self.n_plates:
            self.plate_bubblecap_weeping_flow_m3_s = np.zeros(self.n_plates, dtype=np.float64)

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        if port_name not in self.ports.inlets:
            valid_ports = ", ".join(self.ports.inlets)
            raise ValueError(
                f"Invalid inlet port '{port_name}' for {type(self).__name__}. Valid inlet ports: {valid_ports}."
            )

        if port_name == "feed_1":
            self.feed_1_flow = max(0.0, float(stream.molar_flow_rate))
            self.feed_1_temperature = float(stream.temperature)
            self.feed_1_pressure = float(stream.pressure)
            self.feed_1_composition = _normalize_composition(
                np.asarray(stream.mole_fractions, dtype=np.float64),
                n_species=self.n_species,
            )
            return

        self.reflux_return_flow = max(0.0, float(stream.molar_flow_rate))
        self.reflux_return_temperature = float(stream.temperature)
        self.reflux_return_pressure = float(stream.pressure)
        self.reflux_return_composition = _normalize_composition(
            np.asarray(stream.mole_fractions, dtype=np.float64),
            n_species=self.n_species,
        )

    def apply_requested_outlet_through_flow_demand(
        self, port_name: str, through_molar_flow_rate: float
    ) -> None:
        if port_name not in self.ports.outlets:
            valid_ports = ", ".join(self.ports.outlets)
            raise ValueError(
                f"Invalid outlet port '{port_name}' for {type(self).__name__}. Valid outlet ports: {valid_ports}."
            )
        if port_name == "distillate":
            self.distillate_withdrawal_flow = max(0.0, float(through_molar_flow_rate))
            return
        self.bottoms_withdrawal_flow = max(0.0, float(through_molar_flow_rate))

    def get_outlet_stream(self, port_name: str) -> StreamData:
        if port_name not in self.ports.outlets:
            valid_ports = ", ".join(self.ports.outlets)
            raise ValueError(
                f"Invalid outlet port '{port_name}' for {type(self).__name__}. Valid outlet ports: {valid_ports}."
            )

        pressure = max(self.feed_1_pressure, self.reflux_return_pressure, 101325.0)
        if port_name == "distillate":
            return StreamData(
                temperature=float(self.distillate_temperature),
                pressure=float(pressure),
                mole_fractions=tuple(float(x) for x in self.distillate_composition),
                molar_flow_rate=float(max(0.0, self.distillate_flow)),
            )
        return StreamData(
            temperature=float(self.bottoms_temperature),
            pressure=float(pressure),
            mole_fractions=tuple(float(x) for x in self.bottoms_composition),
            molar_flow_rate=float(max(0.0, self.bottoms_flow)),
        )

    @staticmethod
    def calculate_component_balance_rhs(
        *,
        plate_index: int,
        component_index: int,
        x_above: NDArray[np.float64] | None = None,
        y_below: NDArray[np.float64] | None = None,
        x_plate: NDArray[np.float64],
        y_plate: NDArray[np.float64],
        V_below: float,
        V_plate: float,
        L_above: float,
        L_plate: float,
        E_L_below: float,
        E_V_above: float,
        E_L_plate: float,
        E_V_plate: float,
        P_L: float,
        P_V: float,
        F_L: float,
        F_V: float,
        x_F_L: NDArray[np.float64],
        y_F_V: NDArray[np.float64],
        x_below: NDArray[np.float64] | None = None,
        y_above: NDArray[np.float64] | None = None,
    ) -> float:
        del plate_index
        i = int(component_index)
        x_plate_values = np.asarray(x_plate, dtype=np.float64)
        x_feed_values = np.asarray(x_F_L, dtype=np.float64)
        x_above_values = np.asarray(
            x_above
            if x_above is not None
            else np.clip(2.0 * x_plate_values - x_feed_values, 0.0, None),
            dtype=np.float64,
        )
        y_below_values = np.asarray(
            y_below if y_below is not None else x_feed_values, dtype=np.float64
        )
        # Entrainment source states: neighbor plates, not receiving plate.
        # GE-G86-1: E_L_{p-1} * x_{p-1,i}  and  E_V_{p+1} * y_{p+1,i}
        x_below_values = np.asarray(
            x_below if x_below is not None else x_plate_values, dtype=np.float64
        )
        y_above_values = np.asarray(y_above if y_above is not None else y_plate, dtype=np.float64)
        inlet = (
            float(F_V) * float(y_F_V[i])
            + float(F_L) * float(x_F_L[i])
            + float(V_below) * float(y_below_values[i])
            + float(E_L_below) * float(x_below_values[i])
            + float(L_above) * float(x_above_values[i])
            + float(E_V_above) * float(y_above_values[i])
        )
        outlet = (float(P_V) + float(V_plate) + float(E_V_plate)) * float(y_plate[i]) + (
            float(P_L) + float(L_plate) + float(E_L_plate)
        ) * float(x_plate[i])
        return inlet - outlet

    @staticmethod
    def calculate_energy_balance_rhs(
        *,
        plate_index: int,
        H_below: float,
        H_plate: float,
        h_above: float,
        h_plate: float,
        V_below: float,
        V_plate: float,
        L_above: float,
        L_plate: float,
        E_L_below: float,
        E_V_above: float,
        E_L_plate: float,
        E_V_plate: float,
        P_L: float,
        P_V: float,
        F_L: float,
        F_V: float,
        H_F_V: float,
        h_F_L: float,
        h_below: float | None = None,
        H_above: float | None = None,
    ) -> float:
        del plate_index
        # Entrainment source enthalpies: neighbor plates, not receiving plate.
        # GE-G86-2: E_L_{p-1} * h_{p-1}  and  E_V_{p+1} * H_{p+1}
        h_below_val = float(h_below) if h_below is not None else float(h_plate)
        H_above_val = float(H_above) if H_above is not None else float(H_plate)
        inlet = (
            float(F_V) * float(H_F_V)
            + float(F_L) * float(h_F_L)
            + float(V_below) * float(H_below)
            + float(E_L_below) * h_below_val
            + float(L_above) * float(h_above)
            + float(E_V_above) * H_above_val
        )
        outlet = (float(P_V) + float(V_plate) + float(E_V_plate)) * float(H_plate) + (
            float(P_L) + float(L_plate) + float(E_L_plate)
        ) * float(h_plate)
        return inlet - outlet

    @staticmethod
    def calculate_total_mass_balance_rhs(
        *,
        V_below: float,
        V_plate: float,
        L_above: float,
        L_plate: float,
        E_L_below: float,
        E_V_above: float,
        E_L_plate: float,
        E_V_plate: float,
        P_L: float,
        P_V: float,
        F_L: float,
        F_V: float,
    ) -> float:
        inlet = (
            float(F_V)
            + float(F_L)
            + float(V_below)
            + float(E_L_below)
            + float(L_above)
            + float(E_V_above)
        )
        outlet = (
            float(V_plate)
            + float(E_L_plate)
            + float(L_plate)
            + float(E_V_plate)
            + float(P_V)
            + float(P_L)
        )
        return inlet - outlet

    @staticmethod
    def compute_equilibrium_from_murphree(
        y_p: NDArray[np.float64],
        y_p_minus1: NDArray[np.float64],
        murphree_efficiency: float,
    ) -> NDArray[np.float64]:
        return (
            np.asarray(y_p, dtype=np.float64) - np.asarray(y_p_minus1, dtype=np.float64)
        ) / float(murphree_efficiency) + np.asarray(y_p_minus1, dtype=np.float64)

    @staticmethod
    def compute_composition_from_holdup(
        component_holdup: NDArray[np.float64],
        total_holdup: float,
    ) -> NDArray[np.float64]:
        return np.asarray(component_holdup, dtype=np.float64) / float(total_holdup)

    @staticmethod
    def compute_equilibrium_composition(
        K_values: NDArray[np.float64],
        x_values: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        return np.asarray(K_values, dtype=np.float64) * np.asarray(x_values, dtype=np.float64)

    @staticmethod
    def compute_mixture_molecular_weight(
        molecular_weights: NDArray[np.float64],
        composition: NDArray[np.float64],
    ) -> float:
        return float(
            np.dot(
                np.asarray(molecular_weights, dtype=np.float64),
                np.asarray(composition, dtype=np.float64),
            )
        )

    @staticmethod
    def compute_pressure_drop(pressure_below: float, pressure_plate: float) -> float:
        return float(pressure_below) - float(pressure_plate)

    @staticmethod
    def compute_generic_hydraulic_family(
        *,
        delta_pressure: float,
        total_holdup: float,
        plate_geometry: dict[str, float],
        vapor_flow_fn: object,
        liquid_flow_fn: object,
        liquid_weir_flow_fn: object,
        vapor_froth_flow_fn: object,
        liquid_entrainment_fn: object,
        vapor_entrainment_fn: object,
    ) -> dict[str, float]:
        vapor_flow = vapor_flow_fn(delta_pressure, total_holdup, plate_geometry)  # pyright: ignore[reportCallIssue]
        liquid_flow = liquid_flow_fn(total_holdup, plate_geometry)  # pyright: ignore[reportCallIssue]
        liquid_weir_flow = liquid_weir_flow_fn(total_holdup, vapor_flow, plate_geometry)  # pyright: ignore[reportCallIssue]
        vapor_froth_flow = vapor_froth_flow_fn(vapor_flow, liquid_flow, plate_geometry)  # pyright: ignore[reportCallIssue]
        liquid_entrainment = liquid_entrainment_fn(total_holdup, delta_pressure, plate_geometry)  # pyright: ignore[reportCallIssue]
        vapor_entrainment = vapor_entrainment_fn(total_holdup, delta_pressure, plate_geometry)  # pyright: ignore[reportCallIssue]
        return {
            "delta_pressure": float(delta_pressure),
            "vapor_flow": float(vapor_flow),
            "liquid_flow": float(liquid_flow),
            "liquid_weir_flow": float(liquid_weir_flow),
            "vapor_froth_flow": float(vapor_froth_flow),
            "liquid_entrainment": float(liquid_entrainment),
            "vapor_entrainment": float(vapor_entrainment),
        }

    @staticmethod
    def calculate_reflux_drum_balance_rhs(
        *,
        component_index: int,
        y_top_plate: NDArray[np.float64],
        x_distillate: NDArray[np.float64],
        V_top_plate: float,
        L_reflux: float,
        D_distillate: float,
    ) -> float:
        i = int(component_index)
        return float(V_top_plate) * float(y_top_plate[i]) - (
            float(L_reflux) + float(D_distillate)
        ) * float(x_distillate[i])

    @staticmethod
    def calculate_reboiler_balance_rhs(
        *,
        component_index: int,
        x_bottom_plate: NDArray[np.float64],
        x_bottoms: NDArray[np.float64],
        y_bottoms: NDArray[np.float64],
        L_bottom_plate: float,
        B_bottoms: float,
        V_reboiler: float,
    ) -> float:
        i = int(component_index)
        return (
            float(L_bottom_plate) * float(x_bottom_plate[i])
            - float(B_bottoms) * float(x_bottoms[i])
            - float(V_reboiler) * float(y_bottoms[i])
        )

    @staticmethod
    def compute_crest_height_over_weir(L_D_p: float, W: float, rho_L: float) -> float:
        return (float(L_D_p) / (float(W) * float(rho_L) * 999.0)) ** (2.0 / 3.0)

    @staticmethod
    def compute_dry_tray_pressure_drop(g_L: float, A_D1: float) -> float:
        return (0.003 / 12.0) * (float(g_L) / (100.0 * float(A_D1))) ** 2

    @staticmethod
    def compute_total_holdup_from_hydraulics(
        *,
        beta: float,
        h_w: float,
        h_ow: float,
        A_p: float,
        rho_L: float,
        M_L: float,
        h_T: float,
        h_da: float,
        h_L: float,
        l_clearance: float,
        A_D2: float,
    ) -> float:
        return float(beta) * (float(h_w) + float(h_ow)) * (
            float(A_p) * float(rho_L) / float(M_L)
        ) + (float(h_T) + float(h_da) + float(h_L) - float(l_clearance)) * (
            float(rho_L) * float(A_D2) / float(M_L)
        )

    @staticmethod
    def compute_downcomer_unsealed_tray_head(
        *,
        h_L_below: float,
        h_bc: float,
        gravity: float,
        rho_L: float,
        rho_V: float,
        V_D: float,
        M_V: float,
        A_D2: float,
        A_D1: float,
        f_0: float,
        l_D: float,
        d_be: float,
    ) -> float:
        if float(h_L_below) >= float(h_bc):
            return 0.0
        bracket = (
            0.7 * (float(A_D2) / float(A_D1)) ** 2 + 1.2 + float(f_0) * (float(l_D) / float(d_be))
        )
        return (
            (6.0 / (float(gravity) * float(rho_L) * float(rho_V)))
            * (float(V_D) * float(M_V) / (3600.0 * float(A_D2))) ** 2
            * bracket
        )

    @staticmethod
    def compute_flooding_velocity(F_1: float, F_2: float, sigma_L: float, rho_L: float) -> float:
        return float(F_1) * float(F_2) * (float(sigma_L) / float(rho_L)) ** 0.5

    @staticmethod
    def compute_liquid_height(h_bc: float, h_op: float, h_hu: float) -> float:
        return float(h_bc) + float(h_op) + float(h_hu)

    @staticmethod
    def compute_active_liquid_height(beta: float, h_w: float, h_ow: float, delta_p: float) -> float:
        return float(beta) * (float(h_w) + float(h_ow) + float(delta_p) / 2.0)

    @staticmethod
    def compute_weeping_flow_rate(
        *,
        A_h: float,
        h_dc: float,
        rho_L: float,
        rho_V: float,
        R_s: float,
        h_os: float,
        h_sh: float,
    ) -> float:
        density_factor = ((float(rho_L) - float(rho_V)) / float(rho_V)) ** 0.5
        bracket = (2.0 / (31.0 + float(R_s))) * float(h_os) ** 1.5 + (
            4.0 / (151.0 + float(R_s))
        ) * (1.0 - float(R_s) * float(h_os) / float(h_sh)) ** 2.5
        return 2.36 * (float(A_h) / float(h_dc)) * density_factor * bracket

    @staticmethod
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
        n_species = int(round(float(k[k_map["n_species"]])))
        n_plates = int(round(float(k[k_map["n_plates"]])))

        plate_holdup = np.asarray(y[y_map["plate_component_holdup"]], dtype=np.float64).reshape(
            n_plates, n_species
        )
        drum_holdup = np.asarray(y[y_map["reflux_drum_component_moles"]], dtype=np.float64).reshape(
            -1
        )
        reboiler_holdup = np.asarray(
            y[y_map["reboiler_component_moles"]], dtype=np.float64
        ).reshape(-1)
        plate_energy_holdup = np.asarray(
            y[y_map["plate_energy_holdup_j"]], dtype=np.float64
        ).reshape(-1)

        distillate_request = max(0.0, float(u[u_map["distillate_withdrawal_flow"]]))
        bottoms_request = max(0.0, float(u[u_map["bottoms_withdrawal_flow"]]))
        reflux_return_flow = max(0.0, float(u[u_map["reflux_return_flow"]]))
        reflux_return_comp = _normalize_composition(
            np.asarray(u[u_map["reflux_return_composition"]], dtype=np.float64).reshape(-1),
            n_species=n_species,
        )
        feed_temperature = float(u[u_map["feed_1_temperature"]])
        nominal_vapor = max(0.0, float(k[k_map["nominal_vapor_flow_mol_s"]]))
        nominal_liquid = max(0.0, float(k[k_map["nominal_liquid_flow_mol_s"]]))
        murphree_efficiency = max(1.0e-6, float(k[k_map["murphree_efficiency"]]))
        pressure_drop_nominal = max(1.0, float(k[k_map["hydraulic_pressure_drop_pa"]]))
        K_reference = np.asarray(k[k_map["equilibrium_reference_K"]], dtype=np.float64).reshape(-1)
        species_mw = np.asarray(
            k[k_map["species_molecular_weight_kg_mol"]], dtype=np.float64
        ).reshape(-1)
        cp_liq = np.asarray(
            k[k_map["species_liquid_heat_capacity_j_mol_k"]], dtype=np.float64
        ).reshape(-1)
        cp_vap = np.asarray(
            k[k_map["species_vapor_heat_capacity_j_mol_k"]], dtype=np.float64
        ).reshape(-1)
        dh_vap = np.asarray(
            k[k_map["species_vaporization_enthalpy_j_mol"]], dtype=np.float64
        ).reshape(-1)
        thermo_ref_T = float(k[k_map["thermo_reference_temperature_k"]])
        k_T_sensitivity = float(k[k_map["thermo_k_temperature_sensitivity"]])
        k_P_sensitivity = float(k[k_map["thermo_k_pressure_sensitivity"]])

        distillate_x = _normalize_composition(drum_holdup, n_species=n_species)
        bottoms_x = _normalize_composition(reboiler_holdup, n_species=n_species)

        distillate_flow = _realized_withdrawal_flow(
            requested_flow=distillate_request,
            owner_moles=drum_holdup,
        )
        bottoms_flow = _realized_withdrawal_flow(
            requested_flow=bottoms_request,
            owner_moles=reboiler_holdup,
        )

        plate_x = np.vstack(
            [_normalize_composition(plate_holdup[p], n_species=n_species) for p in range(n_plates)]
        )
        plate_total_holdup = np.asarray(np.sum(plate_holdup, axis=1), dtype=np.float64)

        liquid_molecular_weight = np.array(
            [
                Gani1986DistillationColumn.compute_mixture_molecular_weight(species_mw, plate_x[p])
                for p in range(n_plates)
            ],
            dtype=np.float64,
        )
        liquid_cp_mixture = np.maximum(
            np.array(
                [
                    Gani1986DistillationColumn.compute_mixture_molecular_weight(cp_liq, plate_x[p])
                    for p in range(n_plates)
                ],
                dtype=np.float64,
            ),
            1.0,
        )
        liquid_enthalpy = np.asarray(
            [
                float(plate_energy_holdup[p]) / max(float(plate_total_holdup[p]), _MIN_SUM)
                for p in range(n_plates)
            ],
            dtype=np.float64,
        )
        plate_temperature = np.clip(
            thermo_ref_T + liquid_enthalpy / liquid_cp_mixture,
            250.0,
            680.0,
        )

        pressure_top = max(
            float(u[u_map["feed_1_pressure"]]),
            float(u[u_map["reflux_return_pressure"]]),
            101325.0,
        )
        plate_pressure = np.array(
            [pressure_top + float(p) * pressure_drop_nominal for p in range(n_plates)],
            dtype=np.float64,
        )
        pressure_below = np.array(
            [
                plate_pressure[p + 1]
                if p < (n_plates - 1)
                else plate_pressure[p] + pressure_drop_nominal
                for p in range(n_plates)
            ],
            dtype=np.float64,
        )

        plate_delta_pressure = np.array(
            [
                Gani1986DistillationColumn.compute_pressure_drop(
                    pressure_below[p], plate_pressure[p]
                )
                for p in range(n_plates)
            ],
            dtype=np.float64,
        )

        R = 8.314462618
        sigma_liquid = 0.022
        A_p = 1.1
        A_D1 = 0.22
        A_D2 = 0.16
        W = 1.0
        h_w = 0.05
        h_bc = 0.05
        h_op = 0.02
        l_clearance = 0.03
        f_0 = 0.8
        l_D = 0.40
        d_be = 0.015
        A_h = 0.01
        h_dc = 0.05
        R_s = 0.6
        h_sh = 0.06
        F_1 = 0.8
        F_2 = 1.1

        plate_K = np.zeros((n_plates, n_species), dtype=np.float64)
        plate_y = np.zeros_like(plate_x)
        vapor_molecular_weight = np.zeros(n_plates, dtype=np.float64)
        liquid_density = np.zeros(n_plates, dtype=np.float64)
        vapor_density = np.zeros(n_plates, dtype=np.float64)
        vapor_enthalpy = np.zeros(n_plates, dtype=np.float64)

        y_above = distillate_x
        pressure_ref = max(pressure_top, 1.0)
        for p in range(n_plates):
            temp_factor = np.exp(
                k_T_sensitivity
                * (float(plate_temperature[p]) - thermo_ref_T)
                / max(thermo_ref_T, 1.0)
            )
            pressure_factor = np.exp(
                -k_P_sensitivity * (float(plate_pressure[p]) - pressure_ref) / pressure_ref
            )
            plate_K[p] = np.clip(K_reference * temp_factor * pressure_factor, 0.05, 25.0)
            y_star = _normalize_composition(
                Gani1986DistillationColumn.compute_equilibrium_composition(plate_K[p], plate_x[p]),
                n_species=n_species,
            )
            y_actual = Gani1986DistillationColumn.compute_equilibrium_from_murphree(
                y_star,
                y_above,
                murphree_efficiency,
            )
            plate_y[p] = _normalize_composition(y_actual, n_species=n_species)
            y_above = plate_y[p]

            Z_L = 0.25 + 0.75 * plate_x[p]
            Z_V = 0.85 + 0.15 * plate_y[p]
            rho_L_components = np.maximum(
                50.0,
                75.0
                * float(plate_pressure[p])
                * species_mw
                / (R * float(plate_temperature[p]) * Z_L),
            )
            rho_V_components = np.maximum(
                0.2,
                float(plate_pressure[p]) * species_mw / (R * float(plate_temperature[p]) * Z_V),
            )
            liquid_density[p] = float(np.dot(rho_L_components, plate_x[p]))
            vapor_density[p] = float(np.dot(rho_V_components, plate_y[p]))
            vapor_molecular_weight[p] = Gani1986DistillationColumn.compute_mixture_molecular_weight(
                species_mw, plate_y[p]
            )

            vapor_enthalpy_components = (
                cp_vap * (float(plate_temperature[p]) - thermo_ref_T) + dh_vap
            )
            vapor_enthalpy[p] = float(np.dot(vapor_enthalpy_components, plate_y[p]))

        h_ow = np.zeros(n_plates, dtype=np.float64)
        h_da = np.zeros(n_plates, dtype=np.float64)
        h_T = np.zeros(n_plates, dtype=np.float64)
        h_L = np.zeros(n_plates, dtype=np.float64)
        h_aL = np.zeros(n_plates, dtype=np.float64)
        q_weep = np.zeros(n_plates, dtype=np.float64)
        bubble_total_holdup = np.zeros(n_plates, dtype=np.float64)
        ref_holdup = max(float(np.mean(plate_total_holdup)), 1.0)

        for p in range(n_plates):
            rho_L = max(50.0, float(liquid_density[p]))
            rho_V = max(0.1, float(vapor_density[p]))
            M_L = max(1.0e-5, float(liquid_molecular_weight[p]))
            M_V = max(1.0e-5, float(vapor_molecular_weight[p]))
            delta_head = max(0.0, float(plate_delta_pressure[p])) / max(rho_L * 9.81, 1.0)

            L_D_p = max(1.0e-6, 0.03 * float(plate_total_holdup[p]) * M_L / rho_L)
            h_ow[p] = Gani1986DistillationColumn.compute_crest_height_over_weir(L_D_p, W, rho_L)

            g_L = max(1.0e-6, nominal_vapor * M_V / 3600.0)
            h_da[p] = Gani1986DistillationColumn.compute_dry_tray_pressure_drop(g_L, A_D1)

            h_L_below = float(h_L[p + 1]) if p < (n_plates - 1) else 0.8 * h_bc
            V_D = max(1.0, (nominal_vapor + 0.05 * float(plate_total_holdup[p])) * 3600.0)
            h_T[p] = Gani1986DistillationColumn.compute_downcomer_unsealed_tray_head(
                h_L_below=h_L_below,
                h_bc=h_bc,
                gravity=9.81,
                rho_L=rho_L,
                rho_V=rho_V,
                V_D=V_D,
                M_V=M_V,
                A_D2=A_D2,
                A_D1=A_D1,
                f_0=f_0,
                l_D=l_D,
                d_be=d_be,
            )

            h_op_local = h_op + 0.01 * (float(plate_total_holdup[p]) / max(ref_holdup, 1.0) - 1.0)
            h_L[p] = Gani1986DistillationColumn.compute_liquid_height(h_bc, h_op_local, h_T[p])
            h_aL[p] = Gani1986DistillationColumn.compute_active_liquid_height(
                1.0, h_w, h_ow[p], delta_head
            )

            h_os = max(
                1.0e-6,
                min(
                    h_sh / R_s * 0.95,
                    0.02
                    + 0.2 * float(h_ow[p])
                    + 0.08 * delta_head
                    + 0.01 * (float(plate_total_holdup[p]) / max(ref_holdup, 1.0) - 1.0),
                ),
            )
            q_weep[p] = Gani1986DistillationColumn.compute_weeping_flow_rate(
                A_h=A_h,
                h_dc=h_dc,
                rho_L=rho_L,
                rho_V=rho_V,
                R_s=R_s,
                h_os=h_os,
                h_sh=h_sh,
            )

            bubble_total_holdup[p] = (
                Gani1986DistillationColumn.compute_total_holdup_from_hydraulics(
                    beta=1.0,
                    h_w=h_w,
                    h_ow=h_ow[p],
                    A_p=A_p,
                    rho_L=rho_L,
                    M_L=M_L,
                    h_T=h_T[p],
                    h_da=h_da[p],
                    h_L=h_L[p],
                    l_clearance=l_clearance,
                    A_D2=A_D2,
                )
            )

        flooding_velocity = np.array(
            [
                Gani1986DistillationColumn.compute_flooding_velocity(
                    F_1,
                    F_2,
                    sigma_liquid,
                    max(50.0, float(liquid_density[p])),
                )
                for p in range(n_plates)
            ],
            dtype=np.float64,
        )

        plate_vapor_flow = np.clip(
            nominal_vapor
            * (1.0 + 0.35 * np.maximum(plate_delta_pressure, 0.0) / max(pressure_drop_nominal, 1.0))
            * (1.0 + 0.10 * flooding_velocity / np.maximum(flooding_velocity + 0.1, 1.0e-6))
            * (1.0 + 0.08 * (bubble_total_holdup - plate_total_holdup) / ref_holdup),
            0.05,
            30.0,
        )
        plate_liquid_flow = np.clip(
            nominal_liquid
            + 3.0 * np.maximum(h_ow, 0.0)
            + 45.0 * np.maximum(q_weep, 0.0)
            + 0.02 * np.maximum(bubble_total_holdup - plate_total_holdup, 0.0),
            0.05,
            30.0,
        )
        plate_liquid_entrainment = np.clip(
            0.02 * np.maximum(plate_liquid_flow - nominal_liquid, 0.0)
            + 0.004 * np.maximum(plate_delta_pressure, 0.0) / 1000.0,
            0.0,
            5.0,
        )
        plate_vapor_entrainment = np.clip(
            0.015 * np.maximum(plate_vapor_flow - nominal_vapor, 0.0)
            + 0.03 * np.maximum(h_aL, 0.0),
            0.0,
            5.0,
        )

        reboiler_x = _normalize_composition(reboiler_holdup, n_species=n_species)
        y_reboiler_star = Gani1986DistillationColumn.compute_equilibrium_composition(
            plate_K[-1], reboiler_x
        )
        y_reboiler = _normalize_composition(y_reboiler_star, n_species=n_species)
        reboiler_vapor_flow = max(
            0.05, 1.05 * plate_vapor_flow[-1] + 0.06 * np.sum(reboiler_holdup)
        )

        reflux_to_column = _realized_withdrawal_flow(
            requested_flow=plate_liquid_flow[0],
            owner_moles=drum_holdup,
        )

        plate0_x = plate_x[0]
        plateN_x = plate_x[-1]

        algebraic = np.zeros(algebraic_size, dtype=np.float64)
        algebraic[algebraic_map["distillate_flow"]] = distillate_flow
        algebraic[algebraic_map["bottoms_flow"]] = bottoms_flow
        algebraic[algebraic_map["distillate_temperature"]] = float(plate_temperature[0])
        algebraic[algebraic_map["bottoms_temperature"]] = float(plate_temperature[-1])
        algebraic[algebraic_map["distillate_composition"]] = _normalize_composition(
            0.7 * distillate_x + 0.3 * plate0_x,
            n_species=n_species,
        )
        algebraic[algebraic_map["bottoms_composition"]] = _normalize_composition(
            0.7 * bottoms_x + 0.3 * plateN_x,
            n_species=n_species,
        )
        algebraic[algebraic_map["plate_liquid_composition"]] = plate_x.reshape(-1)
        algebraic[algebraic_map["plate_vapor_composition"]] = plate_y.reshape(-1)
        algebraic[algebraic_map["plate_vapor_flow_mol_s"]] = plate_vapor_flow
        algebraic[algebraic_map["plate_liquid_flow_mol_s"]] = plate_liquid_flow
        algebraic[algebraic_map["plate_liquid_entrainment_mol_s"]] = plate_liquid_entrainment
        algebraic[algebraic_map["plate_vapor_entrainment_mol_s"]] = plate_vapor_entrainment
        feed_flow = max(0.0, float(u[u_map["feed_1_flow"]]))
        feed_plate = max(0, min(n_plates - 1, n_plates // 2))
        plate_total_mass_rhs = np.zeros(n_plates, dtype=np.float64)
        for p in range(n_plates):
            V_below = reboiler_vapor_flow if p == (n_plates - 1) else float(plate_vapor_flow[p + 1])
            L_above = (
                reflux_to_column + reflux_return_flow if p == 0 else float(plate_liquid_flow[p - 1])
            )
            E_L_below = float(plate_liquid_entrainment[p + 1]) if p < (n_plates - 1) else 0.0
            E_V_above = float(plate_vapor_entrainment[p - 1]) if p > 0 else 0.0
            F_L = feed_flow if p == feed_plate else 0.0
            plate_total_mass_rhs[p] = Gani1986DistillationColumn.calculate_total_mass_balance_rhs(
                V_below=V_below,
                V_plate=float(plate_vapor_flow[p]),
                L_above=L_above,
                L_plate=float(plate_liquid_flow[p]),
                E_L_below=E_L_below,
                E_V_above=E_V_above,
                E_L_plate=float(plate_liquid_entrainment[p]),
                E_V_plate=float(plate_vapor_entrainment[p]),
                P_L=0.0,
                P_V=0.0,
                F_L=F_L,
                F_V=0.0,
            )

        algebraic[algebraic_map["plate_total_mass_balance_rhs_mol_s"]] = plate_total_mass_rhs
        algebraic[algebraic_map["plate_pressure_drop_pa"]] = plate_delta_pressure
        algebraic[algebraic_map["reflux_to_column_flow_mol_s"]] = reflux_to_column
        algebraic[algebraic_map["reboiler_vapor_flow_mol_s"]] = reboiler_vapor_flow
        algebraic[algebraic_map["reboiler_vapor_composition"]] = y_reboiler
        algebraic[algebraic_map["plate_temperature_k"]] = plate_temperature
        algebraic[algebraic_map["plate_liquid_enthalpy_j_mol"]] = liquid_enthalpy
        algebraic[algebraic_map["plate_vapor_enthalpy_j_mol"]] = vapor_enthalpy
        algebraic[algebraic_map["plate_equilibrium_K_values"]] = plate_K.reshape(-1)
        algebraic[algebraic_map["plate_liquid_density_kg_m3"]] = liquid_density
        algebraic[algebraic_map["plate_vapor_density_kg_m3"]] = vapor_density
        algebraic[algebraic_map["plate_liquid_molecular_weight_kg_mol"]] = liquid_molecular_weight
        algebraic[algebraic_map["plate_vapor_molecular_weight_kg_mol"]] = vapor_molecular_weight
        algebraic[algebraic_map["plate_bubblecap_crest_height_m"]] = h_ow
        algebraic[algebraic_map["plate_bubblecap_dry_tray_drop_m"]] = h_da
        algebraic[algebraic_map["plate_bubblecap_total_holdup_mol"]] = bubble_total_holdup
        algebraic[algebraic_map["plate_bubblecap_liquid_height_m"]] = h_L
        algebraic[algebraic_map["plate_bubblecap_active_liquid_height_m"]] = h_aL
        algebraic[algebraic_map["plate_bubblecap_weeping_flow_m3_s"]] = q_weep
        return algebraic

    @staticmethod
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
        del t

        n_species = int(round(float(k[k_map["n_species"]])))
        n_plates = int(round(float(k[k_map["n_plates"]])))
        feed_plate = max(0, min(n_plates - 1, n_plates // 2))

        feed_flow = max(0.0, float(u[u_map["feed_1_flow"]]))
        feed_comp = _normalize_composition(
            np.asarray(u[u_map["feed_1_composition"]], dtype=np.float64).reshape(-1),
            n_species=n_species,
        )
        feed_temperature = float(u[u_map["feed_1_temperature"]])
        reflux_flow = max(0.0, float(u[u_map["reflux_return_flow"]]))
        reflux_comp = _normalize_composition(
            np.asarray(u[u_map["reflux_return_composition"]], dtype=np.float64).reshape(-1),
            n_species=n_species,
        )

        distillate_flow = max(0.0, float(algebraic[algebraic_map["distillate_flow"]]))
        bottoms_flow = max(0.0, float(algebraic[algebraic_map["bottoms_flow"]]))
        distillate_x = _normalize_composition(
            np.asarray(
                algebraic[algebraic_map["distillate_composition"]], dtype=np.float64
            ).reshape(-1),
            n_species=n_species,
        )
        bottoms_x = _normalize_composition(
            np.asarray(algebraic[algebraic_map["bottoms_composition"]], dtype=np.float64).reshape(
                -1
            ),
            n_species=n_species,
        )

        plate_holdup = np.asarray(y[y_map["plate_component_holdup"]], dtype=np.float64).reshape(
            n_plates, n_species
        )
        plate_energy_holdup = np.asarray(
            y[y_map["plate_energy_holdup_j"]], dtype=np.float64
        ).reshape(-1)
        plate_x = np.asarray(
            algebraic[algebraic_map["plate_liquid_composition"]], dtype=np.float64
        ).reshape(n_plates, n_species)
        plate_y = np.asarray(
            algebraic[algebraic_map["plate_vapor_composition"]], dtype=np.float64
        ).reshape(n_plates, n_species)
        plate_liquid_enthalpy = np.asarray(
            algebraic[algebraic_map["plate_liquid_enthalpy_j_mol"]], dtype=np.float64
        ).reshape(-1)
        plate_vapor_enthalpy = np.asarray(
            algebraic[algebraic_map["plate_vapor_enthalpy_j_mol"]], dtype=np.float64
        ).reshape(-1)
        plate_vapor_flow = np.asarray(
            algebraic[algebraic_map["plate_vapor_flow_mol_s"]], dtype=np.float64
        ).reshape(-1)
        plate_liquid_flow = np.asarray(
            algebraic[algebraic_map["plate_liquid_flow_mol_s"]], dtype=np.float64
        ).reshape(-1)
        plate_liquid_entrainment = np.asarray(
            algebraic[algebraic_map["plate_liquid_entrainment_mol_s"]], dtype=np.float64
        ).reshape(-1)
        plate_vapor_entrainment = np.asarray(
            algebraic[algebraic_map["plate_vapor_entrainment_mol_s"]], dtype=np.float64
        ).reshape(-1)
        reflux_to_column = max(0.0, float(algebraic[algebraic_map["reflux_to_column_flow_mol_s"]]))
        reboiler_vapor_flow = max(0.0, float(algebraic[algebraic_map["reboiler_vapor_flow_mol_s"]]))
        reboiler_y = _normalize_composition(
            np.asarray(
                algebraic[algebraic_map["reboiler_vapor_composition"]], dtype=np.float64
            ).reshape(-1),
            n_species=n_species,
        )
        thermo_ref_T = float(k[k_map["thermo_reference_temperature_k"]])
        cp_liq = np.asarray(
            k[k_map["species_liquid_heat_capacity_j_mol_k"]], dtype=np.float64
        ).reshape(-1)
        cp_vap = np.asarray(
            k[k_map["species_vapor_heat_capacity_j_mol_k"]], dtype=np.float64
        ).reshape(-1)
        dh_vap = np.asarray(
            k[k_map["species_vaporization_enthalpy_j_mol"]], dtype=np.float64
        ).reshape(-1)
        feed_liquid_enthalpy = float(np.dot(cp_liq, feed_comp) * (feed_temperature - thermo_ref_T))
        feed_vapor_enthalpy = float(feed_liquid_enthalpy + np.dot(dh_vap, feed_comp))
        reboiler_vapor_enthalpy = float(
            np.dot(
                cp_vap * (float(algebraic[algebraic_map["bottoms_temperature"]]) - thermo_ref_T)
                + dh_vap,
                reboiler_y,
            )
        )

        reflux_feed_comp = _normalize_composition(
            reflux_to_column * distillate_x + reflux_flow * reflux_comp,
            n_species=n_species,
        )

        d_plate = np.zeros_like(plate_holdup)
        plate_total_rhs = np.zeros(n_plates, dtype=np.float64)
        d_plate_energy = np.zeros(n_plates, dtype=np.float64)
        zero_feed = np.zeros(n_species, dtype=np.float64)
        for p in range(n_plates):
            x_above = reflux_feed_comp if p == 0 else plate_x[p - 1]
            y_below = reboiler_y if p == (n_plates - 1) else plate_y[p + 1]
            V_below = reboiler_vapor_flow if p == (n_plates - 1) else float(plate_vapor_flow[p + 1])
            L_above = reflux_to_column + reflux_flow if p == 0 else float(plate_liquid_flow[p - 1])
            E_L_below = float(plate_liquid_entrainment[p + 1]) if p < (n_plates - 1) else 0.0
            E_V_above = float(plate_vapor_entrainment[p - 1]) if p > 0 else 0.0

            # Entrainment source-plate compositions (GE-G86-1):
            #   E_L_{p-1} entrains liquid from plate p-1 -> carries x_{p-1}
            #   E_V_{p+1} entrains vapor from plate p+1 -> carries y_{p+1}
            x_below_entrainment = plate_x[p + 1] if p < (n_plates - 1) else bottoms_x
            y_above_entrainment = plate_y[p - 1] if p > 0 else distillate_x

            F_L = feed_flow if p == feed_plate else 0.0
            x_F = feed_comp if p == feed_plate else zero_feed

            for i in range(n_species):
                d_plate[p, i] = Gani1986DistillationColumn.calculate_component_balance_rhs(
                    plate_index=p,
                    component_index=i,
                    x_above=x_above,
                    y_below=y_below,
                    x_plate=plate_x[p],
                    y_plate=plate_y[p],
                    V_below=V_below,
                    V_plate=float(plate_vapor_flow[p]),
                    L_above=L_above,
                    L_plate=float(plate_liquid_flow[p]),
                    E_L_below=E_L_below,
                    E_V_above=E_V_above,
                    E_L_plate=float(plate_liquid_entrainment[p]),
                    E_V_plate=float(plate_vapor_entrainment[p]),
                    P_L=0.0,
                    P_V=0.0,
                    F_L=F_L,
                    F_V=0.0,
                    x_F_L=x_F,
                    y_F_V=zero_feed,
                    x_below=x_below_entrainment,
                    y_above=y_above_entrainment,
                )

            total_rhs = Gani1986DistillationColumn.calculate_total_mass_balance_rhs(
                V_below=V_below,
                V_plate=float(plate_vapor_flow[p]),
                L_above=L_above,
                L_plate=float(plate_liquid_flow[p]),
                E_L_below=E_L_below,
                E_V_above=E_V_above,
                E_L_plate=float(plate_liquid_entrainment[p]),
                E_V_plate=float(plate_vapor_entrainment[p]),
                P_L=0.0,
                P_V=0.0,
                F_L=F_L,
                F_V=0.0,
            )
            plate_total_rhs[p] = total_rhs
            correction = total_rhs - float(np.sum(d_plate[p]))
            d_plate[p] += correction * plate_x[p]

            H_below = (
                reboiler_vapor_enthalpy
                if p == (n_plates - 1)
                else float(plate_vapor_enthalpy[p + 1])
            )
            h_above = (
                float(plate_liquid_enthalpy[0]) if p == 0 else float(plate_liquid_enthalpy[p - 1])
            )

            # Entrainment source-plate enthalpies (GE-G86-2):
            #   E_L_{p-1} entrains liquid from plate p-1 -> carries h_{p-1}
            #   E_V_{p+1} entrains vapor from plate p+1 -> carries H_{p+1}
            h_below_entrainment = (
                float(plate_liquid_enthalpy[p + 1])
                if p < (n_plates - 1)
                else float(plate_liquid_enthalpy[-1])
            )
            H_above_entrainment = (
                float(plate_vapor_enthalpy[p - 1]) if p > 0 else float(plate_vapor_enthalpy[0])
            )

            d_plate_energy[p] = Gani1986DistillationColumn.calculate_energy_balance_rhs(
                plate_index=p,
                H_below=H_below,
                H_plate=float(plate_vapor_enthalpy[p]),
                h_above=h_above,
                h_plate=float(plate_liquid_enthalpy[p]),
                V_below=V_below,
                V_plate=float(plate_vapor_flow[p]),
                L_above=L_above,
                L_plate=float(plate_liquid_flow[p]),
                E_L_below=E_L_below,
                E_V_above=E_V_above,
                E_L_plate=float(plate_liquid_entrainment[p]),
                E_V_plate=float(plate_vapor_entrainment[p]),
                P_L=0.0,
                P_V=0.0,
                F_L=F_L,
                F_V=0.0,
                H_F_V=feed_vapor_enthalpy,
                h_F_L=feed_liquid_enthalpy,
                h_below=h_below_entrainment,
                H_above=H_above_entrainment,
            )

        d_drum = np.zeros(n_species, dtype=np.float64)
        d_reboiler = np.zeros(n_species, dtype=np.float64)
        for i in range(n_species):
            d_drum[i] = Gani1986DistillationColumn.calculate_reflux_drum_balance_rhs(
                component_index=i,
                y_top_plate=plate_y[0],
                x_distillate=distillate_x,
                V_top_plate=float(plate_vapor_flow[0]),
                L_reflux=reflux_to_column,
                D_distillate=distillate_flow,
            )
            d_reboiler[i] = Gani1986DistillationColumn.calculate_reboiler_balance_rhs(
                component_index=i,
                x_bottom_plate=plate_x[-1],
                x_bottoms=bottoms_x,
                y_bottoms=reboiler_y,
                L_bottom_plate=float(plate_liquid_flow[-1]),
                B_bottoms=bottoms_flow,
                V_reboiler=reboiler_vapor_flow,
            )

        dy = np.zeros_like(y)
        dy[y_map["plate_component_holdup"]] = d_plate.reshape(-1)
        dy[y_map["reflux_drum_component_moles"]] = d_drum
        dy[y_map["reboiler_component_moles"]] = d_reboiler
        dy[y_map["plate_energy_holdup_j"]] = d_plate_energy
        return dy


__all__ = ["Gani1986DistillationColumn"]
