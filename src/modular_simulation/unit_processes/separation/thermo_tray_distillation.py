from __future__ import annotations

from functools import lru_cache
from math import isfinite
from typing import Annotated, ClassVar, cast, override

import numpy as np
from numpy.typing import NDArray

from modular_simulation.measurables.process_model import ProcessModel
from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import UnitProcessPorts
import modular_simulation.thermodynamics.distillation_closures as dc
import modular_simulation.thermodynamics.property_package as pp
from modular_simulation.thermodynamics.hydraulic_adapters import pipe_hydraulic_element_for_outlet
from modular_simulation.thermodynamics.hydraulic_participation import (
    HydraulicBalancingGroupSpec,
    HydraulicParticipationSpec,
    HydraulicPortSpec,
    HydraulicScalarStateRef,
)
from modular_simulation.thermodynamics.stream import PortAttributeMap, StreamData
from modular_simulation.utils.typing import ArrayIndex, Seconds

_MIN_SUM = 1.0e-12
_MIN_STEP_SECONDS = 1.0e-12
_G = 9.81
_R = 8.314462618


@lru_cache(maxsize=8)
def _pr_package_for_species_count(n_species: int):
    return _pr_package_for_species_selector(tuple(range(n_species)))


@lru_cache(maxsize=16)
def _pr_package_for_species_selector(selector: tuple[int, ...]):
    default_species = pp._DEFAULT_PR_SPECIES_CAS
    if len(selector) == 0:
        raise ValueError("species selector must not be empty.")
    species_cas = []
    for raw_index in selector:
        index = int(raw_index)
        if index < 0 or index >= len(default_species):
            raise ValueError(
                f"species selector index {index} out of range for default PR species table."
            )
        species_cas.append(default_species[index])
    return pp.PengRobinsonPackage(species_ids=tuple(species_cas))


def _coerce_1d(
    value: NDArray[np.float64], *, expected_size: int, default: float, name: str
) -> NDArray[np.float64]:
    arr = np.asarray(value, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return np.full(expected_size, default, dtype=np.float64)
    if arr.size != expected_size:
        raise ValueError(f"{name} length mismatch: expected {expected_size}, got {arr.size}.")
    return arr


def _safe_owner_fraction(moles: NDArray[np.float64], *, n_species: int) -> NDArray[np.float64]:
    clipped = np.clip(np.asarray(moles, dtype=np.float64).reshape(-1), 0.0, None)
    if clipped.size != n_species:
        raise ValueError(f"mole vector length mismatch: expected {n_species}, got {clipped.size}.")
    total = float(np.sum(clipped))
    if total <= _MIN_SUM:
        return np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
    return clipped / total


def _safe_owner_fraction_zeros(
    moles: NDArray[np.float64], *, n_species: int
) -> NDArray[np.float64]:
    clipped = np.clip(np.asarray(moles, dtype=np.float64).reshape(-1), 0.0, None)
    if clipped.size != n_species:
        raise ValueError(f"mole vector length mismatch: expected {n_species}, got {clipped.size}.")
    total = float(np.sum(clipped))
    if total <= _MIN_SUM:
        return np.zeros(n_species, dtype=np.float64)
    return clipped / total


def _realized_withdrawal_flow(
    *, requested_flow: float, owner_moles: NDArray[np.float64], dt_s: float
) -> float:
    bounded_request = max(0.0, float(requested_flow))
    owner_total = float(
        np.sum(np.clip(np.asarray(owner_moles, dtype=np.float64).reshape(-1), 0.0, None))
    )
    if owner_total <= _MIN_SUM:
        return 0.0
    bounded_dt_s = max(float(dt_s), _MIN_STEP_SECONDS)
    return min(bounded_request, owner_total / bounded_dt_s)


def _pr_bubble_pressure_pa(
    package: pp.PengRobinsonPackage,
    *,
    temperature_k: float,
    composition: NDArray[np.float64],
    fallback_pressure_pa: float,
) -> float:
    z = tuple(float(v) for v in np.asarray(composition, dtype=np.float64).reshape(-1))
    try:
        state = package._flasher.flash(T=round(float(temperature_k), 2), VF=0.0, zs=list(z))
        p = float(state.P)
        if np.isfinite(p) and p > 0.0:
            return p
    except Exception:
        pass
    return max(1.0, float(fallback_pressure_pa))


def _liquid_volume_m3(
    *, total_moles: float, molecular_weight_kg_per_mol: float, liquid_density_kg_m3: float
) -> float:
    return (
        max(0.0, float(total_moles))
        * max(1.0e-9, float(molecular_weight_kg_per_mol))
        / max(1.0e-9, float(liquid_density_kg_m3))
    )


class ThermoTrayDistillationColumnTotalCondenser(ProcessModel):
    _OUTLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "distillate": PortAttributeMap(
            flow="distillate_flow",
            temperature="distillate_temperature",
            pressure="distillate_source_pressure_pa",
            composition="distillate_composition",
        ),
        "bottoms": PortAttributeMap(
            flow="bottoms_flow",
            temperature="bottoms_temperature",
            pressure="bottom_pressure_pa",
            composition="bottoms_composition",
        ),
    }

    tray_component_holdup: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="mol", description="flattened tray-by-species liquid holdup"),
    ] = np.zeros(0, dtype=np.float64)
    tray_temperature: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="K", description="equilibrium tray temperatures"),
    ] = np.zeros(0, dtype=np.float64)
    condenser_drum_component_moles: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="mol", description="condenser drum component holdup"),
    ] = np.zeros(0, dtype=np.float64)
    condenser_drum_temperature: Annotated[
        float,
        M(type=T.DIFFERENTIAL, unit="K", description="condenser drum liquid temperature"),
    ] = 340.0
    condenser_headspace_component_moles: Annotated[
        NDArray[np.float64],
        M(
            type=T.DIFFERENTIAL,
            unit="mol",
            description="condenser excess-headspace component inventory",
        ),
    ] = np.zeros(0, dtype=np.float64)
    condenser_headspace_temperature: Annotated[
        float,
        M(type=T.DIFFERENTIAL, unit="K", description="condenser excess-headspace temperature"),
    ] = 340.0
    reboiler_kettle_component_moles: Annotated[
        NDArray[np.float64],
        M(type=T.DIFFERENTIAL, unit="mol", description="reboiler kettle component holdup"),
    ] = np.zeros(0, dtype=np.float64)
    reboiler_kettle_temperature: Annotated[
        float,
        M(type=T.DIFFERENTIAL, unit="K", description="reboiler kettle equilibrium temperature"),
    ] = 360.0

    feed_flows: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="mol/s", description="feed molar flows by feed index"),
    ] = np.zeros(0, dtype=np.float64)
    feed_temperatures: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="K", description="feed temperatures by feed index"),
    ] = np.zeros(0, dtype=np.float64)
    feed_pressures: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="Pa", description="feed pressures by feed index"),
    ] = np.zeros(0, dtype=np.float64)
    feed_compositions: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="", description="flattened feed compositions [n_feeds, n_species]"),
    ] = np.zeros(0, dtype=np.float64)
    distillate_withdrawal_flow: Annotated[
        float,
        M(type=T.BOUNDARY, unit="mol/s", description="requested distillate withdrawal"),
    ] = 0.0
    reflux_withdrawal_flow: Annotated[
        float,
        M(type=T.BOUNDARY, unit="mol/s", description="requested reflux withdrawal (GE-TTD-END-2a)"),
    ] = 0.0
    bottoms_withdrawal_flow: Annotated[
        float,
        M(type=T.BOUNDARY, unit="mol/s", description="requested bottoms withdrawal"),
    ] = 0.0
    accepted_dt_s: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="s",
            description="accepted integration step duration for withdrawal realizability",
        ),
    ] = 0.1
    condenser_duty_request_W: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="W",
            description="requested condenser duty (negative removes heat)",
        ),
    ] = 0.0
    reboiler_duty_request_W: Annotated[
        float,
        M(type=T.BOUNDARY, unit="W", description="requested reboiler duty (positive adds heat)"),
    ] = 0.0
    blanket_gas_component_flow: Annotated[
        NDArray[np.float64],
        M(
            type=T.BOUNDARY,
            unit="mol/s",
            description="optional blanket-gas addition rate by species",
        ),
    ] = np.zeros(0, dtype=np.float64)
    headspace_vent_component_flow: Annotated[
        NDArray[np.float64],
        M(
            type=T.BOUNDARY,
            unit="mol/s",
            description="optional headspace vent withdrawal rate by species",
        ),
    ] = np.zeros(0, dtype=np.float64)

    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 3
    species_selector: Annotated[
        NDArray[np.float64],
        M(
            type=T.CONSTANT,
            unit="",
            description="0-based indices into the default PR species table for each column species",
        ),
    ] = np.zeros(0, dtype=np.float64)
    n_feeds: Annotated[int, M(type=T.CONSTANT, unit="", description="number of feed ports")] = 1
    n_trays: Annotated[int, M(type=T.CONSTANT, unit="", description="explicit tray count")] = 4
    feed_tray_indices: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="", description="1-based feed tray assignment indices"),
    ] = np.zeros(0, dtype=np.float64)
    p_top_pa: Annotated[
        float,
        M(type=T.CONSTANT, unit="Pa", description="top pressure for tray profile"),
    ] = 150000.0
    delta_p_tray_pa: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="Pa",
            description="legacy uniform tray pressure increment alias for the residual term",
        ),
    ] = 500.0
    tray_residual_pressure_drop_pa: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="Pa",
            description="named residual tray pressure-drop term (GE-TTD-MAT-3b)",
        ),
    ] = 500.0
    p_bottom_pa: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="Pa",
            description="bottoms/kettle pressure (p_top + n_trays * delta_p)",
        ),
    ] = 152000.0
    tray_active_area_m2: Annotated[
        float,
        M(type=T.CONSTANT, unit="m2", description="active tray area for hydraulic closure"),
    ] = 0.8
    tray_weir_height_m: Annotated[
        float,
        M(type=T.CONSTANT, unit="m", description="tray weir height"),
    ] = 0.004
    liquid_flow_coeff: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol/s", description="liquid flow closure coefficient"),
    ] = 50.0
    vapor_flow_coeff: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol/s", description="vapor flow closure coefficient"),
    ] = 2.0
    tray_dry_pressure_drop_pa: Annotated[
        float,
        M(type=T.CONSTANT, unit="Pa", description="dry tray pressure-drop term"),
    ] = 10.0
    kettle_min_holdup_mol: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol", description="minimum kettle holdup for boilup capacity"),
    ] = 1.0
    kettle_boilup_coeff: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="kettle boilup capacity coefficient"),
    ] = 0.2
    eps_sp: Annotated[float, M(type=T.CONSTANT, unit="", description="smooth-plus epsilon")] = (
        1.0e-8
    )
    eps_sm: Annotated[float, M(type=T.CONSTANT, unit="", description="smooth-min epsilon")] = 1.0e-8
    eps_n: Annotated[float, M(type=T.CONSTANT, unit="mol", description="holdup epsilon")] = 1.0e-8
    eps_c: Annotated[
        float,
        M(type=T.CONSTANT, unit="J/K", description="heat-capacity denominator epsilon"),
    ] = 1.0e3
    eps_v: Annotated[
        float,
        M(type=T.CONSTANT, unit="m3", description="headspace volume epsilon"),
    ] = 1.0e-6
    eps_start: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol", description="startup tray epsilon holdup"),
    ] = 1.0
    eps_drum: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol", description="startup condenser drum epsilon holdup"),
    ] = 5.0
    eps_kettle: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol", description="startup kettle epsilon holdup"),
    ] = 5.0
    eps_headspace: Annotated[
        float,
        M(type=T.CONSTANT, unit="mol", description="startup excess-headspace epsilon holdup"),
    ] = 0.1
    condenser_shell_volume_m3: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="m3",
            description="condenser shell volume assigned to drum plus headspace",
        ),
    ] = 1.0
    distillate_nozzle_submergence_m: Annotated[
        float,
        M(type=T.CONSTANT, unit="m", description="distillate nozzle hydrostatic submergence"),
    ] = 0.5
    reflux_nozzle_submergence_m: Annotated[
        float,
        M(type=T.CONSTANT, unit="m", description="reflux nozzle hydrostatic submergence"),
    ] = 0.5
    headspace_compressibility: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="headspace excess-gas compressibility factor"),
    ] = 1.0
    headspace_temperature_relaxation_1_s: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="1/s",
            description="first-order headspace temperature relaxation rate",
        ),
    ] = 0.5
    dry_guard_drum_threshold_mol: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="mol",
            description="drum inventory below which dT_D/dt is frozen (N^D_dry_guard, GE-TTD-END-3)",
        ),
    ] = 1.0e-4
    eps_settle: Annotated[
        float,
        M(type=T.CONSTANT, unit="1/s", description="settle metric threshold"),
    ] = 5.0e-2
    tau_settle_s: Annotated[
        float,
        M(type=T.CONSTANT, unit="s", description="contiguous settle hold horizon"),
    ] = 2.0
    temperature_reference_k: Annotated[
        float,
        M(type=T.CONSTANT, unit="K", description="reference temperature for simple thermo closure"),
    ] = 298.15
    pressure_reference_pa: Annotated[
        float,
        M(type=T.CONSTANT, unit="Pa", description="reference pressure for simple thermo closure"),
    ] = 101325.0
    k_temp_sensitivity_per_k: Annotated[
        float,
        M(type=T.CONSTANT, unit="1/K", description="temperature sensitivity for K closure"),
    ] = 0.003
    default_composition: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="", description="default startup composition"),
    ] = np.zeros(0, dtype=np.float64)
    cp_species_liq_j_per_mol_k: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/mol/K", description="species liquid heat capacities"),
    ] = np.zeros(0, dtype=np.float64)
    latent_species_j_per_mol: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="J/mol", description="species latent enthalpy surrogates"),
    ] = np.zeros(0, dtype=np.float64)
    volatility_reference: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="", description="species volatility reference vector"),
    ] = np.zeros(0, dtype=np.float64)

    tray_pressures_pa: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="Pa", description="tray pressure profile"),
    ] = np.zeros(0, dtype=np.float64)
    tray_liquid_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="flattened tray liquid composition"),
    ] = np.zeros(0, dtype=np.float64)
    tray_vapor_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="flattened tray vapor composition"),
    ] = np.zeros(0, dtype=np.float64)
    tray_liquid_flow: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="tray downflow rates"),
    ] = np.zeros(0, dtype=np.float64)
    tray_vapor_flow: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="mol/s", description="tray upflow rates"),
    ] = np.zeros(0, dtype=np.float64)
    tray_heat_input: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="W", description="ordinary tray heat input (zero in Wave 2)"),
    ] = np.zeros(0, dtype=np.float64)
    reboiler_latent_heat_j_per_mol: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="J/mol", description="dynamic kettle latent enthalpy difference"),
    ] = 30000.0
    distillate_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="distillate outlet flow"),
    ] = 0.0
    reflux_flow: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="mol/s",
            description="realized reflux withdrawal flow (GE-TTD-END-2)",
        ),
    ] = 0.0
    bottoms_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="bottoms outlet flow"),
    ] = 0.0
    distillate_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="distillate composition"),
    ] = np.zeros(0, dtype=np.float64)
    bottoms_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="bottoms composition"),
    ] = np.zeros(0, dtype=np.float64)
    distillate_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="distillate temperature"),
    ] = 298.15
    bottoms_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="bottoms temperature"),
    ] = 298.15
    realized_condensed_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="realized total-condenser condensation flow"),
    ] = 0.0
    non_condensed_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="non-condensed vapor carryover to headspace"),
    ] = 0.0
    headspace_pressure_pa: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="condenser vapor-headspace pressure"),
    ] = 150000.0
    distillate_source_pressure_pa: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="Pa",
            description="distillate liquid source pressure with hydrostatic head",
        ),
    ] = 150000.0
    reflux_source_pressure_pa: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="Pa",
            description="reflux liquid source pressure with hydrostatic head",
        ),
    ] = 150000.0
    bottom_pressure_pa: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="Pa",
            description="live bottom pressure from dynamic pressure-drop closure",
        ),
    ] = 152000.0

    _ports: UnitProcessPorts = UnitProcessPorts(("feed_1",), ("distillate", "bottoms"))

    @staticmethod
    def _collapsed_headspace_interface_recondensation_flow(
        *, realized_condensed_flow: float, non_condensed_flow: float, y_top: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        del realized_condensed_flow, non_condensed_flow
        return np.zeros_like(np.asarray(y_top, dtype=np.float64).reshape(-1))

    def __init__(self, **data: object) -> None:
        if "tray_residual_pressure_drop_pa" not in data and "delta_p_tray_pa" in data:
            data["tray_residual_pressure_drop_pa"] = data["delta_p_tray_pa"]
        elif "tray_residual_pressure_drop_pa" in data and "delta_p_tray_pa" not in data:
            data["delta_p_tray_pa"] = data["tray_residual_pressure_drop_pa"]
        elif (
            "tray_residual_pressure_drop_pa" in data
            and "delta_p_tray_pa" in data
            and float(cast(float, data["tray_residual_pressure_drop_pa"]))
            != float(cast(float, data["delta_p_tray_pa"]))
        ):
            raise ValueError(
                "tray_residual_pressure_drop_pa and delta_p_tray_pa must match when both are provided."
            )
        feed_tray_indices_data = data.pop("feed_tray_indices", None)
        n_trays = int(data.get("n_trays", 4))
        if feed_tray_indices_data is None:
            feed_tray_indices_data = (max(1, n_trays // 2),)
        feed_tray_indices_tuple = tuple(
            int(value) for value in cast(tuple[int, ...], feed_tray_indices_data)
        )
        if len(feed_tray_indices_tuple) == 0:
            raise ValueError("feed_tray_indices must contain at least one tray index.")
        data["n_feeds"] = len(feed_tray_indices_tuple)
        data["feed_tray_indices"] = np.asarray(feed_tray_indices_tuple, dtype=np.float64)
        super().__init__(**data)
        self._ports = UnitProcessPorts(
            tuple(f"feed_{index + 1}" for index in range(self.n_feeds)),
            ("distillate", "bottoms"),
        )

    @override
    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        if self.n_species <= 1:
            raise ValueError("n_species must be at least 2.")
        if self.n_trays <= 0:
            raise ValueError("n_trays must be positive.")
        if self.n_feeds <= 0:
            raise ValueError("n_feeds must be positive.")
        if not isfinite(self.p_top_pa) or self.p_top_pa <= 0.0:
            raise ValueError("p_top_pa must be finite and positive.")
        if not isfinite(self.delta_p_tray_pa) or self.delta_p_tray_pa < 0.0:
            raise ValueError("delta_p_tray_pa must be finite and non-negative.")
        if not isfinite(self.eps_c) or self.eps_c <= 0.0:
            raise ValueError("eps_c must be finite and positive.")

        self.delta_p_tray_pa = float(self.tray_residual_pressure_drop_pa)
        self.p_bottom_pa = float(self.p_top_pa + self.n_trays * self.tray_residual_pressure_drop_pa)

        if np.asarray(self.species_selector, dtype=np.float64).size == 0:
            self.species_selector = np.arange(self.n_species, dtype=np.float64)
        self.species_selector = _coerce_1d(
            self.species_selector,
            expected_size=self.n_species,
            default=0.0,
            name="species_selector",
        )
        selector_int = np.rint(self.species_selector).astype(np.int64)
        if not np.allclose(self.species_selector, selector_int, atol=0.0):
            raise ValueError("species_selector must contain integer indices.")
        if len(set(selector_int.tolist())) != self.n_species:
            raise ValueError("species_selector must contain unique indices.")
        max_species_index = len(pp._DEFAULT_PR_SPECIES_CAS) - 1
        if np.any(selector_int < 0) or np.any(selector_int > max_species_index):
            raise ValueError(f"species_selector values must be within [0, {max_species_index}].")
        self.species_selector = selector_int.astype(np.float64)
        package = _pr_package_for_species_selector(tuple(int(value) for value in selector_int))

        self.feed_tray_indices = _coerce_1d(
            self.feed_tray_indices,
            expected_size=self.n_feeds,
            default=float(max(1, self.n_trays // 2)),
            name="feed_tray_indices",
        )
        self.feed_tray_indices = np.clip(np.round(self.feed_tray_indices), 1.0, float(self.n_trays))

        self.feed_flows = _coerce_1d(
            self.feed_flows, expected_size=self.n_feeds, default=0.0, name="feed_flows"
        )
        self.feed_temperatures = _coerce_1d(
            self.feed_temperatures,
            expected_size=self.n_feeds,
            default=350.0,
            name="feed_temperatures",
        )
        self.feed_pressures = _coerce_1d(
            self.feed_pressures,
            expected_size=self.n_feeds,
            default=self.p_top_pa,
            name="feed_pressures",
        )
        self.feed_compositions = _coerce_1d(
            np.asarray(self.feed_compositions, dtype=np.float64).reshape(-1),
            expected_size=self.n_feeds * self.n_species,
            default=1.0 / float(self.n_species),
            name="feed_compositions",
        )
        self.blanket_gas_component_flow = _coerce_1d(
            np.asarray(self.blanket_gas_component_flow, dtype=np.float64).reshape(-1),
            expected_size=self.n_species,
            default=0.0,
            name="blanket_gas_component_flow",
        )
        self.headspace_vent_component_flow = _coerce_1d(
            np.asarray(self.headspace_vent_component_flow, dtype=np.float64).reshape(-1),
            expected_size=self.n_species,
            default=0.0,
            name="headspace_vent_component_flow",
        )
        feed_matrix = self.feed_compositions.reshape(self.n_feeds, self.n_species)
        for idx in range(self.n_feeds):
            feed_matrix[idx] = dc.normalized_composition(feed_matrix[idx], n_species=self.n_species)
        self.feed_compositions = feed_matrix.reshape(-1)

        if np.asarray(self.default_composition, dtype=np.float64).size == 0:
            self.default_composition = np.asarray(feed_matrix[0], dtype=np.float64)
        self.default_composition = dc.normalized_composition(
            self.default_composition, n_species=self.n_species
        )

        if np.asarray(self.cp_species_liq_j_per_mol_k, dtype=np.float64).size == 0:
            cps = []
            latents = []
            for i in range(self.n_species):
                z = np.zeros(self.n_species, dtype=np.float64)
                z[i] = 1.0
                zt = tuple(float(v) for v in z)
                try:
                    cp = package.heat_capacity_cp(350.0, self.p_top_pa, zt, "liquid")
                except Exception:
                    cp = 120.0 + 10.0 * i
                try:
                    hv = package.enthalpy(350.0, self.p_top_pa, zt, "vapor")
                    hl = package.enthalpy(350.0, self.p_top_pa, zt, "liquid")
                    latent = max(8000.0, hv - hl)
                except Exception:
                    latent = 24000.0 + 4000.0 * i
                cps.append(float(max(10.0, cp)))
                latents.append(float(max(5000.0, latent)))
            self.cp_species_liq_j_per_mol_k = np.asarray(cps, dtype=np.float64)
            self.latent_species_j_per_mol = np.asarray(latents, dtype=np.float64)

        self.cp_species_liq_j_per_mol_k = _coerce_1d(
            self.cp_species_liq_j_per_mol_k,
            expected_size=self.n_species,
            default=120.0,
            name="cp_species_liq_j_per_mol_k",
        )
        self.latent_species_j_per_mol = _coerce_1d(
            self.latent_species_j_per_mol,
            expected_size=self.n_species,
            default=28000.0,
            name="latent_species_j_per_mol",
        )

        if np.asarray(self.volatility_reference, dtype=np.float64).size == 0:
            self.volatility_reference = np.linspace(1.8, 0.7, self.n_species, dtype=np.float64)
            self.volatility_reference[-1] = 1.0
        self.volatility_reference = _coerce_1d(
            self.volatility_reference,
            expected_size=self.n_species,
            default=1.0,
            name="volatility_reference",
        )

        base_tray_mol = 10.0
        if np.asarray(self.tray_component_holdup, dtype=np.float64).size == 0:
            tray_default = np.zeros((self.n_trays, self.n_species), dtype=np.float64)
            species_bias = np.linspace(0.02, -0.02, self.n_species, dtype=np.float64)
            tray_span = max(1, self.n_trays - 1)
            for j in range(self.n_trays):
                tray_factor = 1.0 - (j / float(tray_span))
                z_j = dc.normalized_composition(
                    self.default_composition + tray_factor * species_bias,
                    n_species=self.n_species,
                )
                tray_default[j] = base_tray_mol * z_j
            self.tray_component_holdup = tray_default.reshape(-1)
        self.tray_component_holdup = _coerce_1d(
            self.tray_component_holdup,
            expected_size=self.n_trays * self.n_species,
            default=base_tray_mol / float(self.n_species),
            name="tray_component_holdup",
        )
        self.tray_temperature = _coerce_1d(
            self.tray_temperature,
            expected_size=self.n_trays,
            default=float(np.mean(self.feed_temperatures))
            if self.feed_temperatures.size
            else 350.0,
            name="tray_temperature",
        )
        if np.asarray(self.condenser_drum_component_moles, dtype=np.float64).size == 0:
            self.condenser_drum_component_moles = 5.0 * np.asarray(
                self.default_composition, dtype=np.float64
            )
        self.condenser_drum_component_moles = _coerce_1d(
            self.condenser_drum_component_moles,
            expected_size=self.n_species,
            default=5.0 / float(self.n_species),
            name="condenser_drum_component_moles",
        )
        if np.asarray(self.condenser_headspace_component_moles, dtype=np.float64).size == 0:
            self.condenser_headspace_component_moles = max(
                float(self.eps_headspace), self.eps_n
            ) * np.asarray(self.default_composition, dtype=np.float64)
        self.condenser_headspace_component_moles = _coerce_1d(
            self.condenser_headspace_component_moles,
            expected_size=self.n_species,
            default=max(float(self.eps_headspace), self.eps_n) / float(self.n_species),
            name="condenser_headspace_component_moles",
        )
        if np.asarray(self.reboiler_kettle_component_moles, dtype=np.float64).size == 0:
            self.reboiler_kettle_component_moles = 5.0 * np.asarray(
                self.default_composition, dtype=np.float64
            )
        self.reboiler_kettle_component_moles = _coerce_1d(
            self.reboiler_kettle_component_moles,
            expected_size=self.n_species,
            default=5.0 / float(self.n_species),
            name="reboiler_kettle_component_moles",
        )

        self.tray_pressures_pa = _coerce_1d(
            self.tray_pressures_pa,
            expected_size=self.n_trays,
            default=self.p_top_pa,
            name="tray_pressures_pa",
        )
        self.tray_liquid_composition = _coerce_1d(
            self.tray_liquid_composition,
            expected_size=self.n_trays * self.n_species,
            default=1.0 / float(self.n_species),
            name="tray_liquid_composition",
        )
        self.tray_vapor_composition = _coerce_1d(
            self.tray_vapor_composition,
            expected_size=self.n_trays * self.n_species,
            default=1.0 / float(self.n_species),
            name="tray_vapor_composition",
        )
        self.tray_liquid_flow = _coerce_1d(
            self.tray_liquid_flow,
            expected_size=self.n_trays,
            default=0.0,
            name="tray_liquid_flow",
        )
        self.tray_vapor_flow = _coerce_1d(
            self.tray_vapor_flow,
            expected_size=self.n_trays,
            default=0.0,
            name="tray_vapor_flow",
        )
        self.tray_heat_input = _coerce_1d(
            self.tray_heat_input,
            expected_size=self.n_trays,
            default=0.0,
            name="tray_heat_input",
        )
        self.distillate_composition = _coerce_1d(
            self.distillate_composition,
            expected_size=self.n_species,
            default=1.0 / float(self.n_species),
            name="distillate_composition",
        )
        self.bottoms_composition = _coerce_1d(
            self.bottoms_composition,
            expected_size=self.n_species,
            default=1.0 / float(self.n_species),
            name="bottoms_composition",
        )

        self._settle_hold_s = 0.0
        self._last_boundary_snapshot: NDArray[np.float64] | None = None

    @property
    def ports(self) -> UnitProcessPorts:
        return self._ports

    @property
    @override
    def hydraulic_participation(self) -> HydraulicParticipationSpec:
        ports: dict[str, HydraulicPortSpec] = {
            "distillate": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef(state="distillate_source_pressure_pa"),
            ),
            "bottoms": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef(state="bottom_pressure_pa"),
            ),
        }
        for feed_index in range(self.n_feeds):
            ports[f"feed_{feed_index + 1}"] = HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef(state="p_top_pa"),
            )
        return HydraulicParticipationSpec(
            ports=ports,
            balancing_groups=(
                HydraulicBalancingGroupSpec(
                    name="thermo_tray_distillation_flow_balance",
                    ports=(*self.ports.inlets, *self.ports.outlets),
                ),
            ),
            relations=(),
        )

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        if port_name not in self.ports.inlets:
            valid_ports = ", ".join(self.ports.inlets)
            raise ValueError(
                f"Invalid inlet port '{port_name}' for {type(self).__name__}. Valid inlet ports: {valid_ports}."
            )
        feed_index = int(port_name.split("_")[-1]) - 1
        self.feed_flows[feed_index] = max(0.0, float(stream.molar_flow_rate))
        self.feed_temperatures[feed_index] = float(stream.temperature)
        self.feed_pressures[feed_index] = max(1.0, float(stream.pressure))
        feed_matrix = np.asarray(self.feed_compositions, dtype=np.float64).reshape(
            self.n_feeds, self.n_species
        )
        feed_matrix[feed_index] = dc.normalized_composition(
            np.asarray(stream.mole_fractions, dtype=np.float64),
            n_species=self.n_species,
        )
        self.feed_compositions = feed_matrix.reshape(-1)
        if feed_index == 0:
            self.default_composition = np.asarray(feed_matrix[0], dtype=np.float64)
            if float(self.t) <= 0.0:
                drum_total = float(np.sum(np.clip(self.condenser_drum_component_moles, 0.0, None)))
                kettle_total = float(
                    np.sum(np.clip(self.reboiler_kettle_component_moles, 0.0, None))
                )
                z0 = dc.normalized_composition(feed_matrix[0], n_species=self.n_species)
                if drum_total > 0.0:
                    self.condenser_drum_component_moles = drum_total * z0
                if kettle_total > 0.0:
                    self.reboiler_kettle_component_moles = kettle_total * z0

    def get_outlet_stream(self, port_name: str) -> StreamData:
        if port_name not in self.ports.outlets:
            valid_ports = ", ".join(self.ports.outlets)
            raise ValueError(
                f"Invalid outlet port '{port_name}' for {type(self).__name__}. Valid outlet ports: {valid_ports}."
            )
        port_map = self._OUTLET_MAP[port_name]
        composition = tuple(
            float(value)
            for value in np.asarray(getattr(self, port_map.composition), dtype=np.float64).reshape(
                -1
            )
        )
        if port_name == "bottoms":
            pressure = float(self.bottom_pressure_pa)
        elif port_name == "distillate":
            pressure = float(self.distillate_source_pressure_pa)
        else:
            pressure = float(self.reflux_source_pressure_pa)
        return StreamData(
            temperature=float(getattr(self, port_map.temperature)),
            pressure=pressure,
            mole_fractions=composition,
            molar_flow_rate=float(getattr(self, port_map.flow)),
        )

    def to_hydraulic_element(self, port_name: str):
        return pipe_hydraulic_element_for_outlet(
            unit_name=type(self).__name__,
            port_name=port_name,
            allowed_outlet_ports=self.ports.outlets,
        )

    def apply_requested_outlet_through_flow_demand(
        self, port_name: str, through_molar_flow_rate: float
    ) -> None:
        if port_name not in self.ports.outlets:
            valid_ports = ", ".join(self.ports.outlets)
            raise ValueError(
                f"Invalid outlet port '{port_name}' for {type(self).__name__}. Valid outlet ports: {valid_ports}."
            )
        demand = max(0.0, float(through_molar_flow_rate))
        if port_name == "distillate":
            self.distillate_withdrawal_flow = demand
            return
        self.bottoms_withdrawal_flow = demand

    def build_startup_state(self) -> None:
        if self.n_feeds > 0 and float(np.sum(self.feed_flows)) > 0.0:
            feed_matrix = np.asarray(self.feed_compositions, dtype=np.float64).reshape(
                self.n_feeds, self.n_species
            )
            z0 = dc.normalized_composition(feed_matrix[0], n_species=self.n_species)
            t0 = float(self.feed_temperatures[0])
        else:
            z0 = dc.normalized_composition(self.default_composition, n_species=self.n_species)
            t0 = float(np.mean(self.feed_temperatures)) if self.feed_temperatures.size else 350.0

        tray = np.zeros((self.n_trays, self.n_species), dtype=np.float64)
        for j in range(self.n_trays):
            tray[j] = max(float(self.eps_start), self.eps_n) * z0
        self.tray_component_holdup = tray.reshape(-1)
        self.tray_temperature = np.full(self.n_trays, t0, dtype=np.float64)
        self.condenser_drum_component_moles = max(float(self.eps_drum), self.eps_n) * z0
        self.condenser_headspace_component_moles = max(float(self.eps_headspace), self.eps_n) * z0
        self.reboiler_kettle_component_moles = max(float(self.eps_kettle), self.eps_n) * z0
        self.condenser_drum_temperature = t0
        self.condenser_headspace_temperature = t0
        self.reboiler_kettle_temperature = t0
        self._settle_hold_s = 0.0
        self._last_boundary_snapshot = None

    def compute_settle_metric(self) -> float:
        if not hasattr(self, "_params"):
            return 0.0
        y = self.differential_view.to_array()
        u = self.boundary_view.to_array()
        algebraic = self.calculate_algebraic_values(
            y=y,
            u=u,
            k=self._params.k,
            y_map=self._params.y_map,
            u_map=self._params.boundary_map,
            k_map=self._params.k_map,
            algebraic_map=self._params.algebraic_map,
            algebraic_size=self._params.algebraic_size,
        )
        dy = self.differential_rhs(
            t=self.t,
            y=y,
            u=u,
            k=self._params.k,
            algebraic=algebraic,
            y_map=self._params.y_map,
            u_map=self._params.boundary_map,
            k_map=self._params.k_map,
            algebraic_map=self._params.algebraic_map,
        )
        n_trays = int(self.n_trays)
        n_species = int(self.n_species)

        d_tray = np.asarray(
            dy[self._params.y_map["tray_component_holdup"]], dtype=np.float64
        ).reshape(n_trays, n_species)
        tray_holdup = np.asarray(
            y[self._params.y_map["tray_component_holdup"]], dtype=np.float64
        ).reshape(n_trays, n_species)
        n_scale = np.maximum(np.sum(np.clip(tray_holdup, 0.0, None), axis=1), self.eps_n)
        mat_term = float(np.max(np.abs(d_tray) / n_scale[:, None]))

        d_t_tray = np.asarray(dy[self._params.y_map["tray_temperature"]], dtype=np.float64).reshape(
            -1
        )
        tray_t = np.asarray(y[self._params.y_map["tray_temperature"]], dtype=np.float64).reshape(-1)
        t_scale_tray = np.maximum(np.abs(tray_t), 300.0)
        tray_t_term = float(np.max(np.abs(d_t_tray) / t_scale_tray))

        d_t_drum = float(dy[self._params.y_map["condenser_drum_temperature"]])
        d_t_kettle = float(dy[self._params.y_map["reboiler_kettle_temperature"]])
        t_scale_drum = max(abs(float(y[self._params.y_map["condenser_drum_temperature"]])), 300.0)
        t_scale_kettle = max(
            abs(float(y[self._params.y_map["reboiler_kettle_temperature"]])), 300.0
        )
        drum_term = abs(d_t_drum) / t_scale_drum
        kettle_term = abs(d_t_kettle) / t_scale_kettle

        return max(0.0, mat_term, tray_t_term, drum_term, kettle_term)

    @override
    def step(self, dt: Seconds) -> None:
        dt_s = max(float(dt), _MIN_STEP_SECONDS)
        self.accepted_dt_s = dt_s
        boundary_now = self.boundary_view.to_array()
        super().step(dt_s)
        # GE-TTD-ST-4: reset settle hold when boundary conditions change
        if self._last_boundary_snapshot is not None:
            if not np.array_equal(boundary_now, self._last_boundary_snapshot):
                self._settle_hold_s = 0.0
        self._last_boundary_snapshot = boundary_now.copy()
        settle_now = self.compute_settle_metric()
        if settle_now <= float(self.eps_settle):
            self._settle_hold_s = float(self._settle_hold_s + dt_s)
        else:
            self._settle_hold_s = 0.0

    @property
    def settle_metric(self) -> float:
        return self.compute_settle_metric()

    @property
    def is_settled(self) -> bool:
        return bool(self._settle_hold_s >= float(self.tau_settle_s))

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
        n_species = int(round(float(k[k_map["n_species"]])))
        n_feeds = int(round(float(k[k_map["n_feeds"]])))
        n_trays = int(round(float(k[k_map["n_trays"]])))
        species_selector = tuple(
            int(round(float(value)))
            for value in np.asarray(k[k_map["species_selector"]], dtype=np.float64).reshape(-1)
        )
        package = _pr_package_for_species_selector(species_selector)

        tray_holdup = np.asarray(y[y_map["tray_component_holdup"]], dtype=np.float64).reshape(
            n_trays, n_species
        )
        tray_temperature = np.asarray(y[y_map["tray_temperature"]], dtype=np.float64).reshape(
            n_trays
        )
        drum_moles = np.asarray(
            y[y_map["condenser_drum_component_moles"]], dtype=np.float64
        ).reshape(-1)
        drum_temp = float(y[y_map["condenser_drum_temperature"]])
        headspace_moles = np.asarray(
            y[y_map["condenser_headspace_component_moles"]], dtype=np.float64
        ).reshape(-1)
        headspace_temp = float(y[y_map["condenser_headspace_temperature"]])
        kettle_moles = np.asarray(
            y[y_map["reboiler_kettle_component_moles"]], dtype=np.float64
        ).reshape(-1)

        p_top_anchor = float(k[k_map["p_top_pa"]])
        delta_p = float(k[k_map["tray_residual_pressure_drop_pa"]])
        area = max(1.0e-6, float(k[k_map["tray_active_area_m2"]]))
        weir_height = float(k[k_map["tray_weir_height_m"]])
        liquid_coeff = float(k[k_map["liquid_flow_coeff"]])
        vapor_coeff = float(k[k_map["vapor_flow_coeff"]])
        dry_dp = float(k[k_map["tray_dry_pressure_drop_pa"]])
        eps_sp = float(k[k_map["eps_sp"]])
        eps_sm = float(k[k_map["eps_sm"]])
        k_min = float(k[k_map["kettle_min_holdup_mol"]])
        k_coeff = float(k[k_map["kettle_boilup_coeff"]])
        shell_volume = max(1.0e-6, float(k[k_map["condenser_shell_volume_m3"]]))
        distillate_sub = max(0.0, float(k[k_map["distillate_nozzle_submergence_m"]]))
        reflux_sub = max(0.0, float(k[k_map["reflux_nozzle_submergence_m"]]))
        z_h = max(0.2, float(k[k_map["headspace_compressibility"]]))
        eps_v = max(1.0e-12, float(k[k_map["eps_v"]]))
        eps_h = 1.0e-6
        eps_rho = 1.0e-6

        feed_flows = np.asarray(u[u_map["feed_flows"]], dtype=np.float64).reshape(n_feeds)
        feed_temps = np.asarray(u[u_map["feed_temperatures"]], dtype=np.float64).reshape(n_feeds)
        feed_pressures = np.asarray(u[u_map["feed_pressures"]], dtype=np.float64).reshape(n_feeds)
        feed_comps = np.asarray(u[u_map["feed_compositions"]], dtype=np.float64).reshape(
            n_feeds, n_species
        )
        feed_trays = np.asarray(k[k_map["feed_tray_indices"]], dtype=np.float64).reshape(n_feeds)
        blanket_flow = np.clip(
            np.asarray(u[u_map["blanket_gas_component_flow"]], dtype=np.float64).reshape(-1),
            0.0,
            None,
        )
        vent_flow = np.clip(
            np.asarray(u[u_map["headspace_vent_component_flow"]], dtype=np.float64).reshape(-1),
            0.0,
            None,
        )

        q_cond = float(u[u_map["condenser_duty_request_W"]])
        q_reb = float(u[u_map["reboiler_duty_request_W"]])
        distillate_request = max(0.0, float(u[u_map["distillate_withdrawal_flow"]]))
        reflux_request = max(0.0, float(u[u_map["reflux_withdrawal_flow"]]))
        bottoms_request = float(u[u_map["bottoms_withdrawal_flow"]])
        accepted_dt = max(float(u[u_map["accepted_dt_s"]]), _MIN_STEP_SECONDS)

        tray_pressures = np.asarray(
            [p_top_anchor + j * delta_p for j in range(n_trays)], dtype=np.float64
        )
        x = np.vstack([_safe_owner_fraction(row, n_species=n_species) for row in tray_holdup])

        y_vap = np.zeros_like(x)
        rho_liq = np.zeros(n_trays, dtype=np.float64)
        rho_vap = np.zeros(n_trays, dtype=np.float64)
        mw_liq = np.zeros(n_trays, dtype=np.float64)
        for j in range(n_trays):
            thermo = dc.thermo_pr(
                package,
                temperature_k=float(tray_temperature[j]),
                pressure_pa=float(tray_pressures[j]),
                composition=x[j],
            )
            y_vap[j] = dc.normalized_composition(
                thermo.k_values * x[j],
                n_species=n_species,
            )
            rho_liq[j] = max(eps_rho, float(thermo.rho_liq_kg_m3))
            rho_vap[j] = max(eps_rho, float(thermo.rho_vap_kg_m3))
            # The thermo package returns g/mol; hydraulics need kg/mol here.
            mw_liq[j] = float(package.molecular_weight(tuple(float(v) for v in x[j]))) / 1000.0

        liq_flow = np.zeros(n_trays, dtype=np.float64)
        stage_total = np.sum(np.clip(tray_holdup, 0.0, None), axis=1)
        tray_height = np.zeros(n_trays, dtype=np.float64)
        for j in range(n_trays):
            v_liq = stage_total[j] * mw_liq[j] / max(rho_liq[j], eps_rho)
            h_liq = v_liq / area
            tray_height[j] = h_liq
            liq_flow[j] = liquid_coeff * dc.smooth_plus(h_liq - weir_height, eps_sp) ** 1.5

        z_kettle = _safe_owner_fraction(kettle_moles, n_species=n_species)
        z_drum = _safe_owner_fraction_zeros(drum_moles, n_species=n_species)
        z_drum_mw = _safe_owner_fraction(drum_moles, n_species=n_species)

        h_liq_drum_anchor, _cp_liq_drum_anchor, rho_liq_drum = dc.thermo_pr_liq(
            package,
            temperature_k=float(drum_temp),
            pressure_pa=float(p_top_anchor),
            composition=z_drum,
        )
        mw_drum = float(package.molecular_weight(tuple(float(v) for v in z_drum_mw))) / 1000.0
        drum_total_moles = float(np.sum(np.clip(drum_moles, 0.0, None)))
        drum_liquid_volume = (
            0.0
            if drum_total_moles <= _MIN_SUM
            else _liquid_volume_m3(
                total_moles=drum_total_moles,
                molecular_weight_kg_per_mol=float(
                    package.molecular_weight(tuple(float(v) for v in z_drum))
                )
                / 1000.0,
                liquid_density_kg_m3=rho_liq_drum,
            )
        )
        headspace_volume = max(eps_v, shell_volume - drum_liquid_volume)
        n_x = float(np.sum(np.clip(headspace_moles, 0.0, None)))
        p_x = n_x * z_h * _R * max(1.0, headspace_temp) / headspace_volume
        p_bubble_raw = _pr_bubble_pressure_pa(
            package,
            temperature_k=drum_temp,
            composition=z_drum,
            fallback_pressure_pa=p_top_anchor,
        )
        p_bubble = max(5.0e4, min(5.0e6, p_bubble_raw))
        p_head = max(1.0, p_bubble + p_x)

        # GE-TTD-MAT-3a: live top pressure anchor.
        p_top_live = p_head

        # GE-TTD-MAT-3b first-pass decomposition at initial live tray pressures.
        tray_pressure_drop = dry_dp + rho_liq * _G * tray_height + delta_p
        p_bottom_live = p_top_live + float(np.sum(tray_pressure_drop))

        # GE-TTD-MAT-3c: interpolate tray pressures between live ends.
        tray_span = max(n_trays - 1, 1)
        tray_pressures = np.asarray(
            [p_top_live + (j / tray_span) * (p_bottom_live - p_top_live) for j in range(n_trays)],
            dtype=np.float64,
        )

        # Re-evaluate tray thermo closures at final live tray pressures.
        for j in range(n_trays):
            thermo = dc.thermo_pr(
                package,
                temperature_k=float(tray_temperature[j]),
                pressure_pa=float(tray_pressures[j]),
                composition=x[j],
            )
            y_vap[j] = dc.normalized_composition(
                thermo.k_values * x[j],
                n_species=n_species,
            )
            rho_liq[j] = max(eps_rho, float(thermo.rho_liq_kg_m3))
            rho_vap[j] = max(eps_rho, float(thermo.rho_vap_kg_m3))

        for j in range(n_trays):
            v_liq = stage_total[j] * mw_liq[j] / max(rho_liq[j], eps_rho)
            h_liq = v_liq / area
            tray_height[j] = h_liq
            liq_flow[j] = liquid_coeff * dc.smooth_plus(h_liq - weir_height, eps_sp) ** 1.5

        tray_pressure_drop = dry_dp + rho_liq * _G * tray_height + delta_p
        p_bottom_live = p_top_live + float(np.sum(tray_pressure_drop))
        tray_pressures = np.asarray(
            [p_top_live + (j / tray_span) * (p_bottom_live - p_top_live) for j in range(n_trays)],
            dtype=np.float64,
        )

        _h_liq_drum_live_for_density, _cp_liq_drum_live, rho_liq_drum_live = dc.thermo_pr_liq(
            package,
            temperature_k=float(drum_temp),
            pressure_pa=float(p_head),
            composition=z_drum,
        )
        distillate_source_pressure = p_head + rho_liq_drum_live * _G * distillate_sub
        reflux_source_pressure = p_head + rho_liq_drum_live * _G * reflux_sub

        p_kettle = p_bottom_live
        kettle_flash = dc.feed_flash_pr(
            package,
            temperature_k=float(y[y_map["reboiler_kettle_temperature"]]),
            pressure_pa=float(p_kettle),
            composition=z_kettle,
        )
        latent_b = max(eps_h, float(kettle_flash.h_vap_j_per_mol - kettle_flash.h_liq_j_per_mol))
        v_therm_b = dc.smooth_plus(q_reb, eps_sp) / latent_b
        v_cap_b = k_coeff * np.sqrt(dc.smooth_plus(float(np.sum(kettle_moles)) - k_min, eps_sp))
        v_b = dc.smooth_min(v_therm_b, v_cap_b, eps_sm)

        vap_flow = np.zeros(n_trays, dtype=np.float64)
        vapor_supply = v_b
        feed_flashes: list[dc.ThermoPRState] = []
        for m in range(n_feeds):
            feed_flashes.append(
                dc.feed_flash_pr(
                    package,
                    temperature_k=float(feed_temps[m]),
                    pressure_pa=float(max(1.0, feed_pressures[m])),
                    composition=feed_comps[m],
                )
            )
        for j in range(n_trays - 1, -1, -1):
            vapor_feed = 0.0
            for m in range(n_feeds):
                if int(round(float(feed_trays[m]))) - 1 != j:
                    continue
                f = max(0.0, float(feed_flows[m]))
                vapor_feed += float(feed_flashes[m].vapor_fraction) * f
            dp_avail = dc.smooth_plus(
                tray_pressure_drop[j] - rho_liq[j] * _G * tray_height[j] - dry_dp, eps_sp
            )
            v_cap = vapor_coeff * np.sqrt(dp_avail / max(rho_vap[j], eps_rho))
            vap_flow[j] = dc.smooth_min(v_cap, vapor_supply + vapor_feed, eps_sm)
            vapor_supply = vap_flow[j]

        z_bottom = _safe_owner_fraction_zeros(kettle_moles, n_species=n_species)

        v_top = max(0.0, float(vap_flow[0]))
        h_vap_top = float(
            dc.thermo_pr(
                package,
                temperature_k=float(tray_temperature[0]),
                pressure_pa=float(tray_pressures[0]),
                composition=x[0],
            ).h_vap_j_per_mol
        )
        h_liq_drum_live = float(
            dc.thermo_pr_liq(
                package,
                temperature_k=float(drum_temp),
                pressure_pa=float(p_head),
                composition=z_drum,
            )[0]
        )
        q_cond_avail = max(0.0, -q_cond)
        v_cond_therm = q_cond_avail / max(h_vap_top - h_liq_drum_live, eps_h)
        realized_condensed = min(v_top, max(0.0, v_cond_therm))
        non_condensed = max(0.0, v_top - realized_condensed)

        # GE-TTD-END-2: shared condenser-drum realizability budget
        eps_n = float(k[k_map["eps_n"]])
        D_R_budget = max(0.0, drum_total_moles - eps_n) / accepted_dt
        if D_R_budget <= 0.0:
            distillate_flow = 0.0
            reflux_flow_val = 0.0
        else:
            D_realized = min(distillate_request, D_R_budget)
            R_realized = min(reflux_request, D_R_budget - D_realized)
            distillate_flow = D_realized
            reflux_flow_val = R_realized
        bottoms_flow = _realized_withdrawal_flow(
            requested_flow=bottoms_request, owner_moles=kettle_moles, dt_s=accepted_dt
        )

        tray_q = np.zeros(n_trays, dtype=np.float64)

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["tray_pressures_pa"]] = tray_pressures
        result[algebraic_map["tray_liquid_composition"]] = x.reshape(-1)
        result[algebraic_map["tray_vapor_composition"]] = y_vap.reshape(-1)
        result[algebraic_map["tray_liquid_flow"]] = liq_flow
        result[algebraic_map["tray_vapor_flow"]] = vap_flow
        result[algebraic_map["tray_heat_input"]] = tray_q
        result[algebraic_map["reboiler_latent_heat_j_per_mol"]] = latent_b
        result[algebraic_map["distillate_flow"]] = distillate_flow
        result[algebraic_map["reflux_flow"]] = reflux_flow_val
        result[algebraic_map["bottoms_flow"]] = bottoms_flow
        result[algebraic_map["distillate_composition"]] = z_drum
        result[algebraic_map["bottoms_composition"]] = z_bottom
        result[algebraic_map["distillate_temperature"]] = float(
            y[y_map["condenser_drum_temperature"]]
        )
        result[algebraic_map["bottoms_temperature"]] = float(
            y[y_map["reboiler_kettle_temperature"]]
        )
        result[algebraic_map["realized_condensed_flow"]] = realized_condensed
        result[algebraic_map["non_condensed_flow"]] = non_condensed
        result[algebraic_map["headspace_pressure_pa"]] = p_head
        result[algebraic_map["distillate_source_pressure_pa"]] = distillate_source_pressure
        result[algebraic_map["reflux_source_pressure_pa"]] = reflux_source_pressure
        result[algebraic_map["bottom_pressure_pa"]] = p_bottom_live
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
        del t
        n_species = int(round(float(k[k_map["n_species"]])))
        n_feeds = int(round(float(k[k_map["n_feeds"]])))
        n_trays = int(round(float(k[k_map["n_trays"]])))
        species_selector = tuple(
            int(round(float(value)))
            for value in np.asarray(k[k_map["species_selector"]], dtype=np.float64).reshape(-1)
        )
        package = _pr_package_for_species_selector(species_selector)

        tray_holdup = np.asarray(y[y_map["tray_component_holdup"]], dtype=np.float64).reshape(
            n_trays, n_species
        )
        tray_temperature = np.asarray(y[y_map["tray_temperature"]], dtype=np.float64).reshape(
            n_trays
        )
        drum_moles = np.asarray(
            y[y_map["condenser_drum_component_moles"]], dtype=np.float64
        ).reshape(-1)
        drum_temp = float(y[y_map["condenser_drum_temperature"]])
        headspace_moles = np.asarray(
            y[y_map["condenser_headspace_component_moles"]], dtype=np.float64
        ).reshape(-1)
        headspace_temp = float(y[y_map["condenser_headspace_temperature"]])
        kettle_moles = np.asarray(
            y[y_map["reboiler_kettle_component_moles"]], dtype=np.float64
        ).reshape(-1)
        kettle_temp = float(y[y_map["reboiler_kettle_temperature"]])

        feed_flows = np.asarray(u[u_map["feed_flows"]], dtype=np.float64).reshape(n_feeds)
        feed_temps = np.asarray(u[u_map["feed_temperatures"]], dtype=np.float64).reshape(n_feeds)
        feed_pressures = np.asarray(u[u_map["feed_pressures"]], dtype=np.float64).reshape(n_feeds)
        feed_comps = np.asarray(u[u_map["feed_compositions"]], dtype=np.float64).reshape(
            n_feeds, n_species
        )
        blanket_flow = np.clip(
            np.asarray(u[u_map["blanket_gas_component_flow"]], dtype=np.float64).reshape(-1),
            0.0,
            None,
        )
        vent_flow = np.clip(
            np.asarray(u[u_map["headspace_vent_component_flow"]], dtype=np.float64).reshape(-1),
            0.0,
            None,
        )
        feed_trays = np.asarray(k[k_map["feed_tray_indices"]], dtype=np.float64).reshape(n_feeds)

        q_cond = float(u[u_map["condenser_duty_request_W"]])
        q_reb = float(u[u_map["reboiler_duty_request_W"]])
        accepted_dt = max(float(u[u_map["accepted_dt_s"]]), _MIN_STEP_SECONDS)
        eps_n = float(k[k_map["eps_n"]])
        eps_c = float(k[k_map["eps_c"]])
        eps_h = 1.0e-6
        eps_sp = float(k[k_map["eps_sp"]])
        eps_sm = float(k[k_map["eps_sm"]])
        k_min = float(k[k_map["kettle_min_holdup_mol"]])
        k_coeff = float(k[k_map["kettle_boilup_coeff"]])
        p_top_anchor = float(k[k_map["p_top_pa"]])
        delta_p = float(k[k_map["tray_residual_pressure_drop_pa"]])
        shell_volume = max(1.0e-6, float(k[k_map["condenser_shell_volume_m3"]]))
        z_h = max(0.2, float(k[k_map["headspace_compressibility"]]))
        eps_v = max(1.0e-12, float(k[k_map["eps_v"]]))
        tau_head = max(0.0, float(k[k_map["headspace_temperature_relaxation_1_s"]]))

        tray_pressures = np.asarray(
            algebraic[algebraic_map["tray_pressures_pa"]], dtype=np.float64
        ).reshape(n_trays)
        x = np.asarray(
            algebraic[algebraic_map["tray_liquid_composition"]], dtype=np.float64
        ).reshape(n_trays, n_species)
        y_vap = np.asarray(
            algebraic[algebraic_map["tray_vapor_composition"]], dtype=np.float64
        ).reshape(n_trays, n_species)
        liq_flow = np.asarray(
            algebraic[algebraic_map["tray_liquid_flow"]], dtype=np.float64
        ).reshape(n_trays)
        vap_flow = np.asarray(
            algebraic[algebraic_map["tray_vapor_flow"]], dtype=np.float64
        ).reshape(n_trays)
        tray_q = np.asarray(algebraic[algebraic_map["tray_heat_input"]], dtype=np.float64).reshape(
            n_trays
        )
        distillate_flow = float(algebraic[algebraic_map["distillate_flow"]])
        reflux_flow = float(algebraic[algebraic_map["reflux_flow"]])
        bottoms_flow = float(algebraic[algebraic_map["bottoms_flow"]])
        realized_condensed = float(algebraic[algebraic_map["realized_condensed_flow"]])
        non_condensed = float(algebraic[algebraic_map["non_condensed_flow"]])
        p_head = max(1.0, float(algebraic[algebraic_map["headspace_pressure_pa"]]))
        p_bottom_live = max(p_head, float(algebraic[algebraic_map["bottom_pressure_pa"]]))

        z_drum_mw = _safe_owner_fraction(drum_moles, n_species=n_species)
        z_drum = _safe_owner_fraction(drum_moles, n_species=n_species)
        z_kettle = _safe_owner_fraction(kettle_moles, n_species=n_species)

        tray_thermo: list[dc.ThermoPRState] = []
        for j in range(n_trays):
            tray_thermo.append(
                dc.thermo_pr(
                    package,
                    temperature_k=float(tray_temperature[j]),
                    pressure_pa=float(tray_pressures[j]),
                    composition=x[j],
                )
            )

        feed_flashes: list[dc.ThermoPRState] = []
        for m in range(n_feeds):
            feed_flashes.append(
                dc.feed_flash_pr(
                    package,
                    temperature_k=float(feed_temps[m]),
                    pressure_pa=float(max(1.0, feed_pressures[m])),
                    composition=feed_comps[m],
                )
            )

        p_kettle = p_bottom_live
        kettle_flash = dc.feed_flash_pr(
            package,
            temperature_k=float(kettle_temp),
            pressure_pa=float(p_kettle),
            composition=z_kettle,
        )
        y_kettle = dc.normalized_composition(kettle_flash.vapor_composition, n_species=n_species)
        h_liq_kettle = float(kettle_flash.h_liq_j_per_mol)
        h_vap_kettle = float(kettle_flash.h_vap_j_per_mol)
        cp_kettle = max(1.0, float(kettle_flash.cp_liq_j_per_mol_k))

        latent_b = max(eps_h, h_vap_kettle - h_liq_kettle)
        v_therm_b = dc.smooth_plus(q_reb, eps_sp) / latent_b
        v_cap_b = k_coeff * np.sqrt(dc.smooth_plus(float(np.sum(kettle_moles)) - k_min, eps_sp))
        boilup_flow = dc.smooth_min(v_therm_b, v_cap_b, eps_sm)

        d_tray = np.zeros_like(tray_holdup)
        d_t_tray = np.zeros(n_trays, dtype=np.float64)

        for j in range(n_trays):
            liq_in_flow = reflux_flow if j == 0 else max(0.0, liq_flow[j - 1])
            liq_in_comp = z_drum if j == 0 else x[j - 1]
            vap_in_flow = boilup_flow if j == n_trays - 1 else max(0.0, vap_flow[j + 1])
            vap_in_comp = y_kettle if j == n_trays - 1 else y_vap[j + 1]

            feed_component = np.zeros(n_species, dtype=np.float64)
            feed_hdot = 0.0
            for m in range(n_feeds):
                if int(round(float(feed_trays[m]))) - 1 != j:
                    continue
                f = max(0.0, float(feed_flows[m]))
                ff = feed_flashes[m]
                beta = float(ff.vapor_fraction)
                x_feed = dc.normalized_composition(ff.liquid_composition, n_species=n_species)
                y_feed = dc.normalized_composition(ff.vapor_composition, n_species=n_species)
                feed_component += (1.0 - beta) * f * x_feed + beta * f * y_feed
                h_liq_feed = float(ff.h_liq_j_per_mol)
                h_vap_feed = float(ff.h_vap_j_per_mol)
                feed_hdot += (1.0 - beta) * f * h_liq_feed + beta * f * h_vap_feed

            in_component = liq_in_flow * liq_in_comp + vap_in_flow * vap_in_comp + feed_component
            out_component = max(0.0, liq_flow[j]) * x[j] + max(0.0, vap_flow[j]) * y_vap[j]
            d_tray[j] = in_component - out_component

            h_liq_j = float(tray_thermo[j].h_liq_j_per_mol)
            h_vap_j = float(tray_thermo[j].h_vap_j_per_mol)
            cp_j = max(1.0, float(tray_thermo[j].cp_liq_j_per_mol_k))

            h_liq_in = (
                float(
                    dc.thermo_pr_liq(
                        package,
                        temperature_k=drum_temp,
                        pressure_pa=p_head,
                        composition=z_drum,
                    )[0]
                )
                if j == 0
                else float(tray_thermo[j - 1].h_liq_j_per_mol)
            )
            h_vap_in = (
                h_vap_kettle if j == n_trays - 1 else float(tray_thermo[j + 1].h_vap_j_per_mol)
            )
            hdot_in = liq_in_flow * h_liq_in + vap_in_flow * h_vap_in + feed_hdot
            hdot_out = max(0.0, liq_flow[j]) * h_liq_j + max(0.0, vap_flow[j]) * h_vap_j
            n_liq = max(eps_n, float(np.sum(np.clip(tray_holdup[j], 0.0, None))))
            d_t_tray[j] = (
                hdot_in - hdot_out + tray_q[j] - h_liq_j * float(np.sum(d_tray[j]))
            ) / max(n_liq * cp_j, eps_c)

        interface_recondensation = ThermoTrayDistillationColumnTotalCondenser._collapsed_headspace_interface_recondensation_flow(
            realized_condensed_flow=realized_condensed,
            non_condensed_flow=non_condensed,
            y_top=y_vap[0],
        )
        d_drum = (
            realized_condensed * y_vap[0]
            - distillate_flow * z_drum
            - reflux_flow * z_drum
            + interface_recondensation
        )
        d_headspace = non_condensed * y_vap[0] + blanket_flow - vent_flow - interface_recondensation
        d_kettle = max(0.0, liq_flow[-1]) * x[-1] - bottoms_flow * z_kettle - boilup_flow * y_kettle

        h_liq_drum, cp_drum, _ = dc.thermo_pr_liq(
            package,
            temperature_k=float(drum_temp),
            pressure_pa=float(p_head),
            composition=z_drum,
        )
        h_vap_1 = float(tray_thermo[0].h_vap_j_per_mol)
        n_drum_raw = float(np.sum(np.clip(drum_moles, 0.0, None)))
        n_drum = max(eps_n, n_drum_raw)
        # GE-TTD-END-3: dry-drum temperature guard
        dry_guard = float(k[k_map["dry_guard_drum_threshold_mol"]])
        if n_drum_raw < dry_guard:
            d_t_drum = 0.0
        else:
            d_t_drum = (
                realized_condensed * h_vap_1
                - distillate_flow * h_liq_drum
                - reflux_flow * h_liq_drum
                + q_cond
                - h_liq_drum * float(np.sum(d_drum))
            ) / max(n_drum * cp_drum, eps_c)

        n_x = float(np.sum(np.clip(headspace_moles, 0.0, None)))
        mw_head = (
            float(
                package.molecular_weight(
                    tuple(
                        float(v) for v in _safe_owner_fraction(headspace_moles, n_species=n_species)
                    )
                )
            )
            / 1000.0
        )
        rho_liq_drum = max(
            1.0,
            float(
                dc.thermo_pr_liq(
                    package,
                    temperature_k=float(drum_temp),
                    pressure_pa=float(max(1.0, p_top_anchor)),
                    composition=z_drum,
                )[2]
            ),
        )
        drum_liq_volume = 0.0
        if n_drum_raw > _MIN_SUM:
            drum_liq_volume = _liquid_volume_m3(
                total_moles=n_drum_raw,
                molecular_weight_kg_per_mol=float(
                    package.molecular_weight(tuple(float(v) for v in z_drum_mw))
                )
                / 1000.0,
                liquid_density_kg_m3=rho_liq_drum,
            )
        headspace_volume = max(eps_v, shell_volume - drum_liq_volume)
        cp_head = max(20.0, 35.0 + 8.0 * mw_head * 1000.0)
        h_gas = cp_head * max(1.0, headspace_temp)
        d_t_head = 0.0
        if n_x > eps_n:
            h_in = non_condensed * h_vap_1 + float(np.sum(blanket_flow)) * cp_head * max(
                1.0, drum_temp
            )
            h_out = float(np.sum(vent_flow)) * h_gas
            d_t_head = (h_in - h_out - h_gas * float(np.sum(d_headspace))) / max(
                n_x * cp_head, eps_c
            )
        d_t_head += tau_head * (drum_temp - headspace_temp)

        h_liq_n = float(tray_thermo[-1].h_liq_j_per_mol)
        n_kettle = max(eps_n, float(np.sum(np.clip(kettle_moles, 0.0, None))))
        d_t_kettle = (
            max(0.0, liq_flow[-1]) * h_liq_n
            - bottoms_flow * h_liq_kettle
            - boilup_flow * h_vap_kettle
            + q_reb
            - h_liq_kettle * float(np.sum(d_kettle))
        ) / max(n_kettle * cp_kettle, eps_c)

        dy = np.zeros_like(y)
        dy[y_map["tray_component_holdup"]] = d_tray.reshape(-1)
        dy[y_map["tray_temperature"]] = d_t_tray
        dy[y_map["condenser_drum_component_moles"]] = d_drum
        dy[y_map["condenser_drum_temperature"]] = d_t_drum
        dy[y_map["condenser_headspace_component_moles"]] = d_headspace
        dy[y_map["condenser_headspace_temperature"]] = d_t_head
        dy[y_map["reboiler_kettle_component_moles"]] = d_kettle
        dy[y_map["reboiler_kettle_temperature"]] = d_t_kettle
        return dy


class ThermoTrayDistillationColumnPartialCondenser(ProcessModel):
    @override
    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        raise NotImplementedError(
            "ThermoTrayDistillationColumnPartialCondenser is a reserved backend-only "
            "boundary and is not implemented in Wave 2."
        )

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
        raise NotImplementedError(
            "ThermoTrayDistillationColumnPartialCondenser is reserved for a future wave."
        )

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
        raise NotImplementedError(
            "ThermoTrayDistillationColumnPartialCondenser is reserved for a future wave."
        )


ThermoTrayDistillationColumn = ThermoTrayDistillationColumnTotalCondenser


__all__ = [
    "ThermoTrayDistillationColumnTotalCondenser",
    "ThermoTrayDistillationColumnPartialCondenser",
    "ThermoTrayDistillationColumn",
]
