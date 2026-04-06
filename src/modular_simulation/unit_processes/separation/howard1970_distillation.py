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
_REFERENCE_TEMPERATURE_K = 298.15


def _normalize_composition(raw: NDArray[np.float64], *, n_species: int) -> NDArray[np.float64]:
    values = np.asarray(raw, dtype=np.float64).reshape(-1)
    if values.size != n_species:
        raise ValueError(f"composition length mismatch: expected {n_species}, got {values.size}.")
    if np.any(values < 0.0):
        raise ValueError("composition must contain non-negative values.")
    total = float(np.sum(values))
    if total <= _MIN_SUM:
        return np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
    return values / total


def _realized_withdrawal_flow(*, requested_flow: float, owner_moles: NDArray[np.float64]) -> float:
    request = max(0.0, float(requested_flow))
    inventory = max(0.0, float(np.sum(owner_moles)))
    inventory_limited = inventory / 4.0
    return min(request, inventory_limited)


def _safe_normalize(raw: NDArray[np.float64], *, n_species: int) -> NDArray[np.float64]:
    values = np.asarray(raw, dtype=np.float64).reshape(-1)
    if values.size != n_species:
        raise ValueError(f"vector length mismatch: expected {n_species}, got {values.size}.")
    values = np.clip(values, 0.0, None)
    total = float(np.sum(values))
    if total <= _MIN_SUM:
        return np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
    return values / total


class Howard1970DistillationColumn(ProcessModel):
    plate_component_holdup: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="mol", description="plate component holdup (flattened)"),
    ] = np.zeros(0, dtype=np.float64)
    reflux_drum_component_moles: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="mol", description="reflux drum component holdup"),
    ] = np.zeros(0, dtype=np.float64)
    column_pressure_pa: Annotated[
        float,
        M(type=T.DIFFERENTIAL, unit="Pa", description="column pressure"),
    ] = 101325.0
    plate_temperature_K: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="K", description="plate liquid temperatures"),
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
    feed_plate_index: Annotated[
        int, M(type=T.CONSTANT, unit="", description="feed plate index")
    ] = 1
    plate_reference_volume_m3: Annotated[
        float,
        M(type=T.CONSTANT, unit="m3", description="Howard constant liquid volume per plate"),
    ] = 0.08
    nominal_vapor_flow_mol_s: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol/s", description="nominal plate vapor flow"),
    ] = 6.0
    nominal_liquid_flow_mol_s: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol/s", description="nominal plate liquid flow"),
    ] = 5.0
    reference_molar_volumes_m3_per_mol: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="m3/mol", description="pure-component liquid molar volumes"),
    ] = np.zeros(0, dtype=np.float64)
    component_molar_volume_temperature_coefficient_m3_per_mol_K: Annotated[
        NDArray[np.float64],
        M(
            type=T.CONSTANT,
            unit="m3/(mol K)",
            description="linear temperature coefficients for pure-component liquid molar volumes",
        ),
    ] = np.zeros(0, dtype=np.float64)
    equilibrium_reference_K: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="", description="reference K-values at Tref"),
    ] = np.zeros(0, dtype=np.float64)
    equilibrium_temperature_sensitivity_per_K: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="1/K", description="K-value temperature sensitivity"),
    ] = np.zeros(0, dtype=np.float64)
    equilibrium_pressure_exponent: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="", description="K-value pressure sensitivity exponent"),
    ] = np.zeros(0, dtype=np.float64)
    equilibrium_reference_pressure_pa: Annotated[
        float,
        M(type=T.CONSTANT, unit="Pa", description="reference pressure for K-values"),
    ] = 101325.0
    plate_pressure_drop_pa: Annotated[
        float,
        M(type=T.CONSTANT, unit="Pa", description="per-plate pressure rise from condenser"),
    ] = 2500.0
    component_heat_capacity_j_per_mol_K: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/(mol K)", description="component heat capacities"),
    ] = np.zeros(0, dtype=np.float64)
    vaporization_efficiency_reference: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="", description="Howard Eq. 7 efficiency factors"),
    ] = np.zeros(0, dtype=np.float64)
    vapor_enthalpy_offset_j_per_mol: Annotated[
        float,
        M(type=T.CONSTANT, unit="J/mol", description="vapor enthalpy offset above liquid"),
    ] = 28000.0
    temperature_relaxation_time_s: Annotated[
        float,
        M(type=T.CONSTANT, unit="s", description="plate temperature relaxation timescale"),
    ] = 25.0
    pressure_relaxation_time_s: Annotated[
        float,
        M(type=T.CONSTANT, unit="s", description="column pressure relaxation timescale"),
    ] = 20.0
    energy_balance_A_term_j_per_mol: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/mol", description="Howard Eq. 14 named closure term A_j"),
    ] = np.zeros(0, dtype=np.float64)
    energy_balance_B_term_j_per_mol: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/mol", description="Howard Eq. 14 named closure term B_j"),
    ] = np.zeros(0, dtype=np.float64)
    energy_balance_C_term_j_per_mol: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/mol", description="Howard Eq. 14 named closure term C_j"),
    ] = np.zeros(0, dtype=np.float64)
    plate_heat_loss_j_per_s: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/s", description="Howard Eq. 14 named heat-loss term Q_Lj"),
    ] = np.zeros(0, dtype=np.float64)
    feed_energy_closure_D_term_j_per_mol: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/mol", description="Howard Eq. 25 feed-energy closure term D_j"),
    ] = np.zeros(0, dtype=np.float64)

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
        M(type=T.ALGEBRAIC, unit="", description="per-plate liquid compositions (flattened)"),
    ] = np.zeros(0, dtype=np.float64)
    plate_vapor_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="per-plate vapor compositions (flattened)"),
    ] = np.zeros(0, dtype=np.float64)
    plate_K_values: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="per-plate equilibrium K-values (flattened)"),
    ] = np.zeros(0, dtype=np.float64)
    plate_vaporization_efficiency: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="per-plate vaporization efficiency (flattened)"),
    ] = np.zeros(0, dtype=np.float64)
    plate_vapor_flow_mol_s: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="per-plate vapor flows"),
    ] = np.zeros(0, dtype=np.float64)
    plate_liquid_flow_mol_s: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="per-plate liquid flows"),
    ] = np.zeros(0, dtype=np.float64)
    plate_liquid_enthalpy_j_per_mol: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="J/mol", description="per-plate liquid enthalpy"),
    ] = np.zeros(0, dtype=np.float64)
    plate_vapor_enthalpy_j_per_mol: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="J/mol", description="per-plate vapor enthalpy"),
    ] = np.zeros(0, dtype=np.float64)
    plate_bubble_point_residual: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="bubble-point closure residual per plate"),
    ] = np.zeros(0, dtype=np.float64)
    plate_holdup_target_mol: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol", description="constant-volume target holdup per plate"),
    ] = np.zeros(0, dtype=np.float64)
    plate_flow_closure_residual: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="Howard Eq. 29 residual per plate"),
    ] = np.zeros(0, dtype=np.float64)
    plate_eq29_temperature_closure: Annotated[
        NDArray[np.float64],
        M(
            type=T.ALGEBRAIC,
            unit="mol/s",
            description=(
                "Howard Eq. (29) temperature closure correction per plate: "
                "V_bar * (dv/dt_full - dv/dt_comp), needed to satisfy "
                "Eq. (29) exactly under temperature-dependent molar-volume dynamics."
            ),
        ),
    ] = np.zeros(0, dtype=np.float64)
    plate_molar_volume_time_derivative_m3_per_mol_s: Annotated[
        NDArray[np.float64],
        M(
            type=T.ALGEBRAIC,
            unit="m3/(mol s)",
            description="Howard Eq. 28 liquid molar-volume derivative per plate",
        ),
    ] = np.zeros(0, dtype=np.float64)
    plate_F_coefficient: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="Howard Eq. 30 F_j coefficients"),
    ] = np.zeros(0, dtype=np.float64)
    plate_G_coefficient: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="Howard Eq. 30 G_j coefficients"),
    ] = np.zeros(0, dtype=np.float64)
    plate_K_coefficient: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="Howard Eq. 30 K_j coefficients"),
    ] = np.zeros(0, dtype=np.float64)
    plate_pressure_pa: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="Pa", description="per-plate pressure used in K(T,P)"),
    ] = np.zeros(0, dtype=np.float64)
    plate_energy_balance_residual_j_per_s: Annotated[
        NDArray[np.float64],
        M(
            type=T.ALGEBRAIC,
            unit="J/s",
            description="Howard Eq. 14 residual per plate",
        ),
    ] = np.zeros(0, dtype=np.float64)
    reflux_to_column_flow_mol_s: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="mol/s",
            description="realized reflux return from drum to top plate",
        ),
    ] = 0.0

    _ports: UnitProcessPorts = UnitProcessPorts(
        ("feed_1", "reflux_return"), ("distillate", "bottoms")
    )

    @property
    def ports(self) -> UnitProcessPorts:
        return self._ports

    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        if self.n_species <= 1:
            raise ValueError("n_species must be at least 2 for Howard1970DistillationColumn.")
        if self.n_plates <= 0:
            raise ValueError("n_plates must be positive.")

        expected_plate_size = self.n_species * self.n_plates
        if self.plate_component_holdup.size != expected_plate_size:
            self.plate_component_holdup = np.full(
                expected_plate_size,
                10.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.reflux_drum_component_moles.size != self.n_species:
            self.reflux_drum_component_moles = np.full(
                self.n_species,
                5.0 / float(self.n_species),
                dtype=np.float64,
            )
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
            self.reflux_return_composition,
            n_species=self.n_species,
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
        if self.plate_temperature_K.size != self.n_plates:
            self.plate_temperature_K = np.linspace(
                335.0,
                365.0,
                self.n_plates,
                dtype=np.float64,
            )

        if self.reference_molar_volumes_m3_per_mol.size != self.n_species:
            self.reference_molar_volumes_m3_per_mol = np.linspace(
                0.075,
                0.115,
                self.n_species,
                dtype=np.float64,
            )
        if self.equilibrium_reference_K.size != self.n_species:
            self.equilibrium_reference_K = np.linspace(
                2.0,
                0.6,
                self.n_species,
                dtype=np.float64,
            )
        if self.component_molar_volume_temperature_coefficient_m3_per_mol_K.size != self.n_species:
            self.component_molar_volume_temperature_coefficient_m3_per_mol_K = np.linspace(
                1.0e-5,
                3.0e-5,
                self.n_species,
                dtype=np.float64,
            )
        if self.equilibrium_temperature_sensitivity_per_K.size != self.n_species:
            self.equilibrium_temperature_sensitivity_per_K = np.linspace(
                0.004,
                0.0015,
                self.n_species,
                dtype=np.float64,
            )
        if self.equilibrium_pressure_exponent.size != self.n_species:
            self.equilibrium_pressure_exponent = np.linspace(
                0.55,
                0.20,
                self.n_species,
                dtype=np.float64,
            )
        if self.component_heat_capacity_j_per_mol_K.size != self.n_species:
            self.component_heat_capacity_j_per_mol_K = np.linspace(
                105.0,
                145.0,
                self.n_species,
                dtype=np.float64,
            )
        if self.vaporization_efficiency_reference.size != self.n_species:
            self.vaporization_efficiency_reference = np.full(
                self.n_species,
                0.85,
                dtype=np.float64,
            )
        self.feed_plate_index = int(np.clip(self.feed_plate_index, 0, self.n_plates - 1))

        plate_flat_size = self.n_plates * self.n_species
        if self.plate_liquid_composition.size != plate_flat_size:
            self.plate_liquid_composition = np.full(
                plate_flat_size,
                1.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.plate_vapor_composition.size != plate_flat_size:
            self.plate_vapor_composition = np.full(
                plate_flat_size,
                1.0 / float(self.n_species),
                dtype=np.float64,
            )
        if self.plate_K_values.size != plate_flat_size:
            self.plate_K_values = np.tile(self.equilibrium_reference_K, self.n_plates)
        if self.plate_vaporization_efficiency.size != plate_flat_size:
            self.plate_vaporization_efficiency = np.tile(
                self.vaporization_efficiency_reference,
                self.n_plates,
            )
        if self.plate_vapor_flow_mol_s.size != self.n_plates:
            self.plate_vapor_flow_mol_s = np.full(self.n_plates, self.nominal_vapor_flow_mol_s)
        if self.plate_liquid_flow_mol_s.size != self.n_plates:
            self.plate_liquid_flow_mol_s = np.full(self.n_plates, self.nominal_liquid_flow_mol_s)
        if self.plate_liquid_enthalpy_j_per_mol.size != self.n_plates:
            self.plate_liquid_enthalpy_j_per_mol = np.full(self.n_plates, 0.0)
        if self.plate_vapor_enthalpy_j_per_mol.size != self.n_plates:
            self.plate_vapor_enthalpy_j_per_mol = np.full(
                self.n_plates, self.vapor_enthalpy_offset_j_per_mol
            )
        if self.plate_bubble_point_residual.size != self.n_plates:
            self.plate_bubble_point_residual = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_holdup_target_mol.size != self.n_plates:
            self.plate_holdup_target_mol = np.full(self.n_plates, 10.0, dtype=np.float64)
        if self.plate_flow_closure_residual.size != self.n_plates:
            self.plate_flow_closure_residual = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_molar_volume_time_derivative_m3_per_mol_s.size != self.n_plates:
            self.plate_molar_volume_time_derivative_m3_per_mol_s = np.zeros(
                self.n_plates, dtype=np.float64
            )
        if self.plate_eq29_temperature_closure.size != self.n_plates:
            self.plate_eq29_temperature_closure = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_F_coefficient.size != self.n_plates:
            self.plate_F_coefficient = np.full(self.n_plates, 0.02, dtype=np.float64)
        if self.plate_G_coefficient.size != self.n_plates:
            self.plate_G_coefficient = np.full(self.n_plates, 0.02, dtype=np.float64)
        if self.plate_K_coefficient.size != self.n_plates:
            self.plate_K_coefficient = np.full(self.n_plates, 0.02, dtype=np.float64)
        if self.plate_pressure_pa.size != self.n_plates:
            self.plate_pressure_pa = np.linspace(
                self.column_pressure_pa,
                self.column_pressure_pa + float(self.n_plates - 1) * self.plate_pressure_drop_pa,
                self.n_plates,
                dtype=np.float64,
            )
        if self.plate_energy_balance_residual_j_per_s.size != self.n_plates:
            self.plate_energy_balance_residual_j_per_s = np.zeros(self.n_plates, dtype=np.float64)
        if self.energy_balance_A_term_j_per_mol.size != self.n_plates:
            self.energy_balance_A_term_j_per_mol = np.zeros(self.n_plates, dtype=np.float64)
        if self.energy_balance_B_term_j_per_mol.size != self.n_plates:
            self.energy_balance_B_term_j_per_mol = np.zeros(self.n_plates, dtype=np.float64)
        if self.energy_balance_C_term_j_per_mol.size != self.n_plates:
            self.energy_balance_C_term_j_per_mol = np.zeros(self.n_plates, dtype=np.float64)
        if self.plate_heat_loss_j_per_s.size != self.n_plates:
            self.plate_heat_loss_j_per_s = np.zeros(self.n_plates, dtype=np.float64)
        if self.feed_energy_closure_D_term_j_per_mol.size != self.n_plates:
            self.feed_energy_closure_D_term_j_per_mol = np.zeros(self.n_plates, dtype=np.float64)

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
        if port_name == "distillate":
            return StreamData(
                temperature=float(self.distillate_temperature),
                pressure=float(self.column_pressure_pa),
                mole_fractions=tuple(float(x) for x in self.distillate_composition),
                molar_flow_rate=float(max(0.0, self.distillate_flow)),
            )
        return StreamData(
            temperature=float(self.bottoms_temperature),
            pressure=float(self.column_pressure_pa),
            mole_fractions=tuple(float(x) for x in self.bottoms_composition),
            molar_flow_rate=float(max(0.0, self.bottoms_flow)),
        )

    @staticmethod
    def calculate_component_balance_rhs(
        *,
        plate_index: int,
        component_index: int,
        x_plate: NDArray[np.float64],
        y_plate: NDArray[np.float64],
        V_above: float,
        V_plate: float,
        L_below: float,
        R_plate: float,
    ) -> float:
        j = int(plate_index)
        i = int(component_index)
        return (
            float(V_above) * (float(y_plate[j + 1, i]) - float(x_plate[j, i]))
            + float(L_below) * (float(x_plate[j - 1, i]) - float(x_plate[j, i]))
            - float(V_plate) * (float(y_plate[j, i]) - float(x_plate[j, i]))
        ) / float(R_plate)

    @staticmethod
    def compute_equilibrium_vapor(
        K_values: NDArray[np.float64],
        x_values: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        return np.asarray(K_values, dtype=np.float64) * np.asarray(x_values, dtype=np.float64)

    @staticmethod
    def compute_k_values(
        *,
        reference_K: NDArray[np.float64],
        dK_dT: NDArray[np.float64],
        pressure_exponent: NDArray[np.float64],
        temperature_K: float,
        pressure_pa: float,
        reference_temperature_K: float = _REFERENCE_TEMPERATURE_K,
        reference_pressure_pa: float = 101325.0,
    ) -> NDArray[np.float64]:
        K_ref = np.asarray(reference_K, dtype=np.float64)
        dK = np.asarray(dK_dT, dtype=np.float64)
        alpha = np.asarray(pressure_exponent, dtype=np.float64)
        temperature_shift = float(temperature_K) - float(reference_temperature_K)
        pressure_ratio = max(1.0e-3, float(reference_pressure_pa)) / max(1.0e-3, float(pressure_pa))
        pressure_factor = np.power(pressure_ratio, np.clip(alpha, 0.0, 2.0))
        return np.clip((K_ref + dK * temperature_shift) * pressure_factor, 0.05, 10.0)

    @staticmethod
    def compute_vaporization_efficiency(
        y_values: NDArray[np.float64],
        y_star_values: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        return np.asarray(y_values, dtype=np.float64) / np.asarray(y_star_values, dtype=np.float64)

    @staticmethod
    def compute_murphree_efficiency(
        y_j: NDArray[np.float64],
        y_j_minus_1: NDArray[np.float64],
        y_star_j: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        yj = np.asarray(y_j, dtype=np.float64)
        yjm1 = np.asarray(y_j_minus_1, dtype=np.float64)
        ystar = np.asarray(y_star_j, dtype=np.float64)
        denominator = ystar - yjm1
        return np.divide(
            yj - yjm1,
            denominator,
            out=np.ones_like(yj),
            where=np.abs(denominator) > _MIN_SUM,
        )

    @staticmethod
    def compute_eq29_coefficients_from_eq28(
        *,
        R_plate: float,
        V_bar: float,
        pure_component_molar_volumes: NDArray[np.float64],
        x_j: NDArray[np.float64],
        x_j_minus_1: NDArray[np.float64],
        y_j: NDArray[np.float64],
        y_j_plus_1: NDArray[np.float64],
    ) -> tuple[float, float, float]:
        """Deterministically derive Eq. (29) coefficients from Eq. (28).

        Returns the source-exact composition-only Howard Eq. (30)
        coefficients: V_bar/R_j dotted with the appropriate composition
        difference vectors.  To satisfy Eq. (29) exactly under
        temperature-dependent molar-volume dynamics, the caller must also
        account for the temperature closure term exposed as
        ``plate_eq29_temperature_closure``.
        """
        R_j = max(1.0e-8, float(R_plate))
        Vbar = max(1.0e-9, float(V_bar))
        v_i = np.asarray(pure_component_molar_volumes, dtype=np.float64).reshape(-1)
        x = np.asarray(x_j, dtype=np.float64).reshape(-1)
        x_minus = np.asarray(x_j_minus_1, dtype=np.float64).reshape(-1)
        y = np.asarray(y_j, dtype=np.float64).reshape(-1)
        y_plus = np.asarray(y_j_plus_1, dtype=np.float64).reshape(-1)

        prefactor = Vbar / R_j
        F_j = -prefactor * float(np.dot(v_i, y_plus - x))
        G_j = -prefactor * float(np.dot(v_i, x_minus - x))
        K_j = -prefactor * float(np.dot(v_i, y - x))
        return float(F_j), float(G_j), float(K_j)

    @staticmethod
    def compute_eq30_coefficients(
        *,
        R_plate: float,
        V_bar: float,
        pure_component_molar_volumes: NDArray[np.float64],
        x_j: NDArray[np.float64],
        x_j_minus_1: NDArray[np.float64],
        y_j: NDArray[np.float64],
        y_j_plus_1: NDArray[np.float64],
    ) -> tuple[float, float, float]:
        """Compatibility alias returning deterministic Eq. (28)->Eq. (29) coefficients."""
        return Howard1970DistillationColumn.compute_eq29_coefficients_from_eq28(
            R_plate=R_plate,
            V_bar=V_bar,
            pure_component_molar_volumes=pure_component_molar_volumes,
            x_j=x_j,
            x_j_minus_1=x_j_minus_1,
            y_j=y_j,
            y_j_plus_1=y_j_plus_1,
        )

    @staticmethod
    def compute_molar_volume_time_derivative(
        *,
        pure_component_molar_volumes: NDArray[np.float64],
        composition_time_derivative: NDArray[np.float64],
        molar_volume_temperature_coefficients: NDArray[np.float64] | None = None,
        composition: NDArray[np.float64] | None = None,
        temperature_time_derivative: float = 0.0,
    ) -> float:
        vi = np.asarray(pure_component_molar_volumes, dtype=np.float64).reshape(-1)
        dxdt = np.asarray(composition_time_derivative, dtype=np.float64).reshape(-1)
        dvdt = float(np.dot(vi, dxdt))
        if molar_volume_temperature_coefficients is not None and composition is not None:
            dvdT_mix = float(
                np.dot(
                    np.asarray(composition, dtype=np.float64).reshape(-1),
                    np.asarray(molar_volume_temperature_coefficients, dtype=np.float64).reshape(-1),
                )
            )
            dvdt += dvdT_mix * float(temperature_time_derivative)
        return float(dvdt)

    @staticmethod
    def compute_temperature_dependent_molar_volumes(
        *,
        reference_molar_volumes: NDArray[np.float64],
        temperature_coefficients: NDArray[np.float64],
        temperature_K: float,
        reference_temperature_K: float = _REFERENCE_TEMPERATURE_K,
    ) -> NDArray[np.float64]:
        return np.asarray(reference_molar_volumes, dtype=np.float64).reshape(-1) + np.asarray(
            temperature_coefficients, dtype=np.float64
        ).reshape(-1) * (float(temperature_K) - float(reference_temperature_K))

    @staticmethod
    def compute_liquid_flow_from_eq28(
        *,
        V_above: float,
        V_plate: float,
        L_below: float,
        V_bar: float,
        dvdt: float,
        feed_flow: float = 0.0,
    ) -> float:
        return (
            float(V_above)
            + float(L_below)
            + float(feed_flow)
            - float(V_plate)
            + float(V_bar) * float(dvdt)
        )

    @staticmethod
    def compute_eq28_derivative_balance_residual(
        *,
        V_above: float,
        V_plate: float,
        L_below: float,
        L_plate: float,
        V_bar: float,
        dvdt: float,
        feed_flow: float = 0.0,
    ) -> float:
        return (
            float(V_above)
            + float(L_below)
            + float(feed_flow)
            - float(V_plate)
            - float(L_plate)
            + float(V_bar) * float(dvdt)
        )

    @staticmethod
    def compute_liquid_enthalpy(
        x_values: NDArray[np.float64],
        ideal_component_enthalpies: NDArray[np.float64],
        phi_m: float,
    ) -> float:
        return float(
            np.dot(
                np.asarray(x_values, dtype=np.float64),
                np.asarray(ideal_component_enthalpies, dtype=np.float64),
            )
            + float(phi_m)
        )

    @staticmethod
    def compute_energy_balance_residual(
        *,
        V_above: float,
        H_above: float,
        h_plate: float,
        A_j: float,
        L_below: float,
        h_below: float,
        B_j: float,
        V_plate: float,
        H_plate: float,
        C_j: float,
        Q_Lj: float,
    ) -> float:
        return (
            float(V_above) * ((float(H_above) - float(h_plate)) - float(A_j))
            + float(L_below) * ((float(h_below) - float(h_plate)) - float(B_j))
            - float(V_plate) * ((float(H_plate) - float(h_plate)) - float(C_j))
            - float(Q_Lj)
        )

    @staticmethod
    def bubble_point_residual(
        K_values: NDArray[np.float64],
        x_values: NDArray[np.float64],
    ) -> float:
        return float(
            np.dot(np.asarray(K_values, dtype=np.float64), np.asarray(x_values, dtype=np.float64))
            - 1.0
        )

    @staticmethod
    def compute_bubble_point_temperature_derivative(
        *,
        K_values: NDArray[np.float64],
        dK_dT: NDArray[np.float64],
        x_independent: NDArray[np.float64],
        component_index: int,
        reference_component_index: int,
    ) -> float:
        K = np.asarray(K_values, dtype=np.float64).reshape(-1)
        dK = np.asarray(dK_dT, dtype=np.float64).reshape(-1)
        x_ind = np.asarray(x_independent, dtype=np.float64).reshape(-1)
        i = int(component_index)
        c = int(reference_component_index)

        dZ_dx = float(K[i] - K[c])

        independent_indices = [index for index in range(K.size) if index != c]
        dZ_dT = float(dK[c])
        for independent_position, component in enumerate(independent_indices):
            dZ_dT += float((dK[component] - dK[c]) * x_ind[independent_position])

        return -(dZ_dx / dZ_dT)

    @staticmethod
    def calculate_feed_plate_balance_rhs(
        *,
        plate_index: int,
        component_index: int,
        x_plate: NDArray[np.float64],
        y_plate: NDArray[np.float64],
        x_above: NDArray[np.float64],
        y_below: NDArray[np.float64],
        x_feed: NDArray[np.float64],
        V_above: float,
        V_plate: float,
        L_below: float,
        F_feed: float,
        R_plate: float,
    ) -> float:
        del plate_index
        i = int(component_index)
        return (
            float(V_above) * (float(y_below[i]) - float(x_plate[i]))
            + float(L_below) * (float(x_above[i]) - float(x_plate[i]))
            + float(F_feed) * (float(x_feed[i]) - float(x_plate[i]))
            - float(V_plate) * (float(y_plate[i]) - float(x_plate[i]))
        ) / float(R_plate)

    @staticmethod
    def calculate_feed_plate_holdup_rate(
        *,
        V_above: float,
        V_plate: float,
        L_below: float,
        L_plate: float,
        F_feed: float,
    ) -> float:
        return float(V_above) + float(L_below) + float(F_feed) - float(V_plate) - float(L_plate)

    @staticmethod
    def compute_molar_volume(
        x_values: NDArray[np.float64],
        pure_component_molar_volumes: NDArray[np.float64],
    ) -> float:
        return float(
            np.dot(
                np.asarray(x_values, dtype=np.float64),
                np.asarray(pure_component_molar_volumes, dtype=np.float64),
            )
        )

    @staticmethod
    def compute_holdup_from_volume(
        V_bar: float,
        v_mix: float,
    ) -> float:
        return float(V_bar) * float(v_mix)

    @staticmethod
    def compute_liquid_flow_constraint(
        *,
        V_above: float,
        V_plate: float,
        L_below: float,
        F_j: float,
        G_j: float,
        K_j: float,
    ) -> float:
        return (
            float(V_above) * (1.0 - float(F_j))
            + float(L_below) * (1.0 - float(G_j))
            - float(V_plate) * (1.0 - float(K_j))
        )

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
        feed_plate_index = int(round(float(k[k_map["feed_plate_index"]])))
        feed_plate_index = int(np.clip(feed_plate_index, 0, n_plates - 1))

        plate_holdup = np.asarray(y[y_map["plate_component_holdup"]], dtype=np.float64).reshape(
            n_plates, n_species
        )
        drum_moles = np.asarray(y[y_map["reflux_drum_component_moles"]], dtype=np.float64).reshape(
            -1
        )
        plate_temperature = np.asarray(y[y_map["plate_temperature_K"]], dtype=np.float64).reshape(
            -1
        )

        feed_flow = max(0.0, float(u[u_map["feed_1_flow"]]))
        feed_temperature = float(u[u_map["feed_1_temperature"]])
        feed_composition = _safe_normalize(
            np.asarray(u[u_map["feed_1_composition"]], dtype=np.float64).reshape(-1),
            n_species=n_species,
        )
        reflux_return_flow = max(0.0, float(u[u_map["reflux_return_flow"]]))
        reflux_return_composition = _safe_normalize(
            np.asarray(u[u_map["reflux_return_composition"]], dtype=np.float64).reshape(-1),
            n_species=n_species,
        )
        distillate_request = max(0.0, float(u[u_map["distillate_withdrawal_flow"]]))
        bottoms_request = max(0.0, float(u[u_map["bottoms_withdrawal_flow"]]))

        reference_molar_volumes = np.asarray(
            k[k_map["reference_molar_volumes_m3_per_mol"]], dtype=np.float64
        ).reshape(-1)
        molar_volume_temperature_coefficients = np.asarray(
            k[k_map["component_molar_volume_temperature_coefficient_m3_per_mol_K"]],
            dtype=np.float64,
        ).reshape(-1)
        K_reference = np.asarray(k[k_map["equilibrium_reference_K"]], dtype=np.float64).reshape(-1)
        dK_dT = np.asarray(
            k[k_map["equilibrium_temperature_sensitivity_per_K"]],
            dtype=np.float64,
        ).reshape(-1)
        pressure_exponent = np.asarray(
            k[k_map["equilibrium_pressure_exponent"]],
            dtype=np.float64,
        ).reshape(-1)
        reference_pressure_pa = max(1.0e-3, float(k[k_map["equilibrium_reference_pressure_pa"]]))
        plate_pressure_drop = float(k[k_map["plate_pressure_drop_pa"]])
        cp = np.asarray(k[k_map["component_heat_capacity_j_per_mol_K"]], dtype=np.float64).reshape(
            -1
        )
        efficiency_reference = np.asarray(
            k[k_map["vaporization_efficiency_reference"]], dtype=np.float64
        ).reshape(-1)
        V_bar = max(1.0e-9, float(k[k_map["plate_reference_volume_m3"]]))
        nominal_vapor = max(0.0, float(k[k_map["nominal_vapor_flow_mol_s"]]))
        nominal_liquid = max(0.0, float(k[k_map["nominal_liquid_flow_mol_s"]]))
        vapor_enthalpy_offset = float(k[k_map["vapor_enthalpy_offset_j_per_mol"]])
        energy_A_terms = np.asarray(
            k[k_map["energy_balance_A_term_j_per_mol"]], dtype=np.float64
        ).reshape(-1)
        energy_B_terms = np.asarray(
            k[k_map["energy_balance_B_term_j_per_mol"]], dtype=np.float64
        ).reshape(-1)
        energy_C_terms = np.asarray(
            k[k_map["energy_balance_C_term_j_per_mol"]], dtype=np.float64
        ).reshape(-1)
        plate_heat_loss = np.asarray(k[k_map["plate_heat_loss_j_per_s"]], dtype=np.float64).reshape(
            -1
        )
        feed_energy_D_terms = np.asarray(
            k[k_map["feed_energy_closure_D_term_j_per_mol"]], dtype=np.float64
        ).reshape(-1)

        distillate_x = _normalize_composition(drum_moles, n_species=n_species)
        x_plate = np.vstack(
            [_safe_normalize(plate_holdup[j], n_species=n_species) for j in range(n_plates)]
        )

        plate_K = np.zeros((n_plates, n_species), dtype=np.float64)
        plate_y_star = np.zeros((n_plates, n_species), dtype=np.float64)
        plate_efficiency = np.zeros((n_plates, n_species), dtype=np.float64)
        plate_y = np.zeros((n_plates, n_species), dtype=np.float64)
        bubble_residual = np.zeros(n_plates, dtype=np.float64)
        plate_holdup_target = np.zeros(n_plates, dtype=np.float64)
        plate_liquid_enthalpy = np.zeros(n_plates, dtype=np.float64)
        plate_vapor_enthalpy = np.zeros(n_plates, dtype=np.float64)
        plate_pressure = np.zeros(n_plates, dtype=np.float64)
        energy_balance_residual = np.zeros(n_plates, dtype=np.float64)

        top_pressure = max(1.0e4, float(y[y_map["column_pressure_pa"]]))
        for j in range(n_plates):
            plate_pressure[j] = max(1.0e4, top_pressure + float(j) * plate_pressure_drop)

        for j in range(n_plates):
            K_j = Howard1970DistillationColumn.compute_k_values(
                reference_K=K_reference,
                dK_dT=dK_dT,
                pressure_exponent=pressure_exponent,
                temperature_K=float(plate_temperature[j]),
                pressure_pa=float(plate_pressure[j]),
                reference_pressure_pa=reference_pressure_pa,
            )
            x_j = x_plate[j]
            y_star = K_j * x_j
            murphree_reference = np.clip(
                efficiency_reference
                + 0.10
                * np.tanh(0.25 * Howard1970DistillationColumn.bubble_point_residual(K_j, x_j)),
                0.55,
                0.99,
            )
            y_j_minus_1 = distillate_x if j == 0 else plate_y[j - 1]
            y_raw = np.clip(y_j_minus_1 + murphree_reference * (y_star - y_j_minus_1), 0.0, None)
            y_j = _safe_normalize(y_raw, n_species=n_species)
            efficiency = Howard1970DistillationColumn.compute_vaporization_efficiency(
                y_j,
                np.clip(y_star, _MIN_SUM, None),
            )

            v_i_at_temperature = (
                Howard1970DistillationColumn.compute_temperature_dependent_molar_volumes(
                    reference_molar_volumes=reference_molar_volumes,
                    temperature_coefficients=molar_volume_temperature_coefficients,
                    temperature_K=float(plate_temperature[j]),
                )
            )
            v_mix = Howard1970DistillationColumn.compute_molar_volume(x_j, v_i_at_temperature)
            holdup_target = Howard1970DistillationColumn.compute_holdup_from_volume(V_bar, v_mix)
            bubble = Howard1970DistillationColumn.bubble_point_residual(K_j, x_j)
            phi_m = 120.0 * (1.0 - float(np.dot(x_j, x_j)))
            ideal_enthalpy = cp * (plate_temperature[j] - _REFERENCE_TEMPERATURE_K)
            h_liq = Howard1970DistillationColumn.compute_liquid_enthalpy(x_j, ideal_enthalpy, phi_m)

            plate_K[j] = K_j
            plate_y_star[j] = y_star
            plate_efficiency[j] = efficiency
            plate_y[j] = y_j
            bubble_residual[j] = bubble
            plate_holdup_target[j] = max(1.0e-6, holdup_target)
            plate_liquid_enthalpy[j] = h_liq
            plate_vapor_enthalpy[j] = h_liq + vapor_enthalpy_offset

        feed_enthalpy = Howard1970DistillationColumn.compute_liquid_enthalpy(
            feed_composition,
            cp * (feed_temperature - _REFERENCE_TEMPERATURE_K),
            120.0 * (1.0 - float(np.dot(feed_composition, feed_composition))),
        )

        vapor_flow = np.clip(
            nominal_vapor * (1.0 + 0.15 * bubble_residual),
            0.2 * nominal_vapor,
            2.0 * nominal_vapor + 0.25 * feed_flow,
        )
        plate_F = np.zeros(n_plates, dtype=np.float64)
        plate_G = np.zeros(n_plates, dtype=np.float64)
        plate_Kcoef = np.zeros(n_plates, dtype=np.float64)
        liquid_flow = np.zeros(n_plates, dtype=np.float64)
        molar_volume_time_derivative = np.zeros(n_plates, dtype=np.float64)
        eq29_temperature_closure = np.zeros(n_plates, dtype=np.float64)
        reflux_to_column = _realized_withdrawal_flow(
            requested_flow=nominal_liquid + reflux_return_flow,
            owner_moles=drum_moles,
        )
        for j in range(n_plates):
            V_above = vapor_flow[j + 1] if j < (n_plates - 1) else vapor_flow[j]
            V_plate = vapor_flow[j]
            L_below = reflux_to_column if j == 0 else liquid_flow[j - 1]
            x_above = x_plate[j - 1] if j > 0 else distillate_x
            y_below = plate_y[j + 1] if j < (n_plates - 1) else plate_y[j]
            R_j_actual = max(1.0e-8, float(np.sum(plate_holdup[j])))
            R_j_target = max(1.0e-6, float(plate_holdup_target[j]))

            # Compute component balance fluxes (numerator), then derive
            # composition rates using actual holdup (for dv/dt composition
            # term) and target holdup (for the temperature-derivative path).
            component_flux = np.zeros(n_species, dtype=np.float64)
            for i in range(n_species):
                component_flux[i] = (
                    float(V_above) * (float(y_below[i]) - float(x_plate[j, i]))
                    + float(L_below) * (float(x_above[i]) - float(x_plate[j, i]))
                    - float(V_plate) * (float(plate_y[j, i]) - float(x_plate[j, i]))
                )
                if j == feed_plate_index:
                    component_flux[i] += float(feed_flow) * (
                        float(feed_composition[i]) - float(x_plate[j, i])
                    )

            # Composition rate for the dv/dt composition term (actual holdup).
            x_rate = component_flux / R_j_actual
            # Composition rate for the temperature-derivative path (target holdup,
            # matching the differential_rhs which uses holdup_target).
            x_rate_target = component_flux / R_j_target

            # --- Compute dT_j/dt using the full frozen GE-H70-6 temperature path ---
            # This mirrors the differential_rhs temperature-derivative block exactly:
            #   dT/dt = thermal_drive + bubble_drive + feed_energy_drive - 6*bubble_residual
            # All R_j references in this block use target holdup for RHS consistency.
            H_above_eb = (
                float(plate_vapor_enthalpy[j + 1])
                if j < (n_plates - 1)
                else float(plate_vapor_enthalpy[j])
            )
            h_below_eb = (
                float(plate_liquid_enthalpy[j - 1]) if j > 0 else float(plate_liquid_enthalpy[j])
            )
            feed_heat_term = 0.0
            if j == feed_plate_index and feed_flow > 0.0:
                feed_heat_term = feed_flow * (
                    (feed_enthalpy - float(plate_liquid_enthalpy[j]))
                    - float(feed_energy_D_terms[j])
                )
            q_lj = float(plate_heat_loss[j]) - feed_heat_term
            energy_balance_residual[j] = (
                Howard1970DistillationColumn.compute_energy_balance_residual(
                    V_above=float(V_above),
                    H_above=H_above_eb,
                    h_plate=float(plate_liquid_enthalpy[j]),
                    A_j=float(energy_A_terms[j]),
                    L_below=float(L_below),
                    h_below=h_below_eb,
                    B_j=float(energy_B_terms[j]),
                    V_plate=float(V_plate),
                    H_plate=float(plate_vapor_enthalpy[j]),
                    C_j=float(energy_C_terms[j]),
                    Q_Lj=q_lj,
                )
            )
            cp_mix = max(1.0, float(np.dot(x_plate[j], cp)))
            thermal_drive = float(energy_balance_residual[j]) / (R_j_target * cp_mix)

            # Bubble-drive: composition-induced temperature drift via GE-H70-6.
            # Uses x_rate_target (target holdup) which matches the RHS's dxdt_i.
            # Guard: skip when dK/dT is zero (no temperature sensitivity).
            bubble_drive = 0.0
            if n_species > 1 and np.any(dK_dT != 0.0):
                independent_indices = list(range(n_species - 1))
                independent_x = (
                    x_plate[j][independent_indices]
                    if n_species > 1
                    else np.array([1.0], dtype=np.float64)
                )
                for i in independent_indices:
                    dT_dxi = (
                        Howard1970DistillationColumn.compute_bubble_point_temperature_derivative(
                            K_values=plate_K[j],
                            dK_dT=dK_dT,
                            x_independent=independent_x,
                            component_index=i,
                            reference_component_index=n_species - 1,
                        )
                    )
                    bubble_drive += dT_dxi * float(x_rate_target[i])

            feed_energy_drive = (
                0.02
                * feed_flow
                * (feed_temperature - float(plate_temperature[j]))
                / max(R_j_target, 1.0)
                if j == feed_plate_index
                else 0.0
            )
            dTdt_estimate = (
                thermal_drive + bubble_drive + feed_energy_drive - 6.0 * float(bubble_residual[j])
            )

            v_i_at_T = Howard1970DistillationColumn.compute_temperature_dependent_molar_volumes(
                reference_molar_volumes=reference_molar_volumes,
                temperature_coefficients=molar_volume_temperature_coefficients,
                temperature_K=float(plate_temperature[j]),
            )
            dvdt = Howard1970DistillationColumn.compute_molar_volume_time_derivative(
                pure_component_molar_volumes=v_i_at_T,
                composition_time_derivative=x_rate,
                molar_volume_temperature_coefficients=molar_volume_temperature_coefficients,
                composition=x_plate[j],
                temperature_time_derivative=dTdt_estimate,
            )
            molar_volume_time_derivative[j] = dvdt

            L_target = Howard1970DistillationColumn.compute_liquid_flow_from_eq28(
                V_above=float(V_above),
                V_plate=float(V_plate),
                L_below=float(L_below),
                V_bar=float(V_bar),
                dvdt=float(dvdt),
                feed_flow=float(feed_flow if j == feed_plate_index else 0.0),
            )
            F_j, G_j, K_j_coeff = Howard1970DistillationColumn.compute_eq29_coefficients_from_eq28(
                R_plate=R_j_actual,
                V_bar=float(V_bar),
                pure_component_molar_volumes=Howard1970DistillationColumn.compute_temperature_dependent_molar_volumes(
                    reference_molar_volumes=reference_molar_volumes,
                    temperature_coefficients=molar_volume_temperature_coefficients,
                    temperature_K=float(plate_temperature[j]),
                ),
                x_j=x_plate[j],
                x_j_minus_1=x_above,
                y_j=plate_y[j],
                y_j_plus_1=y_below,
            )

            # Fold temperature-dependent molar-volume closure into the K_j
            # coefficient so that the Eq. (29) constraint expression closes
            # exactly under temperature-dependent molar-volume dynamics.
            #
            # The composition-only F/G/K capture V_bar * dv/dt_comp.  The
            # temperature contribution V_bar * dv/dt_temp must be folded into
            # K_j (associated with V_plate) so that:
            #   L_j = V_above*(1-F) + L_below*(1-G) - V_plate*(1-K_eff)
            # holds exactly for non-feed plates.  For feed plates the same
            # correction preserves the expected feed-flow gap.
            dvdT_mix = float(np.dot(x_plate[j], molar_volume_temperature_coefficients))
            dvdt_temp = dvdT_mix * dTdt_estimate
            temp_closure = float(V_bar) * dvdt_temp
            V_plate_safe = max(1.0e-9, float(V_plate))
            K_j_coeff = K_j_coeff + temp_closure / V_plate_safe
            eq29_temperature_closure[j] = temp_closure

            plate_F[j] = F_j
            plate_G[j] = G_j
            plate_Kcoef[j] = K_j_coeff
            liquid_flow[j] = max(0.0, float(L_target))

        flow_closure_residual = np.zeros(n_plates, dtype=np.float64)
        for j in range(n_plates):
            V_above = vapor_flow[j + 1] if j < (n_plates - 1) else vapor_flow[j]
            V_plate = vapor_flow[j]
            L_below = reflux_to_column if j == 0 else liquid_flow[j - 1]
            residual = Howard1970DistillationColumn.compute_eq28_derivative_balance_residual(
                V_above=float(V_above),
                V_plate=float(V_plate),
                L_below=float(L_below),
                L_plate=float(liquid_flow[j]),
                V_bar=float(V_bar),
                dvdt=float(molar_volume_time_derivative[j]),
                feed_flow=float(feed_flow if j == feed_plate_index else 0.0),
            )
            flow_closure_residual[j] = residual

        bottoms_x = x_plate[-1]
        distillate_flow = _realized_withdrawal_flow(
            requested_flow=distillate_request,
            owner_moles=drum_moles,
        )
        bottoms_flow = _realized_withdrawal_flow(
            requested_flow=bottoms_request,
            owner_moles=plate_holdup[-1],
        )

        algebraic = np.zeros(algebraic_size, dtype=np.float64)
        algebraic[algebraic_map["distillate_flow"]] = distillate_flow
        algebraic[algebraic_map["bottoms_flow"]] = bottoms_flow
        algebraic[algebraic_map["distillate_temperature"]] = float(plate_temperature[0])
        algebraic[algebraic_map["bottoms_temperature"]] = float(plate_temperature[-1])
        algebraic[algebraic_map["distillate_composition"]] = distillate_x
        algebraic[algebraic_map["bottoms_composition"]] = bottoms_x
        algebraic[algebraic_map["plate_liquid_composition"]] = x_plate.reshape(-1)
        algebraic[algebraic_map["plate_vapor_composition"]] = plate_y.reshape(-1)
        algebraic[algebraic_map["plate_K_values"]] = plate_K.reshape(-1)
        algebraic[algebraic_map["plate_vaporization_efficiency"]] = plate_efficiency.reshape(-1)
        algebraic[algebraic_map["plate_vapor_flow_mol_s"]] = vapor_flow
        algebraic[algebraic_map["plate_liquid_flow_mol_s"]] = liquid_flow
        algebraic[algebraic_map["plate_liquid_enthalpy_j_per_mol"]] = plate_liquid_enthalpy
        algebraic[algebraic_map["plate_vapor_enthalpy_j_per_mol"]] = plate_vapor_enthalpy
        algebraic[algebraic_map["plate_bubble_point_residual"]] = bubble_residual
        algebraic[algebraic_map["plate_holdup_target_mol"]] = plate_holdup_target
        algebraic[algebraic_map["plate_flow_closure_residual"]] = flow_closure_residual
        algebraic[algebraic_map["plate_molar_volume_time_derivative_m3_per_mol_s"]] = (
            molar_volume_time_derivative
        )
        algebraic[algebraic_map["plate_F_coefficient"]] = plate_F
        algebraic[algebraic_map["plate_G_coefficient"]] = plate_G
        algebraic[algebraic_map["plate_K_coefficient"]] = plate_Kcoef
        algebraic[algebraic_map["plate_eq29_temperature_closure"]] = eq29_temperature_closure
        algebraic[algebraic_map["plate_pressure_pa"]] = plate_pressure
        algebraic[algebraic_map["plate_energy_balance_residual_j_per_s"]] = energy_balance_residual
        algebraic[algebraic_map["reflux_to_column_flow_mol_s"]] = reflux_to_column

        del feed_temperature, feed_composition, reflux_return_composition
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
        feed_plate_index = int(round(float(k[k_map["feed_plate_index"]])))
        feed_plate_index = int(np.clip(feed_plate_index, 0, n_plates - 1))

        plate_holdup = np.asarray(y[y_map["plate_component_holdup"]], dtype=np.float64).reshape(
            n_plates, n_species
        )
        drum_moles = np.asarray(y[y_map["reflux_drum_component_moles"]], dtype=np.float64).reshape(
            -1
        )
        pressure = float(y[y_map["column_pressure_pa"]])
        plate_temperature = np.asarray(y[y_map["plate_temperature_K"]], dtype=np.float64).reshape(
            -1
        )

        x_plate = np.asarray(
            algebraic[algebraic_map["plate_liquid_composition"]], dtype=np.float64
        ).reshape(n_plates, n_species)
        y_plate = np.asarray(
            algebraic[algebraic_map["plate_vapor_composition"]], dtype=np.float64
        ).reshape(n_plates, n_species)
        vapor_flow = np.asarray(
            algebraic[algebraic_map["plate_vapor_flow_mol_s"]], dtype=np.float64
        ).reshape(-1)
        liquid_flow = np.asarray(
            algebraic[algebraic_map["plate_liquid_flow_mol_s"]], dtype=np.float64
        ).reshape(-1)
        bubble_residual = np.asarray(
            algebraic[algebraic_map["plate_bubble_point_residual"]], dtype=np.float64
        ).reshape(-1)
        plate_k_values = np.asarray(
            algebraic[algebraic_map["plate_K_values"]], dtype=np.float64
        ).reshape(n_plates, n_species)
        plate_energy_residual = np.asarray(
            algebraic[algebraic_map["plate_energy_balance_residual_j_per_s"]], dtype=np.float64
        ).reshape(-1)
        holdup_target = np.asarray(
            algebraic[algebraic_map["plate_holdup_target_mol"]], dtype=np.float64
        ).reshape(-1)
        distillate_flow = max(0.0, float(algebraic[algebraic_map["distillate_flow"]]))
        bottoms_flow = max(0.0, float(algebraic[algebraic_map["bottoms_flow"]]))
        reflux_to_column = max(0.0, float(algebraic[algebraic_map["reflux_to_column_flow_mol_s"]]))

        feed_flow = max(0.0, float(u[u_map["feed_1_flow"]]))
        feed_temperature = float(u[u_map["feed_1_temperature"]])
        feed_pressure = float(u[u_map["feed_1_pressure"]])
        feed_composition = _safe_normalize(
            np.asarray(u[u_map["feed_1_composition"]], dtype=np.float64).reshape(-1),
            n_species=n_species,
        )
        reflux_return_flow = max(0.0, float(u[u_map["reflux_return_flow"]]))
        reflux_return_pressure = float(u[u_map["reflux_return_pressure"]])
        reflux_return_composition = _safe_normalize(
            np.asarray(u[u_map["reflux_return_composition"]], dtype=np.float64).reshape(-1),
            n_species=n_species,
        )

        dK_dT = np.asarray(
            k[k_map["equilibrium_temperature_sensitivity_per_K"]], dtype=np.float64
        ).reshape(-1)

        x_drum = _safe_normalize(drum_moles, n_species=n_species)

        d_plate = np.zeros_like(plate_holdup)
        for j in range(n_plates):
            if 0 < j < (n_plates - 1):
                V_above = float(vapor_flow[j + 1])
                V_j = float(vapor_flow[j])
                L_below = float(liquid_flow[j - 1])
                R_j = max(1.0e-8, float(holdup_target[j]))
                for i in range(n_species):
                    if j == feed_plate_index:
                        dxdt = Howard1970DistillationColumn.calculate_feed_plate_balance_rhs(
                            plate_index=j,
                            component_index=i,
                            x_plate=x_plate[j],
                            y_plate=y_plate[j],
                            x_above=x_plate[j - 1],
                            y_below=y_plate[j + 1],
                            x_feed=feed_composition,
                            V_above=V_above,
                            V_plate=V_j,
                            L_below=L_below,
                            F_feed=feed_flow,
                            R_plate=R_j,
                        )
                        dRdt = Howard1970DistillationColumn.calculate_feed_plate_holdup_rate(
                            V_above=V_above,
                            V_plate=V_j,
                            L_below=L_below,
                            L_plate=float(liquid_flow[j]),
                            F_feed=feed_flow,
                        )
                    else:
                        dxdt = Howard1970DistillationColumn.calculate_component_balance_rhs(
                            plate_index=j,
                            component_index=i,
                            x_plate=x_plate,
                            y_plate=y_plate,
                            V_above=V_above,
                            V_plate=V_j,
                            L_below=L_below,
                            R_plate=R_j,
                        )
                        dRdt = V_above + L_below - V_j - float(liquid_flow[j])
                    d_plate[j, i] = R_j * dxdt + x_plate[j, i] * dRdt
                continue

            if j == 0:
                liquid_in = reflux_to_column * x_drum
                vapor_in = float(vapor_flow[1]) * y_plate[1] if n_plates > 1 else 0.0
                liquid_out = float(liquid_flow[0]) * x_plate[0]
                vapor_out = float(vapor_flow[0]) * y_plate[0]
                d_plate[j] = liquid_in + vapor_in - liquid_out - vapor_out
                if feed_plate_index == 0:
                    d_plate[j] += feed_flow * feed_composition
            else:
                liquid_in = float(liquid_flow[j - 1]) * x_plate[j - 1]
                vapor_in = float(vapor_flow[j]) * y_plate[j]
                liquid_out = (float(liquid_flow[j]) + bottoms_flow) * x_plate[j]
                vapor_out = float(vapor_flow[j]) * y_plate[j]
                d_plate[j] = liquid_in + vapor_in - liquid_out - vapor_out
                if feed_plate_index == j:
                    d_plate[j] += feed_flow * feed_composition

        d_drum = (
            float(vapor_flow[0]) * y_plate[0]
            + reflux_return_flow * reflux_return_composition
            - reflux_to_column * x_drum
            - distillate_flow * x_drum
        )

        d_temperature = np.zeros(n_plates, dtype=np.float64)
        for j in range(n_plates):
            x_j = x_plate[j]
            R_j = max(1.0e-6, float(holdup_target[j]))
            cp_mix = max(
                1.0, float(np.dot(x_j, np.asarray(k[k_map["component_heat_capacity_j_per_mol_K"]])))
            )
            thermal_drive = float(plate_energy_residual[j]) / (R_j * cp_mix)

            independent_indices = list(range(n_species - 1))
            independent_x = (
                x_j[independent_indices] if n_species > 1 else np.array([1.0], dtype=np.float64)
            )
            bubble_drive = 0.0
            if n_species > 1:
                for i in independent_indices:
                    dT_dxi = (
                        Howard1970DistillationColumn.compute_bubble_point_temperature_derivative(
                            K_values=plate_k_values[j],
                            dK_dT=dK_dT,
                            x_independent=independent_x,
                            component_index=i,
                            reference_component_index=n_species - 1,
                        )
                    )
                    total_holdup_rate = float(np.sum(d_plate[j]))
                    dxdt_i = (float(d_plate[j, i]) - float(x_j[i]) * total_holdup_rate) / R_j
                    bubble_drive += dT_dxi * dxdt_i

            feed_energy_drive = (
                0.02 * feed_flow * (feed_temperature - float(plate_temperature[j])) / max(R_j, 1.0)
                if j == feed_plate_index
                else 0.0
            )
            d_temperature[j] = (
                thermal_drive + bubble_drive + feed_energy_drive - 6.0 * float(bubble_residual[j])
            )

        pressure_tau = max(1.0, float(k[k_map["pressure_relaxation_time_s"]]))
        pressure_target = (
            feed_flow * feed_pressure + reflux_return_flow * reflux_return_pressure + 1.0 * pressure
        ) / max(1.0, feed_flow + reflux_return_flow + 1.0)
        d_pressure = (pressure_target - pressure) / pressure_tau

        dy = np.zeros_like(y)
        dy[y_map["plate_component_holdup"]] = d_plate.reshape(-1)
        dy[y_map["reflux_drum_component_moles"]] = d_drum
        dy[y_map["column_pressure_pa"]] = d_pressure
        dy[y_map["plate_temperature_K"]] = d_temperature
        return dy


__all__ = ["Howard1970DistillationColumn"]
