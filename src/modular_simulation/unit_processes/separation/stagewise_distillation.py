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
from modular_simulation.utils.typing import ArrayIndex

_COMPOSITION_TOL = 1.0e-8
_MIN_SUM = 1.0e-12


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


def _realized_withdrawal_flow(*, requested_flow: float, owner_moles: NDArray[np.float64]) -> float:
    bounded_request = max(0.0, float(requested_flow))
    owner_total = float(
        np.sum(np.clip(np.asarray(owner_moles, dtype=np.float64).reshape(-1), 0.0, None))
    )
    if owner_total <= _MIN_SUM:
        return 0.0
    return min(bounded_request, owner_total)


def _realized_phase_change_flow_from_duty(
    *,
    duty_request_w: float,
    latent_heat_j_per_mol: float,
    fallback_flow_mol_s: float,
    inventory_limit_mol_s: float,
    expects_negative_duty: bool,
) -> tuple[float, float]:
    inventory_limit = max(0.0, float(inventory_limit_mol_s))
    latent = max(1.0e-9, float(latent_heat_j_per_mol))
    request = float(duty_request_w)

    if expects_negative_duty:
        if request < 0.0:
            requested_flow = max(0.0, -request / latent)
        else:
            requested_flow = 0.0
    else:
        if request > 0.0:
            requested_flow = max(0.0, request / latent)
        else:
            requested_flow = 0.0

    realized_flow = min(requested_flow, inventory_limit)
    realized_duty = (-realized_flow if expects_negative_duty else realized_flow) * latent
    return realized_duty, realized_flow


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
            type=T.DIFFERENTIAL,
            unit="Pa",
            description="shared dynamic pressure state for stages and product ports",
        ),
    ] = 101325.0

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
        drum_moles = np.asarray(y[y_map["reflux_drum_component_moles"]], dtype=np.float64).reshape(
            -1
        )
        sump_moles = np.asarray(y[y_map["bottoms_sump_component_moles"]], dtype=np.float64).reshape(
            -1
        )

        alpha = np.asarray(k[k_map["relative_volatility_reference"]], dtype=np.float64).reshape(-1)
        if alpha.size != n_species:
            raise ValueError("relative_volatility_reference length mismatch.")

        effective_alpha = np.clip(alpha, 0.1, 10.0)

        drum_x = _owner_fraction_from_moles(drum_moles, n_species=n_species)
        sump_x = _owner_fraction_from_moles(sump_moles, n_species=n_species)

        top_x = _safe_fraction_from_moles(stage_moles[0], n_species=n_species)
        y_top = _safe_fraction_from_moles(effective_alpha * top_x, n_species=n_species)

        vapor_flow = max(0.0, float(k[k_map["stage_vapor_flow_mol_s"]]))
        liquid_flow = max(0.0, float(k[k_map["stage_liquid_flow_mol_s"]]))
        shell_diameter_m = max(1.0e-9, float(k[k_map["shell_diameter_m"]]))
        area = pi * 0.25 * shell_diameter_m * shell_diameter_m
        reference_area = pi * 0.25
        capacity_factor = max(1.0e-6, area / reference_area)
        maximum_vapor_capacity_flow = max(0.0, vapor_flow * capacity_factor)
        maximum_liquid_capacity_flow = max(0.0, liquid_flow * capacity_factor)
        condenser_duty_request_w = float(u[u_map["condenser_duty_request_W"]])
        reboiler_duty_request_w = float(u[u_map["reboiler_duty_request_W"]])
        condenser_latent = float(k[k_map["condenser_latent_heat_j_per_mol"]])
        reboiler_latent = float(k[k_map["reboiler_latent_heat_j_per_mol"]])

        condenser_duty_w, realized_condensed_flow = _realized_phase_change_flow_from_duty(
            duty_request_w=condenser_duty_request_w,
            latent_heat_j_per_mol=condenser_latent,
            fallback_flow_mol_s=vapor_flow,
            inventory_limit_mol_s=min(vapor_flow, maximum_vapor_capacity_flow),
            expects_negative_duty=True,
        )
        support_available_mol = max(0.0, float(np.sum(sump_moles)))
        support_time_constant_s = 4.0
        support_limited_flow = support_available_mol / support_time_constant_s

        reboiler_duty_w, realized_reboiler_boilup_flow = _realized_phase_change_flow_from_duty(
            duty_request_w=reboiler_duty_request_w,
            latent_heat_j_per_mol=reboiler_latent,
            fallback_flow_mol_s=0.6 * vapor_flow,
            inventory_limit_mol_s=min(support_limited_flow, maximum_vapor_capacity_flow),
            expects_negative_duty=False,
        )
        distillate_withdrawal_request = max(0.0, float(u[u_map["distillate_withdrawal_flow"]]))
        bottoms_withdrawal_request = max(0.0, float(u[u_map["bottoms_withdrawal_flow"]]))

        distillate_flow = min(
            _realized_withdrawal_flow(
                requested_flow=distillate_withdrawal_request,
                owner_moles=drum_moles,
            ),
            maximum_liquid_capacity_flow,
        )
        reflux_nominal_flow = max(0.0, realized_condensed_flow - distillate_flow)
        reflux_outlet_flow = min(
            _realized_withdrawal_flow(
                requested_flow=reflux_nominal_flow,
                owner_moles=drum_moles,
            ),
            maximum_liquid_capacity_flow,
        )
        bottoms_flow = min(
            _realized_withdrawal_flow(
                requested_flow=bottoms_withdrawal_request,
                owner_moles=sump_moles,
            ),
            maximum_liquid_capacity_flow,
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

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["distillate_flow"]] = max(0.0, distillate_flow)
        result[algebraic_map["bottoms_flow"]] = max(0.0, bottoms_flow)
        result[algebraic_map["distillate_composition"]] = drum_x
        result[algebraic_map["bottoms_composition"]] = sump_x
        result[algebraic_map["distillate_temperature"]] = mixed_feed_temperature
        result[algebraic_map["bottoms_temperature"]] = mixed_feed_temperature + 12.0
        result[algebraic_map["reflux_outlet_flow"]] = reflux_outlet_flow
        result[algebraic_map["reflux_outlet_temperature"]] = mixed_feed_temperature
        result[algebraic_map["reflux_outlet_composition"]] = drum_x
        result[algebraic_map["condenser_duty_W"]] = condenser_duty_w
        result[algebraic_map["reboiler_duty_W"]] = reboiler_duty_w
        result[algebraic_map["realized_condensed_flow_mol_s"]] = realized_condensed_flow
        result[algebraic_map["realized_reboiler_boilup_flow_mol_s"]] = realized_reboiler_boilup_flow
        result[algebraic_map["maximum_vapor_capacity_flow_mol_s"]] = maximum_vapor_capacity_flow
        result[algebraic_map["maximum_liquid_capacity_flow_mol_s"]] = maximum_liquid_capacity_flow
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
        drum_moles = np.asarray(y[y_map["reflux_drum_component_moles"]], dtype=np.float64).reshape(
            -1
        )
        sump_moles = np.asarray(y[y_map["bottoms_sump_component_moles"]], dtype=np.float64).reshape(
            -1
        )

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

        liquid_flow = max(0.0, float(k[k_map["stage_liquid_flow_mol_s"]]))
        vapor_flow = max(0.0, float(k[k_map["stage_vapor_flow_mol_s"]]))
        boilup_ratio = max(1.0e-9, float(k[k_map["boilup_ratio"]]))
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
        y_stage = np.vstack(
            [
                _safe_fraction_from_moles(
                    effective_alpha * x_stage[stage_index], n_species=n_species
                )
                for stage_index in range(n_stages)
            ]
        )
        x_drum = _owner_fraction_from_moles(drum_moles, n_species=n_species)
        x_sump = _owner_fraction_from_moles(sump_moles, n_species=n_species)
        y_reboiler = _safe_fraction_from_moles(effective_alpha * x_sump, n_species=n_species)

        condenser_flow = max(0.0, float(algebraic[algebraic_map["realized_condensed_flow_mol_s"]]))
        distillate_flow = float(algebraic[algebraic_map["distillate_flow"]])
        bottoms_flow = float(algebraic[algebraic_map["bottoms_flow"]])
        reflux_flow = max(0.0, float(algebraic[algebraic_map["reflux_outlet_flow"]]))
        reboiler_vapor_flow = max(
            0.0, float(algebraic[algebraic_map["realized_reboiler_boilup_flow_mol_s"]])
        )

        feed_to_stage = np.zeros((n_stages, n_species), dtype=np.float64)
        for feed_index in range(n_feeds):
            stage_index = int(
                np.clip(round(float(feed_stage_indices[feed_index])) - 1, 0, n_stages - 1)
            )
            z = _safe_fraction_from_moles(feed_compositions[feed_index], n_species=n_species)
            feed_to_stage[stage_index] += feed_flows[feed_index] * z

        d_stage = np.zeros_like(stage_moles)
        for stage_index in range(n_stages):
            liquid_in = (
                reflux_flow * x_drum if stage_index == 0 else liquid_flow * x_stage[stage_index - 1]
            )
            liquid_out = liquid_flow * x_stage[stage_index]

            vapor_in = (
                reboiler_vapor_flow * y_reboiler
                if stage_index == n_stages - 1
                else vapor_flow * y_stage[stage_index + 1]
            )
            vapor_out = (condenser_flow if stage_index == 0 else vapor_flow) * y_stage[stage_index]

            d_stage[stage_index] = (
                feed_to_stage[stage_index] + liquid_in + vapor_in - liquid_out - vapor_out
            )

        d_drum = (
            condenser_flow * y_stage[0]
            + reflux_return_flow * reflux_return_composition
            - reflux_flow * x_drum
            - distillate_flow * x_drum
        )
        d_sump = (
            liquid_flow * x_stage[-1] - reboiler_vapor_flow * y_reboiler - bottoms_flow * x_sump
        )

        d_pressure = 0.0

        dy = np.zeros_like(y)
        dy[y_map["stage_component_moles"]] = d_stage.reshape(-1)
        dy[y_map["reflux_drum_component_moles"]] = d_drum
        dy[y_map["bottoms_sump_component_moles"]] = d_sump
        dy[y_map["column_pressure_pa"]] = d_pressure
        return dy


__all__ = ["StagewiseDistillationColumn"]
