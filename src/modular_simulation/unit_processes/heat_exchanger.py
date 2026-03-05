from __future__ import annotations

# pyright: reportMissingTypeStubs=false

from dataclasses import dataclass
from math import exp, isfinite, log
from typing import Annotated, ClassVar, Literal, cast, override

import numpy as np
from numpy.typing import NDArray
from pydantic import PrivateAttr, field_validator

from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import (
    AlgebraicProcessModel,
    UnitProcessPorts,
)
from modular_simulation.thermodynamics.hydraulic_adapters import pipe_hydraulic_element_for_outlet
from modular_simulation.thermodynamics.property_package import PropertyPackage
from modular_simulation.thermodynamics.stream import PortAttributeMap, StreamData
from modular_simulation.utils.typing import ArrayIndex, Seconds

_FLOW_EPSILON = 1.0e-12
_COMPOSITION_TOL = 1.0e-8
_TINY_POSITIVE_PRESSURE = 1.0e-9
_CP_FALLBACK = 75.0
_CR_EPS = 1.0e-10
_DELTA_T_EPS = 1.0e-12

_ARRANGEMENT_COUNTER = 0.0
_ARRANGEMENT_CO = 1.0
_ARRANGEMENT_CROSS = 2.0

HEAT_EXCHANGER_PORTS = UnitProcessPorts(
    ("hot_inlet", "cold_inlet"),
    ("hot_outlet", "cold_outlet"),
)


def _normalize_arrangement(value: str) -> Literal["counter", "co", "cross"]:
    normalized = value.strip().casefold().replace("_", "-")
    if normalized in {"counter", "counter-current", "countercurrent"}:
        return "counter"
    if normalized in {"co", "co-current", "cocurrent", "parallel"}:
        return "co"
    if normalized in {"cross", "crossflow", "cross-flow"}:
        return "cross"
    raise ValueError("flow_arrangement must be 'counter', 'co', or 'cross' (aliases accepted).")


def _arrangement_from_selector(selector: float) -> Literal["counter", "co", "cross"]:
    if abs(selector - _ARRANGEMENT_COUNTER) < 0.5:
        return "counter"
    if abs(selector - _ARRANGEMENT_CO) < 0.5:
        return "co"
    if abs(selector - _ARRANGEMENT_CROSS) < 0.5:
        return "cross"
    raise ValueError("flow_arrangement selector must encode counter, co, or cross.")


def _vector_from_state(values: NDArray[np.float64], index: ArrayIndex) -> NDArray[np.float64]:
    return np.asarray(values[index], dtype=np.float64).reshape(-1)


def _coerce_vector(
    value: NDArray[np.float64], *, expected_size: int, name: str
) -> NDArray[np.float64]:
    vector = np.asarray(value, dtype=np.float64).reshape(-1)
    if vector.size == 0:
        return np.full(expected_size, 1.0 / float(expected_size), dtype=np.float64)
    if vector.size != expected_size:
        raise ValueError(f"{name} length mismatch: expected {expected_size}, got {vector.size}.")
    return vector


def _validate_composition(composition: NDArray[np.float64], *, name: str) -> None:
    if not np.all(np.isfinite(composition)):
        raise ValueError(f"{name} must contain only finite values.")
    if np.any(composition < 0.0):
        raise ValueError(f"{name} must contain non-negative values.")
    if abs(float(np.sum(composition)) - 1.0) > _COMPOSITION_TOL:
        raise ValueError(f"{name} must sum to 1.0.")


def _lmtd(delta_t1: float, delta_t2: float) -> float:
    if not isfinite(delta_t1) or not isfinite(delta_t2):
        return 0.0
    if delta_t1 <= _DELTA_T_EPS or delta_t2 <= _DELTA_T_EPS:
        return 0.0
    if abs(delta_t1 - delta_t2) <= _DELTA_T_EPS:
        return max(delta_t1, 0.0)
    ratio = delta_t1 / delta_t2
    if ratio <= 0.0:
        return 0.0
    return max((delta_t1 - delta_t2) / log(ratio), 0.0)


def _effectiveness(ntu: float, c_r: float, arrangement: Literal["counter", "co", "cross"]) -> float:
    ntu_safe = max(float(ntu), 0.0)
    c_r_safe = min(max(float(c_r), 0.0), 1.0)

    if ntu_safe <= 0.0:
        return 0.0

    if arrangement == "co":
        denom = 1.0 + c_r_safe
        epsilon = (1.0 - exp(-ntu_safe * denom)) / denom
    elif arrangement == "counter":
        if abs(1.0 - c_r_safe) <= _CR_EPS:
            epsilon = ntu_safe / (1.0 + ntu_safe)
        else:
            exp_term = exp(-ntu_safe * (1.0 - c_r_safe))
            epsilon = (1.0 - exp_term) / (1.0 - c_r_safe * exp_term)
    else:
        if c_r_safe <= _CR_EPS:
            epsilon = 1.0 - exp(-ntu_safe)
        else:
            epsilon = 1.0 - exp((exp(-c_r_safe * ntu_safe) - 1.0) / c_r_safe)

    return min(max(float(epsilon), 0.0), 1.0)


@dataclass(frozen=True)
class _HeatExchangerResult:
    hot_outlet_temperature: float
    cold_outlet_temperature: float
    duty_hot: float
    duty_cold: float
    duty_transfer: float
    effectiveness: float
    ntu: float
    c_hot: float
    c_cold: float
    c_min: float
    c_max: float
    c_r: float
    q_max: float
    delta_t1: float
    delta_t2: float
    lmtd: float
    ua_from_lmtd: float


def _solve_exchanger(
    *,
    hot_inlet_temperature: float,
    cold_inlet_temperature: float,
    hot_flow: float,
    cold_flow: float,
    ua: float,
    cp_hot: float,
    cp_cold: float,
    arrangement: Literal["counter", "co", "cross"],
) -> _HeatExchangerResult:
    if (
        hot_flow <= _FLOW_EPSILON
        or cold_flow <= _FLOW_EPSILON
        or cp_hot <= 0.0
        or cp_cold <= 0.0
        or ua <= 0.0
    ):
        duty_transfer = 0.0
        hot_out = hot_inlet_temperature
        cold_out = cold_inlet_temperature
        c_hot = max(hot_flow, 0.0) * max(cp_hot, 0.0)
        c_cold = max(cold_flow, 0.0) * max(cp_cold, 0.0)
        c_min = min(c_hot, c_cold)
        c_max = max(c_hot, c_cold)
        c_r = c_min / c_max if c_max > 0.0 else 0.0
        q_max = max(c_min * (hot_inlet_temperature - cold_inlet_temperature), 0.0)
        delta_t1 = max(hot_inlet_temperature - cold_inlet_temperature, 0.0)
        delta_t2 = delta_t1
        lmtd = _lmtd(delta_t1, delta_t2)
        return _HeatExchangerResult(
            hot_outlet_temperature=hot_out,
            cold_outlet_temperature=cold_out,
            duty_hot=-duty_transfer,
            duty_cold=duty_transfer,
            duty_transfer=duty_transfer,
            effectiveness=0.0,
            ntu=0.0,
            c_hot=c_hot,
            c_cold=c_cold,
            c_min=c_min,
            c_max=c_max,
            c_r=c_r,
            q_max=q_max,
            delta_t1=delta_t1,
            delta_t2=delta_t2,
            lmtd=lmtd,
            ua_from_lmtd=0.0,
        )

    c_hot = hot_flow * cp_hot
    c_cold = cold_flow * cp_cold
    c_min = min(c_hot, c_cold)
    c_max = max(c_hot, c_cold)
    c_r = c_min / c_max if c_max > 0.0 else 0.0

    delta_t_in = hot_inlet_temperature - cold_inlet_temperature
    if delta_t_in <= 0.0:
        return _HeatExchangerResult(
            hot_outlet_temperature=hot_inlet_temperature,
            cold_outlet_temperature=cold_inlet_temperature,
            duty_hot=0.0,
            duty_cold=0.0,
            duty_transfer=0.0,
            effectiveness=0.0,
            ntu=0.0,
            c_hot=c_hot,
            c_cold=c_cold,
            c_min=c_min,
            c_max=c_max,
            c_r=c_r,
            q_max=0.0,
            delta_t1=0.0,
            delta_t2=0.0,
            lmtd=0.0,
            ua_from_lmtd=0.0,
        )

    ntu = ua / c_min
    epsilon = _effectiveness(ntu, c_r, arrangement)
    q_max = c_min * delta_t_in
    duty_transfer = epsilon * q_max

    hot_outlet_temperature = hot_inlet_temperature - duty_transfer / c_hot
    cold_outlet_temperature = cold_inlet_temperature + duty_transfer / c_cold

    duty_hot_raw = c_hot * (hot_outlet_temperature - hot_inlet_temperature)
    duty_cold_raw = c_cold * (cold_outlet_temperature - cold_inlet_temperature)
    duty_balanced = 0.5 * (duty_cold_raw - duty_hot_raw)
    duty_hot = -duty_balanced
    duty_cold = duty_balanced

    hot_outlet_temperature = hot_inlet_temperature + duty_hot / c_hot
    cold_outlet_temperature = cold_inlet_temperature + duty_cold / c_cold

    if arrangement == "counter":
        delta_t1 = max(hot_inlet_temperature - cold_outlet_temperature, 0.0)
        delta_t2 = max(hot_outlet_temperature - cold_inlet_temperature, 0.0)
    else:
        delta_t1 = max(hot_inlet_temperature - cold_inlet_temperature, 0.0)
        delta_t2 = max(hot_outlet_temperature - cold_outlet_temperature, 0.0)

    lmtd = _lmtd(delta_t1, delta_t2)
    ua_from_lmtd = duty_balanced / lmtd if lmtd > _DELTA_T_EPS else 0.0

    return _HeatExchangerResult(
        hot_outlet_temperature=hot_outlet_temperature,
        cold_outlet_temperature=cold_outlet_temperature,
        duty_hot=duty_hot,
        duty_cold=duty_cold,
        duty_transfer=duty_balanced,
        effectiveness=epsilon,
        ntu=max(ntu, 0.0),
        c_hot=c_hot,
        c_cold=c_cold,
        c_min=c_min,
        c_max=c_max,
        c_r=c_r,
        q_max=q_max,
        delta_t1=delta_t1,
        delta_t2=delta_t2,
        lmtd=lmtd,
        ua_from_lmtd=ua_from_lmtd,
    )


class HeatExchanger(AlgebraicProcessModel):
    _INLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "hot_inlet": PortAttributeMap(
            flow="hot_inlet_flow",
            temperature="hot_inlet_temperature",
            pressure="hot_inlet_pressure",
            composition="hot_inlet_composition",
        ),
        "cold_inlet": PortAttributeMap(
            flow="cold_inlet_flow",
            temperature="cold_inlet_temperature",
            pressure="cold_inlet_pressure",
            composition="cold_inlet_composition",
        ),
    }
    _OUTLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "hot_outlet": PortAttributeMap(
            flow="hot_outlet_flow",
            temperature="hot_outlet_temperature",
            pressure="hot_outlet_pressure",
            composition="hot_outlet_composition",
        ),
        "cold_outlet": PortAttributeMap(
            flow="cold_outlet_flow",
            temperature="cold_outlet_temperature",
            pressure="cold_outlet_pressure",
            composition="cold_outlet_composition",
        ),
    }

    flow_arrangement: Annotated[
        float | Literal["counter", "co", "cross"],
        M(type=T.CONSTANT, unit="", description="arrangement selector: 0=counter, 1=co, 2=cross"),
    ] = _ARRANGEMENT_COUNTER
    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2
    ua: Annotated[
        float,
        M(type=T.CONSTANT, unit="W/K", description="overall heat-transfer conductance"),
    ] = 0.0

    hot_inlet_flow: Annotated[
        float,
        M(type=T.CONTROLLED, unit="mol/s", description="hot-side inlet molar flow rate"),
    ] = 0.0
    hot_inlet_temperature: Annotated[
        float,
        M(type=T.CONTROLLED, unit="K", description="hot-side inlet temperature"),
    ] = 350.0
    hot_inlet_pressure: Annotated[
        float,
        M(type=T.CONTROLLED, unit="Pa", description="hot-side inlet pressure"),
    ] = 101325.0
    hot_inlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.CONTROLLED, unit="", description="hot-side inlet composition vector"),
    ] = np.zeros(0, dtype=np.float64)

    cold_inlet_flow: Annotated[
        float,
        M(type=T.CONTROLLED, unit="mol/s", description="cold-side inlet molar flow rate"),
    ] = 0.0
    cold_inlet_temperature: Annotated[
        float,
        M(type=T.CONTROLLED, unit="K", description="cold-side inlet temperature"),
    ] = 300.0
    cold_inlet_pressure: Annotated[
        float,
        M(type=T.CONTROLLED, unit="Pa", description="cold-side inlet pressure"),
    ] = 101325.0
    cold_inlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.CONTROLLED, unit="", description="cold-side inlet composition vector"),
    ] = np.zeros(0, dtype=np.float64)

    hot_outlet_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="hot-side outlet molar flow rate"),
    ] = 0.0
    hot_outlet_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="hot-side outlet temperature"),
    ] = 350.0
    hot_outlet_pressure: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="hot-side outlet pressure"),
    ] = 101325.0
    hot_outlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="hot-side outlet composition vector"),
    ] = np.zeros(0, dtype=np.float64)

    cold_outlet_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="cold-side outlet molar flow rate"),
    ] = 0.0
    cold_outlet_temperature: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="cold-side outlet temperature"),
    ] = 300.0
    cold_outlet_pressure: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="Pa", description="cold-side outlet pressure"),
    ] = 101325.0
    cold_outlet_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="cold-side outlet composition vector"),
    ] = np.zeros(0, dtype=np.float64)

    heat_duty_hot: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W", description="hot-side duty (negative when cooling)"),
    ] = 0.0
    heat_duty_cold: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W", description="cold-side duty (positive when heating)"),
    ] = 0.0
    heat_duty: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W", description="heat transfer magnitude from hot to cold"),
    ] = 0.0
    effectiveness: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="", description="heat-exchanger effectiveness"),
    ] = 0.0
    ntu: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="", description="number of transfer units"),
    ] = 0.0
    c_hot: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W/K", description="hot-side heat-capacity rate"),
    ] = 0.0
    c_cold: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W/K", description="cold-side heat-capacity rate"),
    ] = 0.0
    c_min: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W/K", description="minimum heat-capacity rate"),
    ] = 0.0
    c_max: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W/K", description="maximum heat-capacity rate"),
    ] = 0.0
    c_r: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="", description="heat-capacity ratio C_min/C_max"),
    ] = 0.0
    q_max: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W", description="maximum possible duty"),
    ] = 0.0
    terminal_delta_t1: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="first terminal temperature difference"),
    ] = 0.0
    terminal_delta_t2: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="second terminal temperature difference"),
    ] = 0.0
    lmtd: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="K", description="log-mean temperature difference"),
    ] = 0.0
    ua_lmtd: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W/K", description="UA back-calculated from Q and LMTD"),
    ] = 0.0

    _property_package: PropertyPackage | None = PrivateAttr(default=None)

    @field_validator("flow_arrangement", mode="before")
    @classmethod
    def _parse_arrangement(cls, value: object) -> float:
        if isinstance(value, str):
            arrangement = _normalize_arrangement(value)
            if arrangement == "counter":
                return _ARRANGEMENT_COUNTER
            if arrangement == "co":
                return _ARRANGEMENT_CO
            return _ARRANGEMENT_CROSS
        if not isinstance(value, (int, float)):
            raise ValueError("flow_arrangement must be 'counter', 'co', or 'cross'.")
        arrangement = _arrangement_from_selector(float(value))
        if arrangement == "counter":
            return _ARRANGEMENT_COUNTER
        if arrangement == "co":
            return _ARRANGEMENT_CO
        return _ARRANGEMENT_CROSS

    @override
    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        if self.n_species <= 0:
            raise ValueError("n_species must be a positive integer.")
        if not isfinite(self.ua) or self.ua < 0.0:
            raise ValueError("ua must be finite and non-negative.")

        self.hot_inlet_composition = _coerce_vector(
            self.hot_inlet_composition,
            expected_size=self.n_species,
            name="hot_inlet_composition",
        )
        self.cold_inlet_composition = _coerce_vector(
            self.cold_inlet_composition,
            expected_size=self.n_species,
            name="cold_inlet_composition",
        )
        self.hot_outlet_composition = _coerce_vector(
            self.hot_outlet_composition,
            expected_size=self.n_species,
            name="hot_outlet_composition",
        )
        self.cold_outlet_composition = _coerce_vector(
            self.cold_outlet_composition,
            expected_size=self.n_species,
            name="cold_outlet_composition",
        )

        for name, value in (
            ("hot_inlet_flow", self.hot_inlet_flow),
            ("cold_inlet_flow", self.cold_inlet_flow),
        ):
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")

        for name, value in (
            ("hot_inlet_temperature", self.hot_inlet_temperature),
            ("cold_inlet_temperature", self.cold_inlet_temperature),
        ):
            if not isfinite(value):
                raise ValueError(f"{name} must be finite.")

        for name, value in (
            ("hot_inlet_pressure", self.hot_inlet_pressure),
            ("cold_inlet_pressure", self.cold_inlet_pressure),
        ):
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive.")

        _validate_composition(self.hot_inlet_composition, name="hot_inlet_composition")
        _validate_composition(self.cold_inlet_composition, name="cold_inlet_composition")

    @property
    def ports(self) -> UnitProcessPorts:
        return HEAT_EXCHANGER_PORTS

    def set_property_package(self, package: PropertyPackage | None) -> None:
        self._property_package = package

    def apply_inlet(self, port_name: str, stream: StreamData) -> None:
        if port_name not in self.ports.inlets:
            valid_ports = ", ".join(self.ports.inlets)
            raise ValueError(
                f"Invalid inlet port '{port_name}' for {type(self).__name__}. Valid inlet ports: {valid_ports}."
            )

        port_map = self._INLET_MAP[port_name]
        setattr(self, port_map.flow, float(stream.molar_flow_rate))
        setattr(self, port_map.temperature, float(stream.temperature))
        setattr(self, port_map.pressure, float(stream.pressure))
        setattr(self, port_map.composition, np.asarray(stream.mole_fractions, dtype=np.float64))

    def get_outlet_stream(self, port_name: str) -> StreamData:
        if port_name not in self.ports.outlets:
            valid_ports = ", ".join(self.ports.outlets)
            raise ValueError(
                f"Invalid outlet port '{port_name}' for {type(self).__name__}. Valid outlet ports: {valid_ports}."
            )

        port_map = self._OUTLET_MAP[port_name]
        composition = tuple(
            float(value)
            for value in np.asarray(getattr(self, port_map.composition), dtype=np.float64)
        )
        return StreamData(
            temperature=float(getattr(self, port_map.temperature)),
            pressure=float(getattr(self, port_map.pressure)),
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
        del y, y_map

        n_species = int(round(float(k[k_map["n_species"]])))
        if n_species <= 0:
            raise ValueError("n_species must be positive.")

        arrangement = _arrangement_from_selector(float(k[k_map["flow_arrangement"]]))
        ua = float(k[k_map["ua"]])

        hot_inlet_flow = float(u[u_map["hot_inlet_flow"]])
        hot_inlet_temperature = float(u[u_map["hot_inlet_temperature"]])
        hot_inlet_pressure = float(u[u_map["hot_inlet_pressure"]])
        hot_inlet_composition = _vector_from_state(u, u_map["hot_inlet_composition"])

        cold_inlet_flow = float(u[u_map["cold_inlet_flow"]])
        cold_inlet_temperature = float(u[u_map["cold_inlet_temperature"]])
        cold_inlet_pressure = float(u[u_map["cold_inlet_pressure"]])
        cold_inlet_composition = _vector_from_state(u, u_map["cold_inlet_composition"])

        if not isfinite(ua) or ua < 0.0:
            raise ValueError("ua must be finite and non-negative.")

        for name, value in (
            ("hot_inlet_flow", hot_inlet_flow),
            ("cold_inlet_flow", cold_inlet_flow),
        ):
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")

        for name, value in (
            ("hot_inlet_temperature", hot_inlet_temperature),
            ("cold_inlet_temperature", cold_inlet_temperature),
        ):
            if not isfinite(value):
                raise ValueError(f"{name} must be finite.")

        for name, value in (
            ("hot_inlet_pressure", hot_inlet_pressure),
            ("cold_inlet_pressure", cold_inlet_pressure),
        ):
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive.")

        if hot_inlet_composition.size != n_species:
            raise ValueError(
                f"hot_inlet_composition length mismatch: expected {n_species}, got {hot_inlet_composition.size}."
            )
        if cold_inlet_composition.size != n_species:
            raise ValueError(
                f"cold_inlet_composition length mismatch: expected {n_species}, got {cold_inlet_composition.size}."
            )

        _validate_composition(hot_inlet_composition, name="hot_inlet_composition")
        _validate_composition(cold_inlet_composition, name="cold_inlet_composition")

        solved = _solve_exchanger(
            hot_inlet_temperature=hot_inlet_temperature,
            cold_inlet_temperature=cold_inlet_temperature,
            hot_flow=hot_inlet_flow,
            cold_flow=cold_inlet_flow,
            ua=ua,
            cp_hot=_CP_FALLBACK,
            cp_cold=_CP_FALLBACK,
            arrangement=arrangement,
        )

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["hot_outlet_flow"]] = hot_inlet_flow
        result[algebraic_map["hot_outlet_temperature"]] = solved.hot_outlet_temperature
        result[algebraic_map["hot_outlet_pressure"]] = max(
            hot_inlet_pressure, _TINY_POSITIVE_PRESSURE
        )
        result[algebraic_map["hot_outlet_composition"]] = hot_inlet_composition

        result[algebraic_map["cold_outlet_flow"]] = cold_inlet_flow
        result[algebraic_map["cold_outlet_temperature"]] = solved.cold_outlet_temperature
        result[algebraic_map["cold_outlet_pressure"]] = max(
            cold_inlet_pressure, _TINY_POSITIVE_PRESSURE
        )
        result[algebraic_map["cold_outlet_composition"]] = cold_inlet_composition

        result[algebraic_map["heat_duty_hot"]] = solved.duty_hot
        result[algebraic_map["heat_duty_cold"]] = solved.duty_cold
        result[algebraic_map["heat_duty"]] = solved.duty_transfer
        result[algebraic_map["effectiveness"]] = solved.effectiveness
        result[algebraic_map["ntu"]] = solved.ntu
        result[algebraic_map["c_hot"]] = solved.c_hot
        result[algebraic_map["c_cold"]] = solved.c_cold
        result[algebraic_map["c_min"]] = solved.c_min
        result[algebraic_map["c_max"]] = solved.c_max
        result[algebraic_map["c_r"]] = solved.c_r
        result[algebraic_map["q_max"]] = solved.q_max
        result[algebraic_map["terminal_delta_t1"]] = solved.delta_t1
        result[algebraic_map["terminal_delta_t2"]] = solved.delta_t2
        result[algebraic_map["lmtd"]] = solved.lmtd
        result[algebraic_map["ua_lmtd"]] = solved.ua_from_lmtd
        return result

    @override
    def step(self, dt: Seconds) -> None:
        super().step(dt)

        package = self._property_package
        if package is None:
            return

        hot_z_array = np.asarray(self.hot_inlet_composition, dtype=np.float64)
        cold_z_array = np.asarray(self.cold_inlet_composition, dtype=np.float64)
        hot_z = tuple(cast(list[float], hot_z_array.tolist()))
        cold_z = tuple(cast(list[float], cold_z_array.tolist()))

        hot_phase = package.flash_tp(
            T=float(self.hot_inlet_temperature),
            P=max(float(self.hot_inlet_pressure), _TINY_POSITIVE_PRESSURE),
            z=hot_z,
        ).phase
        cold_phase = package.flash_tp(
            T=float(self.cold_inlet_temperature),
            P=max(float(self.cold_inlet_pressure), _TINY_POSITIVE_PRESSURE),
            z=cold_z,
        ).phase

        cp_hot = float(
            package.heat_capacity_cp(
                T=float(self.hot_inlet_temperature),
                P=max(float(self.hot_inlet_pressure), _TINY_POSITIVE_PRESSURE),
                z=hot_z,
                phase=hot_phase,
            )
        )
        cp_cold = float(
            package.heat_capacity_cp(
                T=float(self.cold_inlet_temperature),
                P=max(float(self.cold_inlet_pressure), _TINY_POSITIVE_PRESSURE),
                z=cold_z,
                phase=cold_phase,
            )
        )

        solved = _solve_exchanger(
            hot_inlet_temperature=float(self.hot_inlet_temperature),
            cold_inlet_temperature=float(self.cold_inlet_temperature),
            hot_flow=float(self.hot_inlet_flow),
            cold_flow=float(self.cold_inlet_flow),
            ua=float(self.ua),
            cp_hot=cp_hot,
            cp_cold=cp_cold,
            arrangement=_arrangement_from_selector(float(self.flow_arrangement)),
        )

        self.hot_outlet_flow = float(self.hot_inlet_flow)
        self.hot_outlet_pressure = max(float(self.hot_inlet_pressure), _TINY_POSITIVE_PRESSURE)
        self.hot_outlet_temperature = solved.hot_outlet_temperature
        self.hot_outlet_composition = np.asarray(self.hot_inlet_composition, dtype=np.float64)

        self.cold_outlet_flow = float(self.cold_inlet_flow)
        self.cold_outlet_pressure = max(float(self.cold_inlet_pressure), _TINY_POSITIVE_PRESSURE)
        self.cold_outlet_temperature = solved.cold_outlet_temperature
        self.cold_outlet_composition = np.asarray(self.cold_inlet_composition, dtype=np.float64)

        self.heat_duty_hot = solved.duty_hot
        self.heat_duty_cold = solved.duty_cold
        self.heat_duty = solved.duty_transfer
        self.effectiveness = solved.effectiveness
        self.ntu = solved.ntu
        self.c_hot = solved.c_hot
        self.c_cold = solved.c_cold
        self.c_min = solved.c_min
        self.c_max = solved.c_max
        self.c_r = solved.c_r
        self.q_max = solved.q_max
        self.terminal_delta_t1 = solved.delta_t1
        self.terminal_delta_t2 = solved.delta_t2
        self.lmtd = solved.lmtd
        self.ua_lmtd = solved.ua_from_lmtd


__all__ = ["HEAT_EXCHANGER_PORTS", "HeatExchanger"]
