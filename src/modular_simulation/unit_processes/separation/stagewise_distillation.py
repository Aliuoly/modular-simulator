from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from math import ceil, isfinite, pi
from typing import Annotated, ClassVar, cast, override

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

_COMPOSITION_TOL = 1.0e-8
_MIN_SUM = 1.0e-12
_MIN_STEP_SECONDS = 1.0e-12
_MAX_REFINEMENT_SUBDIVISIONS = 16
_MIN_REFINEMENT_SUBSTEP_S = 1.0e-3


def _coerce_1d(
    value: NDArray[np.float64], *, expected_size: int, default: float, name: str
) -> NDArray[np.float64]:
    arr = np.asarray(value, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return np.full(expected_size, default, dtype=np.float64)
    if arr.size != expected_size:
        raise ValueError(f"{name} length mismatch: expected {expected_size}, got {arr.size}.")
    return arr


def _normalize_composition(raw: NDArray[np.float64], *, n_species: int) -> NDArray[np.float64]:
    z = np.asarray(raw, dtype=np.float64).reshape(-1)
    if z.size != n_species:
        raise ValueError(f"composition length mismatch: expected {n_species}, got {z.size}.")
    if not np.all(np.isfinite(z)):
        raise ValueError("composition must contain only finite values.")
    if np.any(z < 0.0):
        raise ValueError("composition must contain non-negative values.")
    total = float(np.sum(z))
    if total <= _MIN_SUM:
        return np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
    normalized = z / total
    if abs(float(np.sum(normalized)) - 1.0) > _COMPOSITION_TOL:
        raise ValueError("composition normalization failed.")
    return normalized


def _safe_fraction_from_moles(moles: NDArray[np.float64], *, n_species: int) -> NDArray[np.float64]:
    clipped = np.clip(np.asarray(moles, dtype=np.float64).reshape(-1), 0.0, None)
    if clipped.size != n_species:
        raise ValueError(f"mole vector length mismatch: expected {n_species}, got {clipped.size}.")
    total = float(np.sum(clipped))
    if total <= _MIN_SUM:
        return np.full(n_species, 1.0 / float(n_species), dtype=np.float64)
    return clipped / total


def _owner_fraction_from_moles(
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
    *, requested_flow: float, owner_moles: NDArray[np.float64], dt_s: float | None = None
) -> float:
    bounded_request = max(0.0, float(requested_flow))
    owner_total = float(
        np.sum(np.clip(np.asarray(owner_moles, dtype=np.float64).reshape(-1), 0.0, None))
    )
    if owner_total <= _MIN_SUM:
        return 0.0
    if dt_s is None:
        return min(bounded_request, owner_total)
    bounded_dt_s = max(float(dt_s), _MIN_STEP_SECONDS)
    return min(bounded_request, owner_total / bounded_dt_s)


class StagewiseDistillationColumn(ProcessModel):
    _OUTLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "distillate": PortAttributeMap(
            flow="distillate_flow",
            temperature="distillate_temperature",
            pressure="column_pressure_pa",
            composition="distillate_composition",
        ),
        "bottoms": PortAttributeMap(
            flow="bottoms_flow",
            temperature="bottoms_temperature",
            pressure="column_pressure_pa",
            composition="bottoms_composition",
        ),
        "reflux_outlet": PortAttributeMap(
            flow="reflux_outlet_flow",
            temperature="reflux_outlet_temperature",
            pressure="column_pressure_pa",
            composition="reflux_outlet_composition",
        ),
    }

    stage_component_moles: Annotated[
        NDArray[np.float64],
        M(
            type=T.DIFFERENTIAL,
            unit="mol",
            description="flattened stage-by-species component inventories",
        ),
    ] = np.zeros(0, dtype=np.float64)
    reflux_drum_component_moles: Annotated[
        NDArray[np.float64],
        M(
            type=T.DIFFERENTIAL,
            unit="mol",
            description="duty-limited condenser surrogate reflux-drum component inventory",
        ),
    ] = np.zeros(0, dtype=np.float64)
    bottoms_sump_component_moles: Annotated[
        NDArray[np.float64],
        M(
            type=T.DIFFERENTIAL,
            unit="mol",
            description="kettle reboiler bottoms-sump component inventory",
        ),
    ] = np.zeros(0, dtype=np.float64)
    column_pressure_pa: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="Pa",
            description="shared pressure interface derived from top/bottom vapor-region state solution",
        ),
    ] = 101325.0
    stage_internal_energy_J: Annotated[
        NDArray[np.float64],
        M(
            type=T.DIFFERENTIAL,
            unit="J",
            description="reduced-order stage liquid internal energies",
        ),
    ] = np.zeros(0, dtype=np.float64)
    reflux_drum_internal_energy_J: Annotated[
        float,
        M(
            type=T.DIFFERENTIAL,
            unit="J",
            description="reflux-drum internal energy state",
        ),
    ] = 0.0
    bottoms_sump_internal_energy_J: Annotated[
        float,
        M(
            type=T.DIFFERENTIAL,
            unit="J",
            description="bottoms-sump internal energy state",
        ),
    ] = 0.0
    top_vapor_holdup_mol: Annotated[
        float,
        M(
            type=T.DIFFERENTIAL,
            unit="mol",
            description="top-region vapor holdup pressure-driving state",
        ),
    ] = 1.0
    bottom_vapor_holdup_mol: Annotated[
        float,
        M(
            type=T.DIFFERENTIAL,
            unit="mol",
            description="bottom-region vapor holdup pressure-driving state",
        ),
    ] = 1.0

    feed_flows: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="mol/s", description="molar feed rates by feed index"),
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
        M(
            type=T.BOUNDARY,
            unit="",
            description="feed compositions by feed index and species index",
        ),
    ] = np.zeros((0, 0), dtype=np.float64)
    reflux_return_flow: Annotated[
        float, M(type=T.BOUNDARY, unit="mol/s", description="external reflux-return molar flow")
    ] = 0.0
    reflux_return_temperature: Annotated[
        float,
        M(type=T.BOUNDARY, unit="K", description="external reflux-return stream temperature"),
    ] = 298.15
    reflux_return_pressure: Annotated[
        float,
        M(type=T.BOUNDARY, unit="Pa", description="external reflux-return stream pressure"),
    ] = 101325.0
    reflux_return_composition: Annotated[
        NDArray[np.float64],
        M(type=T.BOUNDARY, unit="", description="external reflux-return composition vector"),
    ] = np.zeros(0, dtype=np.float64)
    distillate_withdrawal_flow: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="mol/s",
            description="external distillate withdrawal request from reflux-drum holdup",
        ),
    ] = 0.0
    bottoms_withdrawal_flow: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="mol/s",
            description="external bottoms withdrawal request from bottoms-sump holdup",
        ),
    ] = 0.0
    condenser_duty_request_W: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="W",
            description=(
                "requested condenser duty; negative removes heat and drives Q/lambda condensation"
            ),
        ),
    ] = 0.0
    reboiler_duty_request_W: Annotated[
        float,
        M(
            type=T.BOUNDARY,
            unit="W",
            description=("requested reboiler duty; positive adds heat and drives Q/lambda boilup"),
        ),
    ] = 0.0

    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2
    n_feeds: Annotated[int, M(type=T.CONSTANT, unit="", description="number of feed ports")] = 1
    n_stages: Annotated[
        int, M(type=T.CONSTANT, unit="", description="tray-equivalent contacting stages")
    ] = 8
    feed_stage_indices: Annotated[
        NDArray[np.float64],
        M(type=T.CONSTANT, unit="", description="1-based feed stage assignment indices"),
    ] = np.zeros(0, dtype=np.float64)
    active_contact_height_m: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="m",
            description="active contacting height controlling tray-equivalent stage count",
        ),
    ] = 4.0
    tray_spacing_m: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="m",
            description="fixed tray spacing used to infer tray-equivalent stages",
        ),
    ] = 0.5
    shell_diameter_m: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="m",
            description="column shell diameter controlling area, holdup/residence, and capacity semantics",
        ),
    ] = 1.0
    reflux_ratio: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="reference/derived L/D indicator (non-actuating)"),
    ] = 1.5
    boilup_ratio: Annotated[
        float,
        M(type=T.CONSTANT, unit="", description="reference/derived V/B indicator (non-actuating)"),
    ] = 1.2
    stage_liquid_flow_mol_s: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="mol/s",
            description="constant-molar-overflow liquid downflow for stage coupling",
        ),
    ] = 6.0
    stage_vapor_flow_mol_s: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="mol/s",
            description="constant-molar-overflow vapor upflow for stage coupling",
        ),
    ] = 6.0
    pressure_relaxation_time_s: Annotated[
        float,
        M(type=T.CONSTANT, unit="s", description="first-order pressure relaxation constant"),
    ] = 10.0
    relative_volatility_reference: Annotated[
        NDArray[np.float64],
        M(
            type=T.CONSTANT,
            unit="",
            description="constant relative-volatility alpha vector (HK-referenced first slice)",
        ),
    ] = np.zeros(0, dtype=np.float64)
    condenser_latent_heat_j_per_mol: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="J/mol",
            description="fixed latent heat surrogate for condenser Q/lambda mapping",
        ),
    ] = 30000.0
    reboiler_latent_heat_j_per_mol: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="J/mol",
            description="fixed latent heat surrogate for reboiler Q/lambda mapping",
        ),
    ] = 30000.0

    distillate_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="distillate product flow"),
    ] = 0.0
    bottoms_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="bottoms product flow"),
    ] = 0.0
    distillate_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="distillate product composition"),
    ] = np.zeros(0, dtype=np.float64)
    bottoms_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="bottoms product composition"),
    ] = np.zeros(0, dtype=np.float64)
    distillate_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="distillate stream temperature proxy"),
    ] = 298.15
    bottoms_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="bottoms stream temperature proxy"),
    ] = 298.15
    reflux_outlet_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="reflux liquid flow returned to top stage"),
    ] = 0.0
    reflux_outlet_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="reflux liquid outlet temperature proxy"),
    ] = 298.15
    reflux_outlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="reflux liquid outlet composition"),
    ] = np.zeros(0, dtype=np.float64)
    condenser_duty_W: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="W",
            description="realized condenser duty with negative sign convention for heat removal",
        ),
    ] = 0.0
    reboiler_duty_W: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="W",
            description="realized reboiler duty with positive sign convention for heat addition",
        ),
    ] = 0.0
    realized_condensed_flow_mol_s: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="mol/s",
            description="realized top-vapor condensation flow mapped from condenser Q/lambda",
        ),
    ] = 0.0
    realized_reboiler_boilup_flow_mol_s: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="mol/s",
            description="realized reboiler boilup flow mapped from reboiler Q/lambda",
        ),
    ] = 0.0
    maximum_vapor_capacity_flow_mol_s: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="mol/s",
            description="diameter-scaled vapor throughput capacity proxy limit",
        ),
    ] = 0.0
    maximum_liquid_capacity_flow_mol_s: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="mol/s",
            description="diameter-scaled liquid handling throughput capacity limit",
        ),
    ] = 0.0
    representative_internal_liquid_traffic_mol_s: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="mol/s",
            description="representative internal liquid tray-traffic from reduced hydraulic calculation",
        ),
    ] = 0.0
    representative_internal_vapor_traffic_mol_s: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="mol/s",
            description="representative internal vapor tray-traffic from reduced hydraulic calculation",
        ),
    ] = 0.0

    _ports: UnitProcessPorts = UnitProcessPorts(
        ("feed_1", "reflux_return"), ("distillate", "bottoms", "reflux_outlet")
    )

    def __init__(self, **data: object) -> None:
        feed_stage_indices_data = data.pop("feed_stage_indices", None)
        active_contact_height = float(data.get("active_contact_height_m", 4.0))
        tray_spacing = float(data.get("tray_spacing_m", 0.5))

        if not isfinite(active_contact_height) or active_contact_height <= 0.0:
            raise ValueError("active_contact_height_m must be finite and positive.")
        if not isfinite(tray_spacing) or tray_spacing <= 0.0:
            raise ValueError("tray_spacing_m must be finite and positive.")

        inferred_stages = max(2, int(ceil(active_contact_height / tray_spacing)))
        data["n_stages"] = inferred_stages

        if feed_stage_indices_data is None:
            feed_stage_indices_data = (max(1, inferred_stages // 2),)
        feed_stage_indices_tuple = tuple(
            int(value) for value in cast(tuple[int, ...], feed_stage_indices_data)
        )
        if len(feed_stage_indices_tuple) == 0:
            raise ValueError("feed_stage_indices must contain at least one feed stage index.")
        data["n_feeds"] = len(feed_stage_indices_tuple)
        data["feed_stage_indices"] = np.asarray(feed_stage_indices_tuple, dtype=np.float64)

        super().__init__(**data)

        self._ports = UnitProcessPorts(
            (*tuple(f"feed_{index + 1}" for index in range(self.n_feeds)), "reflux_return"),
            ("distillate", "bottoms", "reflux_outlet"),
        )

    @override
    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)

        if self.n_species <= 1:
            raise ValueError("n_species must be at least 2 for stagewise distillation.")
        if self.n_feeds <= 0:
            raise ValueError("n_feeds must be positive.")
        if self.n_stages < 2:
            raise ValueError("n_stages must be at least 2.")
        if not isfinite(self.shell_diameter_m) or self.shell_diameter_m <= 0.0:
            raise ValueError("shell_diameter_m must be finite and positive.")
        if not isfinite(self.reflux_ratio) or self.reflux_ratio < 0.0:
            raise ValueError("reflux_ratio must be finite and non-negative.")
        if not isfinite(self.boilup_ratio) or self.boilup_ratio <= 0.0:
            raise ValueError("boilup_ratio must be finite and positive.")
        if not isfinite(self.pressure_relaxation_time_s) or self.pressure_relaxation_time_s <= 0.0:
            raise ValueError("pressure_relaxation_time_s must be finite and positive.")
        if (
            not isfinite(self.condenser_latent_heat_j_per_mol)
            or self.condenser_latent_heat_j_per_mol <= 0.0
        ):
            raise ValueError("condenser_latent_heat_j_per_mol must be finite and positive.")
        if (
            not isfinite(self.reboiler_latent_heat_j_per_mol)
            or self.reboiler_latent_heat_j_per_mol <= 0.0
        ):
            raise ValueError("reboiler_latent_heat_j_per_mol must be finite and positive.")

        area = pi * 0.25 * self.shell_diameter_m * self.shell_diameter_m
        per_stage_holdup = max(5.0, 90.0 * area)
        self.stage_component_moles = _coerce_1d(
            self.stage_component_moles,
            expected_size=self.n_stages * self.n_species,
            default=per_stage_holdup / float(self.n_species),
            name="stage_component_moles",
        )
        self.reflux_drum_component_moles = _coerce_1d(
            self.reflux_drum_component_moles,
            expected_size=self.n_species,
            default=max(5.0, 45.0 * area) / float(self.n_species),
            name="reflux_drum_component_moles",
        )
        self.bottoms_sump_component_moles = _coerce_1d(
            self.bottoms_sump_component_moles,
            expected_size=self.n_species,
            default=max(5.0, 45.0 * area) / float(self.n_species),
            name="bottoms_sump_component_moles",
        )
        self.feed_flows = _coerce_1d(
            self.feed_flows,
            expected_size=self.n_feeds,
            default=0.0,
            name="feed_flows",
        )
        self.feed_temperatures = _coerce_1d(
            self.feed_temperatures,
            expected_size=self.n_feeds,
            default=298.15,
            name="feed_temperatures",
        )
        self.feed_pressures = _coerce_1d(
            self.feed_pressures,
            expected_size=self.n_feeds,
            default=self.column_pressure_pa,
            name="feed_pressures",
        )
        feed_compositions_flat = _coerce_1d(
            np.asarray(self.feed_compositions, dtype=np.float64).reshape(-1),
            expected_size=self.n_feeds * self.n_species,
            default=1.0 / float(self.n_species),
            name="feed_compositions",
        )
        feed_compositions_matrix = feed_compositions_flat.reshape(self.n_feeds, self.n_species)
        for row_index in range(self.n_feeds):
            feed_compositions_matrix[row_index] = _normalize_composition(
                feed_compositions_matrix[row_index], n_species=self.n_species
            )
        self.feed_compositions = feed_compositions_matrix.reshape(-1)
        self.reflux_return_composition = _coerce_1d(
            self.reflux_return_composition,
            expected_size=self.n_species,
            default=1.0 / float(self.n_species),
            name="reflux_return_composition",
        )
        self.reflux_return_composition = _normalize_composition(
            self.reflux_return_composition,
            n_species=self.n_species,
        )

        liquid_cp_j_per_mol_k = 120.0
        reference_temperature_k = 298.15
        self.stage_internal_energy_J = _coerce_1d(
            self.stage_internal_energy_J,
            expected_size=self.n_stages,
            default=per_stage_holdup * liquid_cp_j_per_mol_k * (340.0 - reference_temperature_k),
            name="stage_internal_energy_J",
        )

        area = pi * 0.25 * self.shell_diameter_m * self.shell_diameter_m
        vapor_space_height_m = max(0.15, 0.2 * self.tray_spacing_m)
        vapor_space_volume_m3 = max(1.0e-4, area * vapor_space_height_m)
        r_gas_j_per_mol_k = 8.314462618
        nominal_holdup = max(
            1.0e-6,
            self.column_pressure_pa * vapor_space_volume_m3 / (r_gas_j_per_mol_k * 340.0),
        )
        self.top_vapor_holdup_mol = max(1.0e-6, float(self.top_vapor_holdup_mol or nominal_holdup))
        self.bottom_vapor_holdup_mol = max(
            1.0e-6, float(self.bottom_vapor_holdup_mol or nominal_holdup)
        )

        drum_total_moles = max(
            _MIN_SUM, float(np.sum(np.clip(self.reflux_drum_component_moles, 0.0, None)))
        )
        sump_total_moles = max(
            _MIN_SUM, float(np.sum(np.clip(self.bottoms_sump_component_moles, 0.0, None)))
        )
        if float(self.reflux_drum_internal_energy_J) == 0.0:
            self.reflux_drum_internal_energy_J = (
                drum_total_moles * liquid_cp_j_per_mol_k * (340.0 - reference_temperature_k)
            )
        if float(self.bottoms_sump_internal_energy_J) == 0.0:
            self.bottoms_sump_internal_energy_J = (
                sump_total_moles * liquid_cp_j_per_mol_k * (340.0 - reference_temperature_k)
            )

        self.feed_stage_indices = _coerce_1d(
            self.feed_stage_indices,
            expected_size=self.n_feeds,
            default=float(max(1, self.n_stages // 2)),
            name="feed_stage_indices",
        )
        self.feed_stage_indices = np.clip(
            np.round(self.feed_stage_indices), 1.0, float(self.n_stages)
        )

        self.relative_volatility_reference = _coerce_1d(
            self.relative_volatility_reference,
            expected_size=self.n_species,
            default=1.0,
            name="relative_volatility_reference",
        )
        if np.allclose(self.relative_volatility_reference, np.ones(self.n_species), atol=1.0e-12):
            alpha = np.linspace(1.6, 0.7, self.n_species, dtype=np.float64)
            alpha = np.clip(alpha, 0.2, None)
            alpha[-1] = 1.0
            self.relative_volatility_reference = alpha

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
        self.reflux_outlet_composition = _coerce_1d(
            self.reflux_outlet_composition,
            expected_size=self.n_species,
            default=1.0 / float(self.n_species),
            name="reflux_outlet_composition",
        )

        self._runtime_distillate_withdrawal_demand_latched = False
        self._runtime_bottoms_withdrawal_demand_latched = False
        self._runtime_distillate_withdrawal_demand_mol_s = 0.0
        self._runtime_bottoms_withdrawal_demand_mol_s = 0.0

    @property
    def ports(self) -> UnitProcessPorts:
        return self._ports

    @property
    @override
    def hydraulic_participation(self) -> HydraulicParticipationSpec:
        ports: dict[str, HydraulicPortSpec] = {
            "distillate": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef(state="column_pressure_pa"),
            ),
            "bottoms": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef(state="column_pressure_pa"),
            ),
            "reflux_return": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef(state="column_pressure_pa"),
            ),
            "reflux_outlet": HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef(state="column_pressure_pa"),
            ),
        }
        for feed_index in range(self.n_feeds):
            ports[f"feed_{feed_index + 1}"] = HydraulicPortSpec(
                role="pressure_state",
                pressure_state=HydraulicScalarStateRef(state="column_pressure_pa"),
            )

        return HydraulicParticipationSpec(
            ports=ports,
            balancing_groups=(
                HydraulicBalancingGroupSpec(
                    name="stagewise_distillation_flow_balance",
                    ports=(*self.ports.inlets, *self.ports.outlets),
                ),
            ),
            relations=(
                HydraulicRelationSpec(
                    name="shared_product_pressure",
                    kind="pressure_equal",
                    ports=("distillate", "bottoms", "reflux_outlet"),
                ),
            ),
        )

    def _feed_compositions_matrix(self) -> NDArray[np.float64]:
        return np.asarray(self.feed_compositions, dtype=np.float64).reshape(
            self.n_feeds, self.n_species
        )

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        if port_name not in self.ports.inlets:
            valid_ports = ", ".join(self.ports.inlets)
            raise ValueError(
                f"Invalid inlet port '{port_name}' for {type(self).__name__}. Valid inlet ports: {valid_ports}."
            )

        if port_name == "reflux_return":
            self.reflux_return_flow = max(0.0, float(stream.molar_flow_rate))
            self.reflux_return_temperature = float(stream.temperature)
            self.reflux_return_pressure = float(stream.pressure)
            self.reflux_return_composition = _normalize_composition(
                np.asarray(stream.mole_fractions, dtype=np.float64), n_species=self.n_species
            )
            return

        feed_index = int(port_name.split("_")[-1]) - 1
        self.feed_flows[feed_index] = max(0.0, float(stream.molar_flow_rate))
        self.feed_temperatures[feed_index] = float(stream.temperature)
        self.feed_pressures[feed_index] = float(stream.pressure)
        feed_matrix = self._feed_compositions_matrix()
        feed_matrix[feed_index] = _normalize_composition(
            np.asarray(stream.mole_fractions, dtype=np.float64), n_species=self.n_species
        )
        self.feed_compositions = feed_matrix.reshape(-1)

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
        return StreamData(
            temperature=float(getattr(self, port_map.temperature)),
            pressure=float(self.column_pressure_pa),
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
            self._runtime_distillate_withdrawal_demand_latched = True
            self._runtime_distillate_withdrawal_demand_mol_s = demand
            return
        if port_name == "bottoms":
            self._runtime_bottoms_withdrawal_demand_latched = True
            self._runtime_bottoms_withdrawal_demand_mol_s = demand
            return
        # reflux_outlet demand is accepted for runtime compatibility, but the
        # reflux path remains internally solved from condensation minus
        # distillate withdrawal in this monolithic closure.

    @override
    def step(self, dt: Seconds) -> None:
        dt_s = max(float(dt), _MIN_STEP_SECONDS)
        distillate_request = (
            self._runtime_distillate_withdrawal_demand_mol_s
            if self._runtime_distillate_withdrawal_demand_latched
            else max(0.0, float(self.distillate_withdrawal_flow))
        )
        bottoms_request = (
            self._runtime_bottoms_withdrawal_demand_mol_s
            if self._runtime_bottoms_withdrawal_demand_latched
            else max(0.0, float(self.bottoms_withdrawal_flow))
        )

        drum_moles = np.asarray(self.reflux_drum_component_moles, dtype=np.float64)
        sump_moles = np.asarray(self.bottoms_sump_component_moles, dtype=np.float64)

        distillate_at_macro = _realized_withdrawal_flow(
            requested_flow=distillate_request,
            owner_moles=drum_moles,
            dt_s=dt_s,
        )
        bottoms_at_macro = _realized_withdrawal_flow(
            requested_flow=bottoms_request,
            owner_moles=sump_moles,
            dt_s=dt_s,
        )

        distillate_mismatch = distillate_request > distillate_at_macro + 1.0e-12
        bottoms_mismatch = bottoms_request > bottoms_at_macro + 1.0e-12

        original_distillate = float(self.distillate_withdrawal_flow)
        original_bottoms = float(self.bottoms_withdrawal_flow)

        realized_distillate_flow = distillate_at_macro
        realized_bottoms_flow = bottoms_at_macro

        if distillate_mismatch or bottoms_mismatch:
            # GE-PW-3 step 2: bounded internal substep refinement before
            # fallback cap.  Subdividing allows internal state (condensation,
            # feed, boilup) to replenish owner regions between substeps so
            # that progressive withdrawal may satisfy more of the demand than
            # a single conservative macro-step cap.
            n_sub = min(
                _MAX_REFINEMENT_SUBDIVISIONS,
                max(1, int(round(dt_s / _MIN_REFINEMENT_SUBSTEP_S))),
            )
            sub_dt = dt_s / float(n_sub)
            total_distillate_withdrawn = 0.0
            total_bottoms_withdrawn = 0.0

            for _ in range(n_sub):
                current_drum = np.asarray(self.reflux_drum_component_moles, dtype=np.float64)
                current_sump = np.asarray(self.bottoms_sump_component_moles, dtype=np.float64)

                sub_distillate_flow = _realized_withdrawal_flow(
                    requested_flow=distillate_request,
                    owner_moles=current_drum,
                    dt_s=sub_dt,
                )
                sub_bottoms_flow = _realized_withdrawal_flow(
                    requested_flow=bottoms_request,
                    owner_moles=current_sump,
                    dt_s=sub_dt,
                )
                self.distillate_withdrawal_flow = sub_distillate_flow
                self.bottoms_withdrawal_flow = sub_bottoms_flow

                super().step(float(sub_dt))

                # Capture what the model actually realized for this substep
                # after all internal algebraic/differential constraints.
                total_distillate_withdrawn += max(0.0, float(self.distillate_flow)) * sub_dt
                total_bottoms_withdrawn += max(0.0, float(self.bottoms_flow)) * sub_dt

            realized_distillate_flow = total_distillate_withdrawn / dt_s
            realized_bottoms_flow = total_bottoms_withdrawn / dt_s
        else:
            self.distillate_withdrawal_flow = distillate_at_macro
            self.bottoms_withdrawal_flow = bottoms_at_macro

            super().step(float(dt))

            realized_distillate_flow = max(0.0, float(self.distillate_flow))
            realized_bottoms_flow = max(0.0, float(self.bottoms_flow))

        # Report macro-step realized through-flow so runtime observability and
        # line-side coupling evidence cannot mistake substep-local transients
        # for a fully satisfied accepted-step demand.
        self.distillate_flow = max(0.0, float(realized_distillate_flow))
        self.bottoms_flow = max(0.0, float(realized_bottoms_flow))

        self.distillate_withdrawal_flow = original_distillate
        self.bottoms_withdrawal_flow = original_bottoms

        self._runtime_distillate_withdrawal_demand_latched = False
        self._runtime_bottoms_withdrawal_demand_latched = False
        self._runtime_distillate_withdrawal_demand_mol_s = 0.0
        self._runtime_bottoms_withdrawal_demand_mol_s = 0.0

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
        n_stages = int(round(float(k[k_map["n_stages"]])))

        stage_moles = np.asarray(y[y_map["stage_component_moles"]], dtype=np.float64).reshape(
            n_stages, n_species
        )
        stage_internal_energy = np.asarray(
            y[y_map["stage_internal_energy_J"]], dtype=np.float64
        ).reshape(n_stages)
        top_vapor_holdup = max(1.0e-9, float(y[y_map["top_vapor_holdup_mol"]]))
        bottom_vapor_holdup = max(1.0e-9, float(y[y_map["bottom_vapor_holdup_mol"]]))
        drum_moles = np.asarray(y[y_map["reflux_drum_component_moles"]], dtype=np.float64).reshape(
            -1
        )
        sump_moles = np.asarray(y[y_map["bottoms_sump_component_moles"]], dtype=np.float64).reshape(
            -1
        )
        drum_energy = float(y[y_map["reflux_drum_internal_energy_J"]])
        sump_energy = float(y[y_map["bottoms_sump_internal_energy_J"]])

        alpha = np.asarray(k[k_map["relative_volatility_reference"]], dtype=np.float64).reshape(-1)
        if alpha.size != n_species:
            raise ValueError("relative_volatility_reference length mismatch.")

        drum_x = _owner_fraction_from_moles(drum_moles, n_species=n_species)
        sump_x = _owner_fraction_from_moles(sump_moles, n_species=n_species)

        vapor_flow = max(0.0, float(k[k_map["stage_vapor_flow_mol_s"]]))

        liquid_density_kg_m3 = 750.0
        liquid_mw_kg_mol = 0.08
        weir_height_m = 0.005
        liquid_hydraulic_coeff = 10000.0
        area_active_m2 = pi * 0.25 * max(1.0e-9, float(k[k_map["shell_diameter_m"]])) ** 2
        stage_total_moles = np.sum(np.clip(stage_moles, 0.0, None), axis=1)
        stage_liquid_volume = (
            stage_total_moles * liquid_mw_kg_mol / max(liquid_density_kg_m3, 1.0e-9)
        )
        stage_liquid_head = stage_liquid_volume / max(area_active_m2, 1.0e-9)
        stage_liquid_flow = liquid_hydraulic_coeff * np.power(
            np.clip(stage_liquid_head - weir_height_m, 0.0, None), 1.5
        )
        representative_liquid_flow = (
            float(np.mean(stage_liquid_flow)) if stage_liquid_flow.size else 0.0
        )

        shell_diameter_m = max(1.0e-9, float(k[k_map["shell_diameter_m"]]))
        area = pi * 0.25 * shell_diameter_m * shell_diameter_m
        vapor_space_height_m = max(0.15, 0.2 * float(k[k_map["tray_spacing_m"]]))
        vapor_volume_m3 = max(1.0e-4, area * vapor_space_height_m)
        r_gas_j_per_mol_k = 8.314462618
        liquid_cp_j_per_mol_k = 120.0
        reference_temperature_k = 298.15
        stage_safe_moles = np.clip(np.sum(np.clip(stage_moles, 0.0, None), axis=1), _MIN_SUM, None)
        stage_temperature = np.clip(
            reference_temperature_k
            + stage_internal_energy / (stage_safe_moles * liquid_cp_j_per_mol_k),
            250.0,
            700.0,
        )
        drum_total = max(_MIN_SUM, float(np.sum(np.clip(drum_moles, 0.0, None))))
        sump_total = max(_MIN_SUM, float(np.sum(np.clip(sump_moles, 0.0, None))))
        drum_temperature = float(
            np.clip(
                reference_temperature_k + drum_energy / (drum_total * liquid_cp_j_per_mol_k),
                250.0,
                700.0,
            )
        )
        sump_temperature = float(
            np.clip(
                reference_temperature_k + sump_energy / (sump_total * liquid_cp_j_per_mol_k),
                250.0,
                700.0,
            )
        )
        p_top = r_gas_j_per_mol_k * drum_temperature * top_vapor_holdup / vapor_volume_m3
        p_bottom = r_gas_j_per_mol_k * sump_temperature * bottom_vapor_holdup / vapor_volume_m3
        stage_pressure = np.linspace(p_top, p_bottom, n_stages, dtype=np.float64)
        if n_stages > 1:
            delta_p_links = np.clip(stage_pressure[1:] - stage_pressure[:-1], 0.0, None)
            rho_vapor = np.clip(
                stage_pressure[:-1] * 0.08 / (r_gas_j_per_mol_k * stage_temperature[:-1]),
                0.2,
                5.0,
            )
            dry_loss_pa = 5.0
            delta_p_head = liquid_density_kg_m3 * 9.81 * stage_liquid_head[:-1]
            delta_p_available = np.clip(delta_p_links - dry_loss_pa - delta_p_head, 0.0, None)
            vapor_capacity_coeff = 5.0
            vapor_internal_flow = vapor_capacity_coeff * np.sqrt(
                delta_p_available / np.clip(rho_vapor, 1.0e-9, None)
            )
            representative_vapor_flow = float(np.mean(vapor_internal_flow))
        else:
            representative_vapor_flow = vapor_flow
        reference_area = pi * 0.25
        capacity_factor = max(1.0e-6, area / reference_area)
        dynamic_vapor_capacity = (
            representative_vapor_flow if representative_vapor_flow > 1.0e-9 else vapor_flow
        )
        maximum_vapor_capacity_flow = max(
            0.0, min(vapor_flow, dynamic_vapor_capacity) * capacity_factor
        )
        maximum_liquid_capacity_flow = max(0.0, representative_liquid_flow * capacity_factor)
        condenser_duty_request_w = float(u[u_map["condenser_duty_request_W"]])
        reboiler_duty_request_w = float(u[u_map["reboiler_duty_request_W"]])
        condenser_latent = float(k[k_map["condenser_latent_heat_j_per_mol"]])
        reboiler_latent = float(k[k_map["reboiler_latent_heat_j_per_mol"]])

        top_vapor_release_tau_s = 2.0
        top_vapor_release_capacity = top_vapor_holdup / top_vapor_release_tau_s
        top_vapor_supply = min(
            maximum_vapor_capacity_flow,
            max(top_vapor_release_capacity, representative_vapor_flow, 0.2 * vapor_flow),
        )
        if condenser_duty_request_w < 0.0:
            thermal_condensation_drive = np.clip(
                (stage_temperature[0] - drum_temperature) / 30.0,
                0.0,
                1.0,
            )
            pressure_condensation_drive = np.clip(
                np.log(np.clip(p_top, 1.0e3, None) / 101325.0) + 0.5,
                0.0,
                1.0,
            )
            condenser_duty_drive = np.clip(
                -condenser_duty_request_w
                / max(condenser_latent * max(top_vapor_supply, 1.0e-9), 1.0e-9),
                0.0,
                1.0,
            )
            condensation_drive = np.clip(
                0.55 * condenser_duty_drive
                + 0.25 * thermal_condensation_drive
                + 0.20 * pressure_condensation_drive,
                0.0,
                1.0,
            )
            realized_condensed_flow = top_vapor_supply * condensation_drive
        else:
            realized_condensed_flow = 0.0
        condenser_duty_w = -realized_condensed_flow * condenser_latent

        rho_liq_sump = np.clip(
            690.0 + 0.25 * (sump_temperature - reference_temperature_k), 550.0, 900.0
        )
        duty_density_factor = np.clip(
            max(0.0, reboiler_duty_request_w)
            / max(reboiler_latent * max(maximum_vapor_capacity_flow, 1.0e-9), 1.0e-9),
            0.0,
            1.0,
        )
        rho_downcomer = rho_liq_sump
        rho_riser = np.clip(rho_liq_sump * (1.0 - 0.55 * duty_density_factor), 120.0, rho_liq_sump)
        loop_static_head_m = max(0.3, 0.15 * float(k[k_map["active_contact_height_m"]]))
        delta_p_drive = max((rho_downcomer - rho_riser) * 9.81 * loop_static_head_m, 0.0)
        circulation_capacity_coeff = 80.0
        circulation_flow = circulation_capacity_coeff * np.sqrt(
            delta_p_drive / max(rho_liq_sump, 1.0e-9)
        )
        support_available_mol = max(0.0, float(np.sum(np.clip(sump_moles, 0.0, None))))
        bottom_vapor_capacity = min(
            circulation_flow, maximum_vapor_capacity_flow, support_available_mol
        )
        if reboiler_duty_request_w > 0.0:
            q_per_circulation_mol = reboiler_duty_request_w / max(circulation_flow, 1.0e-9)
            thermal_boilup_drive = np.clip(
                q_per_circulation_mol / max(3.0 * reboiler_latent, 1.0e-9),
                0.0,
                1.0,
            )
            pressure_boilup_drive = np.clip(
                np.log(101325.0 / np.clip(p_bottom, 1.0e3, None)) + 0.5,
                0.0,
                1.0,
            )
            volatility_drive = np.clip(
                float(np.dot(sump_x, np.clip(alpha / max(np.max(alpha), 1.0), 0.0, 1.0))),
                0.0,
                1.0,
            )
            beta_boilup = np.clip(
                thermal_boilup_drive
                * (0.75 + 0.25 * pressure_boilup_drive)
                * (0.85 + 0.15 * volatility_drive),
                0.0,
                1.0,
            )
            realized_reboiler_boilup_flow = min(
                beta_boilup * circulation_flow, bottom_vapor_capacity
            )
        else:
            realized_reboiler_boilup_flow = 0.0
        reboiler_duty_w = realized_reboiler_boilup_flow * reboiler_latent
        distillate_withdrawal_request = max(0.0, float(u[u_map["distillate_withdrawal_flow"]]))
        bottoms_withdrawal_request = max(0.0, float(u[u_map["bottoms_withdrawal_flow"]]))

        distillate_flow = _realized_withdrawal_flow(
            requested_flow=distillate_withdrawal_request,
            owner_moles=drum_moles,
        )
        reflux_nominal_flow = max(0.0, realized_condensed_flow - distillate_flow)
        reflux_outlet_flow = min(
            _realized_withdrawal_flow(
                requested_flow=reflux_nominal_flow,
                owner_moles=drum_moles,
            ),
            maximum_liquid_capacity_flow,
        )
        bottoms_flow = _realized_withdrawal_flow(
            requested_flow=bottoms_withdrawal_request,
            owner_moles=sump_moles,
        )

        feed_flows = np.asarray(u[u_map["feed_flows"]], dtype=np.float64).reshape(n_feeds)
        feed_temperatures = np.asarray(u[u_map["feed_temperatures"]], dtype=np.float64).reshape(
            n_feeds
        )
        total_feed = float(np.sum(np.clip(feed_flows, 0.0, None)))
        if total_feed <= _MIN_SUM:
            mixed_feed_temperature = 298.15
        else:
            mixed_feed_temperature = float(
                np.dot(np.clip(feed_flows, 0.0, None), feed_temperatures) / total_feed
            )

        distillate_temperature = drum_temperature
        bottoms_temperature = sump_temperature
        reflux_temperature = float(np.clip(stage_temperature[0], 250.0, 700.0))

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["distillate_flow"]] = max(0.0, distillate_flow)
        result[algebraic_map["bottoms_flow"]] = max(0.0, bottoms_flow)
        result[algebraic_map["distillate_composition"]] = drum_x
        result[algebraic_map["bottoms_composition"]] = sump_x
        result[algebraic_map["distillate_temperature"]] = distillate_temperature
        result[algebraic_map["bottoms_temperature"]] = bottoms_temperature
        result[algebraic_map["reflux_outlet_flow"]] = reflux_outlet_flow
        result[algebraic_map["reflux_outlet_temperature"]] = reflux_temperature
        result[algebraic_map["reflux_outlet_composition"]] = drum_x
        result[algebraic_map["condenser_duty_W"]] = condenser_duty_w
        result[algebraic_map["reboiler_duty_W"]] = reboiler_duty_w
        result[algebraic_map["realized_condensed_flow_mol_s"]] = realized_condensed_flow
        result[algebraic_map["realized_reboiler_boilup_flow_mol_s"]] = realized_reboiler_boilup_flow
        result[algebraic_map["maximum_vapor_capacity_flow_mol_s"]] = maximum_vapor_capacity_flow
        result[algebraic_map["maximum_liquid_capacity_flow_mol_s"]] = maximum_liquid_capacity_flow
        result[algebraic_map["representative_internal_liquid_traffic_mol_s"]] = (
            representative_liquid_flow
        )
        result[algebraic_map["representative_internal_vapor_traffic_mol_s"]] = (
            representative_vapor_flow
        )
        result[algebraic_map["column_pressure_pa"]] = 0.5 * (p_top + p_bottom)
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
        n_stages = int(round(float(k[k_map["n_stages"]])))

        stage_moles = np.asarray(y[y_map["stage_component_moles"]], dtype=np.float64).reshape(
            n_stages, n_species
        )
        stage_internal_energy = np.asarray(
            y[y_map["stage_internal_energy_J"]], dtype=np.float64
        ).reshape(n_stages)
        drum_moles = np.asarray(y[y_map["reflux_drum_component_moles"]], dtype=np.float64).reshape(
            -1
        )
        sump_moles = np.asarray(y[y_map["bottoms_sump_component_moles"]], dtype=np.float64).reshape(
            -1
        )
        drum_internal_energy = float(y[y_map["reflux_drum_internal_energy_J"]])
        sump_internal_energy = float(y[y_map["bottoms_sump_internal_energy_J"]])
        top_vapor_holdup = max(1.0e-9, float(y[y_map["top_vapor_holdup_mol"]]))
        bottom_vapor_holdup = max(1.0e-9, float(y[y_map["bottom_vapor_holdup_mol"]]))

        feed_flows = np.clip(
            np.asarray(u[u_map["feed_flows"]], dtype=np.float64).reshape(n_feeds), 0.0, None
        )
        feed_compositions = np.asarray(u[u_map["feed_compositions"]], dtype=np.float64).reshape(
            n_feeds, n_species
        )
        feed_stage_indices = np.asarray(k[k_map["feed_stage_indices"]], dtype=np.float64).reshape(
            n_feeds
        )

        alpha = np.asarray(k[k_map["relative_volatility_reference"]], dtype=np.float64).reshape(-1)
        effective_alpha = np.clip(alpha, 0.1, 10.0)

        vapor_flow = max(0.0, float(k[k_map["stage_vapor_flow_mol_s"]]))
        reflux_return_flow = max(0.0, float(u[u_map["reflux_return_flow"]]))
        reflux_return_composition = _safe_fraction_from_moles(
            np.asarray(u[u_map["reflux_return_composition"]], dtype=np.float64).reshape(-1),
            n_species=n_species,
        )

        x_stage = np.vstack(
            [
                _safe_fraction_from_moles(stage_moles[stage_index], n_species=n_species)
                for stage_index in range(n_stages)
            ]
        )
        x_drum = _owner_fraction_from_moles(drum_moles, n_species=n_species)
        x_sump = _owner_fraction_from_moles(sump_moles, n_species=n_species)

        condenser_flow = max(0.0, float(algebraic[algebraic_map["realized_condensed_flow_mol_s"]]))
        distillate_flow = float(algebraic[algebraic_map["distillate_flow"]])
        bottoms_flow = float(algebraic[algebraic_map["bottoms_flow"]])
        reflux_flow = max(0.0, float(algebraic[algebraic_map["reflux_outlet_flow"]]))
        reboiler_vapor_flow = max(
            0.0, float(algebraic[algebraic_map["realized_reboiler_boilup_flow_mol_s"]])
        )

        liquid_density_kg_m3 = 750.0
        liquid_mw_kg_mol = 0.08
        weir_height_m = 0.005
        liquid_hydraulic_coeff = 10000.0
        area_active_m2 = pi * 0.25 * max(1.0e-9, float(k[k_map["shell_diameter_m"]])) ** 2
        stage_total_moles = np.sum(np.clip(stage_moles, 0.0, None), axis=1)
        stage_liquid_volume = (
            stage_total_moles * liquid_mw_kg_mol / max(liquid_density_kg_m3, 1.0e-9)
        )
        stage_liquid_head = stage_liquid_volume / max(area_active_m2, 1.0e-9)
        stage_liquid_flow = liquid_hydraulic_coeff * np.power(
            np.clip(stage_liquid_head - weir_height_m, 0.0, None), 1.5
        )

        feed_to_stage = np.zeros((n_stages, n_species), dtype=np.float64)
        for feed_index in range(n_feeds):
            stage_index = int(
                np.clip(round(float(feed_stage_indices[feed_index])) - 1, 0, n_stages - 1)
            )
            z = _safe_fraction_from_moles(feed_compositions[feed_index], n_species=n_species)
            feed_to_stage[stage_index] += feed_flows[feed_index] * z

        liquid_cp_j_per_mol_k = 120.0
        reference_temperature_k = 298.15
        stage_safe_moles = np.clip(stage_total_moles, _MIN_SUM, None)
        stage_temperature = np.clip(
            reference_temperature_k
            + stage_internal_energy / (stage_safe_moles * liquid_cp_j_per_mol_k),
            250.0,
            700.0,
        )
        drum_total = max(_MIN_SUM, float(np.sum(np.clip(drum_moles, 0.0, None))))
        sump_total = max(_MIN_SUM, float(np.sum(np.clip(sump_moles, 0.0, None))))
        drum_temperature = float(
            np.clip(
                reference_temperature_k
                + drum_internal_energy / (drum_total * liquid_cp_j_per_mol_k),
                250.0,
                700.0,
            )
        )
        sump_temperature = float(
            np.clip(
                reference_temperature_k
                + sump_internal_energy / (sump_total * liquid_cp_j_per_mol_k),
                250.0,
                700.0,
            )
        )
        shell_diameter_m = max(1.0e-9, float(k[k_map["shell_diameter_m"]]))
        area = pi * 0.25 * shell_diameter_m * shell_diameter_m
        vapor_space_height_m = max(0.15, 0.2 * float(k[k_map["tray_spacing_m"]]))
        vapor_volume_m3 = max(1.0e-4, area * vapor_space_height_m)
        r_gas_j_per_mol_k = 8.314462618
        p_top = r_gas_j_per_mol_k * drum_temperature * top_vapor_holdup / vapor_volume_m3
        p_bottom = r_gas_j_per_mol_k * sump_temperature * bottom_vapor_holdup / vapor_volume_m3
        stage_pressure = np.linspace(p_top, p_bottom, n_stages, dtype=np.float64)
        temp_sensitivity = np.linspace(450.0, 250.0, n_species, dtype=np.float64)
        pressure_sensitivity = np.linspace(0.18, 0.06, n_species, dtype=np.float64)
        inv_t_shift = (1.0 / stage_temperature[:, None]) - (1.0 / 340.0)
        log_p_shift_stage = np.log(np.clip(stage_pressure[:, None], 1.0e3, None) / 101325.0)
        k_stage = np.clip(
            effective_alpha[None, :]
            * np.exp(
                temp_sensitivity[None, :] * inv_t_shift
                - pressure_sensitivity[None, :] * log_p_shift_stage
            ),
            0.05,
            50.0,
        )
        y_stage = np.vstack(
            [
                _safe_fraction_from_moles(
                    k_stage[stage_index] * x_stage[stage_index], n_species=n_species
                )
                for stage_index in range(n_stages)
            ]
        )
        k_top = np.clip(
            effective_alpha
            * np.exp(
                temp_sensitivity * ((1.0 / drum_temperature) - (1.0 / 340.0))
                - pressure_sensitivity * np.log(np.clip(p_top, 1.0e3, None) / 101325.0)
            ),
            0.05,
            50.0,
        )
        top_contact_factor = 1.0 - np.exp(-0.2 * float(n_stages))
        k_top = 1.0 + top_contact_factor * (k_top - 1.0)
        y_top_equilibrium = _safe_fraction_from_moles(k_top * x_stage[0], n_species=n_species)
        k_bottom = np.clip(
            effective_alpha
            * np.exp(
                temp_sensitivity * ((1.0 / sump_temperature) - (1.0 / 340.0))
                - pressure_sensitivity * np.log(np.clip(p_bottom, 1.0e3, None) / 101325.0)
            ),
            0.05,
            50.0,
        )
        y_reboiler = _safe_fraction_from_moles(k_bottom * x_sump, n_species=n_species)

        cp_liq_species = np.linspace(95.0, 145.0, n_species, dtype=np.float64)
        cp_vap_species = np.linspace(60.0, 95.0, n_species, dtype=np.float64)
        latent_species = np.linspace(26000.0, 34000.0, n_species, dtype=np.float64)
        h_liq_stage = np.sum(x_stage * cp_liq_species[None, :], axis=1) * (
            stage_temperature - reference_temperature_k
        )
        h_vap_stage = np.sum(y_stage * cp_vap_species[None, :], axis=1) * (
            stage_temperature - reference_temperature_k
        ) + np.sum(y_stage * latent_species[None, :], axis=1)
        h_liq_drum = float(
            np.dot(x_drum, cp_liq_species) * (drum_temperature - reference_temperature_k)
        )
        h_liq_sump = float(
            np.dot(x_sump, cp_liq_species) * (sump_temperature - reference_temperature_k)
        )
        h_vap_top = float(
            np.dot(y_top_equilibrium, cp_vap_species)
            * (stage_temperature[0] - reference_temperature_k)
            + np.dot(y_top_equilibrium, latent_species)
        )
        h_vap_boilup = float(
            np.dot(y_reboiler, cp_vap_species) * (sump_temperature - reference_temperature_k)
            + np.dot(y_reboiler, latent_species)
        )

        stage_feed_energy_in = np.zeros(n_stages, dtype=np.float64)
        feed_temperatures = np.asarray(u[u_map["feed_temperatures"]], dtype=np.float64).reshape(
            n_feeds
        )
        for feed_index in range(n_feeds):
            stage_index = int(
                np.clip(round(float(feed_stage_indices[feed_index])) - 1, 0, n_stages - 1)
            )
            feed_flow = float(feed_flows[feed_index])
            if feed_flow <= 0.0:
                continue
            feed_z = _safe_fraction_from_moles(feed_compositions[feed_index], n_species=n_species)
            h_feed = float(
                np.dot(feed_z, cp_liq_species)
                * (float(feed_temperatures[feed_index]) - reference_temperature_k)
            )
            stage_feed_energy_in[stage_index] += feed_flow * h_feed

        if n_stages > 1:
            delta_p_links = np.clip(stage_pressure[1:] - stage_pressure[:-1], 0.0, None)
            rho_vapor = np.clip(
                stage_pressure[:-1] * 0.08 / (r_gas_j_per_mol_k * stage_temperature[:-1]),
                0.2,
                5.0,
            )
            dry_loss_pa = 5.0
            delta_p_head = liquid_density_kg_m3 * 9.81 * stage_liquid_head[:-1]
            delta_p_available = np.clip(delta_p_links - dry_loss_pa - delta_p_head, 0.0, None)
            vapor_capacity_coeff = 5.0
            vapor_internal_flow = vapor_capacity_coeff * np.sqrt(
                delta_p_available / np.clip(rho_vapor, 1.0e-9, None)
            )
        else:
            vapor_internal_flow = np.zeros(0, dtype=np.float64)
        vapor_internal_flow = np.clip(vapor_internal_flow, 0.0, vapor_flow)

        d_stage_energy = np.zeros(n_stages, dtype=np.float64)
        for stage_index in range(n_stages):
            liquid_in_energy = (
                reflux_flow * h_liq_drum
                if stage_index == 0
                else stage_liquid_flow[stage_index - 1] * h_liq_stage[stage_index - 1]
            )
            liquid_out_energy = stage_liquid_flow[stage_index] * h_liq_stage[stage_index]
            vapor_in_energy = (
                reboiler_vapor_flow * h_vap_boilup
                if stage_index == n_stages - 1
                else vapor_internal_flow[stage_index] * h_vap_stage[stage_index + 1]
            )
            vapor_out_energy = (
                condenser_flow * h_vap_top
                if stage_index == 0
                else vapor_internal_flow[stage_index - 1] * h_vap_stage[stage_index]
            )
            d_stage_energy[stage_index] = (
                stage_feed_energy_in[stage_index]
                + liquid_in_energy
                + vapor_in_energy
                - liquid_out_energy
                - vapor_out_energy
            )

        condenser_heat_removal_w = max(0.0, -float(algebraic[algebraic_map["condenser_duty_W"]]))
        d_drum_energy = (
            condenser_flow * h_vap_top
            - condenser_heat_removal_w
            + reflux_return_flow
            * float(
                np.dot(reflux_return_composition, cp_liq_species)
                * (float(u[u_map["reflux_return_temperature"]]) - reference_temperature_k)
            )
            - distillate_flow * h_liq_drum
            - reflux_flow * h_liq_drum
        )
        d_sump_energy = (
            stage_liquid_flow[-1] * h_liq_stage[-1]
            + float(algebraic[algebraic_map["reboiler_duty_W"]])
            - reboiler_vapor_flow * h_vap_boilup
            - bottoms_flow * h_liq_sump
        )

        d_top_vapor = condenser_flow - (vapor_internal_flow[0] if vapor_internal_flow.size else 0.0)
        d_bottom_vapor = reboiler_vapor_flow - (
            vapor_internal_flow[-1] if vapor_internal_flow.size else 0.0
        )

        d_t_top = d_drum_energy / max(drum_total * liquid_cp_j_per_mol_k, _MIN_SUM)
        d_t_bottom = d_sump_energy / max(sump_total * liquid_cp_j_per_mol_k, _MIN_SUM)
        d_p_top = (
            r_gas_j_per_mol_k
            / vapor_volume_m3
            * (drum_temperature * d_top_vapor + top_vapor_holdup * d_t_top)
        )
        d_p_bottom = (
            r_gas_j_per_mol_k
            / vapor_volume_m3
            * (sump_temperature * d_bottom_vapor + bottom_vapor_holdup * d_t_bottom)
        )
        d_stage = np.zeros_like(stage_moles)
        for stage_index in range(n_stages):
            liquid_in = (
                reflux_flow * x_drum
                if stage_index == 0
                else stage_liquid_flow[stage_index - 1] * x_stage[stage_index - 1]
            )
            liquid_out = stage_liquid_flow[stage_index] * x_stage[stage_index]

            vapor_in = (
                reboiler_vapor_flow * y_reboiler
                if stage_index == n_stages - 1
                else vapor_internal_flow[stage_index] * y_stage[stage_index + 1]
            )
            vapor_out = (
                condenser_flow * y_top_equilibrium
                if stage_index == 0
                else vapor_internal_flow[stage_index - 1] * y_stage[stage_index]
            )

            d_stage[stage_index] = (
                feed_to_stage[stage_index] + liquid_in + vapor_in - liquid_out - vapor_out
            )

        d_drum = (
            condenser_flow * y_top_equilibrium
            + reflux_return_flow * reflux_return_composition
            - reflux_flow * x_drum
            - distillate_flow * x_drum
        )
        d_sump = (
            stage_liquid_flow[-1] * x_stage[-1]
            - reboiler_vapor_flow * y_reboiler
            - bottoms_flow * x_sump
        )

        dy = np.zeros_like(y)
        dy[y_map["stage_component_moles"]] = d_stage.reshape(-1)
        dy[y_map["reflux_drum_component_moles"]] = d_drum
        dy[y_map["bottoms_sump_component_moles"]] = d_sump
        dy[y_map["stage_internal_energy_J"]] = d_stage_energy
        dy[y_map["reflux_drum_internal_energy_J"]] = d_drum_energy
        dy[y_map["bottoms_sump_internal_energy_J"]] = d_sump_energy
        dy[y_map["top_vapor_holdup_mol"]] = d_top_vapor
        dy[y_map["bottom_vapor_holdup_mol"]] = d_bottom_vapor
        return dy


__all__ = ["StagewiseDistillationColumn"]
