from __future__ import annotations

# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportImplicitStringConcatenation=false

from math import exp, isfinite, log, sqrt
from typing import Annotated, ClassVar, cast, override
import warnings

import numpy as np
from numpy.typing import NDArray
from pydantic import PrivateAttr, model_validator

from modular_simulation.measurables.process_model import StateMetadata as M
from modular_simulation.measurables.process_model import StateType as T
from modular_simulation.thermodynamics.algebraic_process_model import (
    AlgebraicProcessModel,
    UnitProcessPorts,
)
from modular_simulation.thermodynamics.hydraulic_adapters import pipe_hydraulic_element_for_outlet
from modular_simulation.thermodynamics.property_package import FlashResult, PropertyPackage
from modular_simulation.thermodynamics.stream import PortAttributeMap, StreamData
from modular_simulation.utils.typing import ArrayIndex, Seconds

_FLOW_EPSILON = 1.0e-12
_COMPOSITION_TOL = 1.0e-8
_SMALL_POSITIVE = 1.0e-12
_ROOT_EPSILON = 1.0e-9

SHORTCUT_DISTILLATION_PORTS = UnitProcessPorts(("inlet",), ("distillate", "bottoms"))


class ShortcutDistillation(AlgebraicProcessModel):
    _INLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "inlet": PortAttributeMap(
            flow="inlet_flow",
            temperature="inlet_temperature",
            pressure="inlet_pressure",
            composition="inlet_composition",
        )
    }
    _OUTLET_MAP: ClassVar[dict[str, PortAttributeMap]] = {
        "distillate": PortAttributeMap(
            flow="distillate_flow",
            temperature="condenser_temperature",
            pressure="condenser_pressure",
            composition="distillate_composition",
        ),
        "bottoms": PortAttributeMap(
            flow="bottoms_flow",
            temperature="reboiler_temperature",
            pressure="reboiler_pressure",
            composition="bottoms_composition",
        ),
    }

    n_species: Annotated[int, M(type=T.CONSTANT, unit="", description="number of species")] = 2
    light_key_index: Annotated[
        int,
        M(type=T.CONSTANT, unit="", description="light key component index"),
    ] = 0
    heavy_key_index: Annotated[
        int,
        M(type=T.CONSTANT, unit="", description="heavy key component index"),
    ] = 1

    configured_light_key_distillate_recovery_target: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="",
            description="configured abstract light-key recovery target to distillate",
        ),
    ] = 0.98
    configured_heavy_key_bottoms_recovery_target: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="",
            description="configured abstract heavy-key recovery target to bottoms",
        ),
    ] = 0.98
    configured_minimum_reflux_ratio_factor: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="",
            description="configured abstract multiplier applied to minimum reflux ratio when no explicit target is set",
        ),
    ] = 1.5
    configured_reflux_ratio_target: Annotated[
        float,
        M(
            type=T.CONSTANT,
            unit="",
            description="configured abstract explicit reflux-ratio target (>0 overrides factor mode)",
        ),
    ] = 0.0

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
        M(type=T.BOUNDARY, unit="", description="inlet composition vector by species index"),
    ] = np.zeros(0, dtype=np.float64)

    distillate_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="distillate molar flow rate"),
    ] = 0.0
    bottoms_flow: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="mol/s", description="bottoms molar flow rate"),
    ] = 0.0
    distillate_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="distillate composition"),
    ] = np.zeros(0, dtype=np.float64)
    bottoms_composition: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="bottoms composition"),
    ] = np.zeros(0, dtype=np.float64)

    minimum_stages: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="", description="Fenske minimum stages"),
    ] = 0.0
    minimum_reflux_ratio: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="", description="Underwood minimum reflux ratio"),
    ] = 0.0
    actual_stages: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="", description="Gilliland estimated actual stages"),
    ] = 0.0
    actual_reflux_ratio: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="", description="actual reflux ratio"),
    ] = 0.0
    underwood_theta: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="", description="Underwood root"),
    ] = 0.0
    relative_volatility: Annotated[
        NDArray[np.float64],
        M(type=T.ALGEBRAIC, unit="", description="relative volatility versus heavy key"),
    ] = np.zeros(0, dtype=np.float64)
    condenser_duty: Annotated[
        float,
        M(
            type=T.ALGEBRAIC,
            unit="W",
            description="estimated condenser duty (negative for heat removal)",
        ),
    ] = 0.0
    reboiler_duty: Annotated[
        float,
        M(type=T.ALGEBRAIC, unit="W", description="estimated reboiler duty"),
    ] = 0.0

    _property_package: PropertyPackage | None = PrivateAttr(default=None)
    _condenser_temperature: float = PrivateAttr(default=298.15)
    _condenser_pressure: float = PrivateAttr(default=101325.0)
    _reboiler_temperature: float = PrivateAttr(default=298.15)
    _reboiler_pressure: float = PrivateAttr(default=101325.0)

    @staticmethod
    def _vector_from_state(values: NDArray[np.float64], index: ArrayIndex) -> NDArray[np.float64]:
        return np.asarray(values[index], dtype=np.float64).reshape(-1)

    @staticmethod
    def _coerce_vector(
        value: NDArray[np.float64], *, expected_size: int, name: str, default: float
    ) -> NDArray[np.float64]:
        vector = np.asarray(value, dtype=np.float64).reshape(-1)
        if vector.size == 0:
            return np.full(expected_size, default, dtype=np.float64)
        if vector.size != expected_size:
            raise ValueError(
                f"{name} length mismatch: expected {expected_size}, got {vector.size}."
            )
        return vector

    @staticmethod
    def _validate_composition(composition: NDArray[np.float64], *, name: str) -> None:
        if not np.all(np.isfinite(composition)):
            raise ValueError(f"{name} must contain only finite values.")
        if np.any(composition < 0.0):
            raise ValueError(f"{name} must contain non-negative values.")
        if abs(float(np.sum(composition)) - 1.0) > _COMPOSITION_TOL:
            raise ValueError(f"{name} must sum to 1.0.")

    @staticmethod
    def _validate_recovery(value: float, name: str) -> None:
        if not isfinite(value) or value <= 0.0 or value >= 1.0:
            raise ValueError(f"{name} must be finite and strictly within (0, 1).")

    @staticmethod
    def _safe_normalize(
        flow_vector: NDArray[np.float64], fallback: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        flow_vector = np.clip(np.asarray(flow_vector, dtype=np.float64), 0.0, None)
        total = float(np.sum(flow_vector))
        if total <= _FLOW_EPSILON:
            return fallback.copy()
        return flow_vector / total

    @staticmethod
    def _extract_k_values(flash: FlashResult, n_species: int) -> NDArray[np.float64]:
        if flash.K_values is not None and len(flash.K_values) == n_species:
            k = np.asarray(flash.K_values, dtype=np.float64)
        elif flash.vapor_composition is not None and flash.liquid_composition is not None:
            y = np.asarray(flash.vapor_composition, dtype=np.float64)
            x = np.asarray(flash.liquid_composition, dtype=np.float64)
            if y.size != n_species or x.size != n_species:
                raise ValueError("Flash composition size mismatch while extracting K-values.")
            k = y / np.maximum(x, _SMALL_POSITIVE)
        else:
            raise ValueError(
                "Unable to estimate K-values from property package; flash result did not provide K_values "
                + "or both vapor/liquid compositions."
            )

        if not np.all(np.isfinite(k)) or np.any(k <= 0.0):
            raise ValueError("Estimated K-values must be finite and positive.")
        return np.clip(k, _SMALL_POSITIVE, 1.0e12)

    @staticmethod
    def _fenske_n_min(
        *, x_d_lk: float, x_b_lk: float, x_d_hk: float, x_b_hk: float, alpha_lk: float
    ) -> float:
        if alpha_lk <= 1.0:
            raise ValueError(
                "Light-key relative volatility must be greater than 1 for Fenske equation."
            )
        numerator = (x_d_lk / max(x_b_lk, _SMALL_POSITIVE)) * (
            x_b_hk / max(x_d_hk, _SMALL_POSITIVE)
        )
        if numerator <= 1.0:
            raise ValueError("Fenske equation produced non-physical separation term (<= 1).")
        return max(_SMALL_POSITIVE, log(numerator) / log(alpha_lk))

    @staticmethod
    def _underwood_function(
        theta: float, z: NDArray[np.float64], alpha: NDArray[np.float64], q: float
    ) -> float:
        denominator = alpha - theta
        signed_denominator = np.where(
            np.abs(denominator) < _SMALL_POSITIVE,
            np.where(denominator >= 0.0, _SMALL_POSITIVE, -_SMALL_POSITIVE),
            denominator,
        )
        return float(np.sum(z * alpha / signed_denominator) - (1.0 - q))

    @staticmethod
    def _solve_underwood_theta(
        *,
        z: NDArray[np.float64],
        alpha: NDArray[np.float64],
        q: float,
        alpha_hk: float,
        alpha_lk: float,
    ) -> float:
        if alpha_lk <= alpha_hk:
            raise ValueError("Expected alpha_lk > alpha_hk while solving Underwood root.")

        poles = sorted(float(value) for value in alpha if alpha_hk < float(value) < alpha_lk)
        boundaries = [alpha_hk + _ROOT_EPSILON, *poles, alpha_lk - _ROOT_EPSILON]
        for left_raw, right_raw in zip(boundaries[:-1], boundaries[1:]):
            left = left_raw + _ROOT_EPSILON
            right = right_raw - _ROOT_EPSILON
            if left >= right:
                continue

            f_left = ShortcutDistillation._underwood_function(left, z, alpha, q)
            f_right = ShortcutDistillation._underwood_function(right, z, alpha, q)
            if not isfinite(f_left) or not isfinite(f_right):
                continue
            if f_left == 0.0:
                return left
            if f_right == 0.0:
                return right
            if f_left * f_right > 0.0:
                continue

            lo = left
            hi = right
            flo = f_left
            for _ in range(200):
                mid = 0.5 * (lo + hi)
                f_mid = ShortcutDistillation._underwood_function(mid, z, alpha, q)
                if not isfinite(f_mid):
                    break
                if abs(f_mid) < 1.0e-10 or abs(hi - lo) < 1.0e-10:
                    return mid
                if flo * f_mid <= 0.0:
                    hi = mid
                else:
                    lo = mid
                    flo = f_mid
            return 0.5 * (lo + hi)

        raise ValueError(
            "Underwood root not found in (alpha_HK, alpha_LK). Check recoveries, key components, "
            + "and feed thermodynamic state."
        )

    @staticmethod
    def _gilliland_n_actual(n_min: float, r_min: float, r_actual: float) -> float:
        x = (r_actual - r_min) / (r_actual + 1.0)
        x = min(max(x, 1.0e-9), 1.0 - 1.0e-9)
        y = 1.0 - exp(((1.0 + 54.4 * x) / (11.0 + 117.2 * x)) * ((x - 1.0) / sqrt(x)))
        y = min(max(y, 1.0e-9), 1.0 - 1.0e-9)
        return max(n_min + 1.0e-6, (n_min + y) / (1.0 - y))

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_configured_specs(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        legacy_names = {
            "light_key_distillate_recovery": "configured_light_key_distillate_recovery_target",
            "configured_light_key_distillate_recovery": "configured_light_key_distillate_recovery_target",
            "heavy_key_bottoms_recovery": "configured_heavy_key_bottoms_recovery_target",
            "configured_heavy_key_bottoms_recovery": "configured_heavy_key_bottoms_recovery_target",
            "reflux_ratio_factor": "configured_minimum_reflux_ratio_factor",
            "configured_reflux_ratio_factor": "configured_minimum_reflux_ratio_factor",
            "reflux_ratio_setpoint": "configured_reflux_ratio_target",
            "configured_reflux_ratio": "configured_reflux_ratio_target",
        }
        for legacy_name, new_name in legacy_names.items():
            if legacy_name in data:
                if new_name in data:
                    raise ValueError(f"Provide only one of '{legacy_name}' or '{new_name}'.")
                warnings.warn(
                    f"{legacy_name} is deprecated; use {new_name}",
                    DeprecationWarning,
                    stacklevel=2,
                )
                data[new_name] = data.pop(legacy_name)
        return data

    @override
    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        if self.n_species <= 1:
            raise ValueError("n_species must be at least 2 for shortcut distillation.")
        if self.light_key_index < 0 or self.light_key_index >= self.n_species:
            raise ValueError("light_key_index is out of bounds.")
        if self.heavy_key_index < 0 or self.heavy_key_index >= self.n_species:
            raise ValueError("heavy_key_index is out of bounds.")
        if self.light_key_index == self.heavy_key_index:
            raise ValueError("light_key_index and heavy_key_index must be different.")

        if not isfinite(self.inlet_flow) or self.inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not isfinite(self.inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not isfinite(self.inlet_pressure) or self.inlet_pressure <= 0.0:
            raise ValueError("inlet_pressure must be finite and positive.")

        self._validate_recovery(
            self.configured_light_key_distillate_recovery_target,
            "configured_light_key_distillate_recovery_target",
        )
        self._validate_recovery(
            self.configured_heavy_key_bottoms_recovery_target,
            "configured_heavy_key_bottoms_recovery_target",
        )

        if (
            not isfinite(self.configured_minimum_reflux_ratio_factor)
            or self.configured_minimum_reflux_ratio_factor <= 1.0
        ):
            raise ValueError(
                "configured_minimum_reflux_ratio_factor must be finite and greater than 1."
            )
        if (
            not isfinite(self.configured_reflux_ratio_target)
            or self.configured_reflux_ratio_target < 0.0
        ):
            raise ValueError("configured_reflux_ratio_target must be finite and non-negative.")

        self.inlet_composition = self._coerce_vector(
            self.inlet_composition,
            expected_size=self.n_species,
            name="inlet_composition",
            default=1.0 / float(self.n_species),
        )
        self.distillate_composition = self._coerce_vector(
            self.distillate_composition,
            expected_size=self.n_species,
            name="distillate_composition",
            default=1.0 / float(self.n_species),
        )
        self.bottoms_composition = self._coerce_vector(
            self.bottoms_composition,
            expected_size=self.n_species,
            name="bottoms_composition",
            default=1.0 / float(self.n_species),
        )
        self.relative_volatility = self._coerce_vector(
            self.relative_volatility,
            expected_size=self.n_species,
            name="relative_volatility",
            default=1.0,
        )

        self._validate_composition(
            np.asarray(self.inlet_composition, dtype=np.float64), name="inlet_composition"
        )
        self._condenser_temperature = float(self.inlet_temperature)
        self._condenser_pressure = float(self.inlet_pressure)
        self._reboiler_temperature = float(self.inlet_temperature)
        self._reboiler_pressure = float(self.inlet_pressure)

    @property
    def ports(self) -> UnitProcessPorts:
        return SHORTCUT_DISTILLATION_PORTS

    def set_property_package(self, package: PropertyPackage | None) -> None:
        self._property_package = package

    @property
    def condenser_temperature(self) -> float:
        return float(self._condenser_temperature)

    @condenser_temperature.setter
    def condenser_temperature(self, value: float) -> None:
        self._condenser_temperature = float(value)

    @property
    def condenser_pressure(self) -> float:
        return float(self._condenser_pressure)

    @condenser_pressure.setter
    def condenser_pressure(self, value: float) -> None:
        self._condenser_pressure = float(value)

    @property
    def reboiler_temperature(self) -> float:
        return float(self._reboiler_temperature)

    @reboiler_temperature.setter
    def reboiler_temperature(self, value: float) -> None:
        self._reboiler_temperature = float(value)

    @property
    def reboiler_pressure(self) -> float:
        return float(self._reboiler_pressure)

    @reboiler_pressure.setter
    def reboiler_pressure(self, value: float) -> None:
        self._reboiler_pressure = float(value)

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
        self.condenser_temperature = float(stream.temperature)
        self.condenser_pressure = float(stream.pressure)
        self.reboiler_temperature = float(stream.temperature)
        self.reboiler_pressure = float(stream.pressure)

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
        if n_species <= 1:
            raise ValueError("n_species must be at least 2 for shortcut distillation.")

        lk_index = int(round(float(k[k_map["light_key_index"]])))
        hk_index = int(round(float(k[k_map["heavy_key_index"]])))
        if lk_index == hk_index:
            raise ValueError("light_key_index and heavy_key_index must be different.")
        if lk_index < 0 or lk_index >= n_species or hk_index < 0 or hk_index >= n_species:
            raise ValueError("Key component indices are out of bounds.")

        inlet_flow = float(u[u_map["inlet_flow"]])
        inlet_temperature = float(u[u_map["inlet_temperature"]])
        inlet_pressure = float(u[u_map["inlet_pressure"]])
        z = ShortcutDistillation._vector_from_state(u, u_map["inlet_composition"])
        lk_rec = float(k[k_map["configured_light_key_distillate_recovery_target"]])
        hk_bottoms_rec = float(k[k_map["configured_heavy_key_bottoms_recovery_target"]])

        if not isfinite(inlet_flow) or inlet_flow < 0.0:
            raise ValueError("inlet_flow must be finite and non-negative.")
        if not isfinite(inlet_temperature):
            raise ValueError("inlet_temperature must be finite.")
        if not isfinite(inlet_pressure) or inlet_pressure <= 0.0:
            raise ValueError("inlet_pressure must be finite and positive.")
        if z.size != n_species:
            raise ValueError(
                f"inlet_composition length mismatch: expected {n_species}, got {z.size}."
            )

        ShortcutDistillation._validate_composition(z, name="inlet_composition")
        ShortcutDistillation._validate_recovery(
            lk_rec, "configured_light_key_distillate_recovery_target"
        )
        ShortcutDistillation._validate_recovery(
            hk_bottoms_rec, "configured_heavy_key_bottoms_recovery_target"
        )

        feed_components = inlet_flow * z
        recovery = np.full(n_species, 0.5, dtype=np.float64)
        recovery[lk_index] = lk_rec
        recovery[hk_index] = 1.0 - hk_bottoms_rec

        distillate_component = np.clip(feed_components * recovery, 0.0, None)
        bottoms_component = np.clip(feed_components - distillate_component, 0.0, None)
        distillate_flow = float(np.sum(distillate_component))
        bottoms_flow = float(np.sum(bottoms_component))

        distillate_comp = ShortcutDistillation._safe_normalize(distillate_component, z)
        bottoms_comp = ShortcutDistillation._safe_normalize(bottoms_component, z)

        result = np.zeros(algebraic_size, dtype=np.float64)
        result[algebraic_map["distillate_flow"]] = distillate_flow
        result[algebraic_map["bottoms_flow"]] = bottoms_flow
        result[algebraic_map["distillate_composition"]] = distillate_comp
        result[algebraic_map["bottoms_composition"]] = bottoms_comp
        result[algebraic_map["minimum_stages"]] = 0.0
        result[algebraic_map["minimum_reflux_ratio"]] = 0.0
        result[algebraic_map["actual_stages"]] = 0.0
        result[algebraic_map["actual_reflux_ratio"]] = 0.0
        result[algebraic_map["underwood_theta"]] = 0.0
        result[algebraic_map["relative_volatility"]] = np.ones(n_species, dtype=np.float64)
        result[algebraic_map["condenser_duty"]] = 0.0
        result[algebraic_map["reboiler_duty"]] = 0.0
        return result

    @override
    def step(self, dt: Seconds) -> None:
        super().step(dt)

        self.condenser_temperature = float(self.inlet_temperature)
        self.condenser_pressure = float(self.inlet_pressure)
        self.reboiler_temperature = float(self.inlet_temperature)
        self.reboiler_pressure = float(self.inlet_pressure)

        package = self._property_package
        if package is None:
            return

        z = np.asarray(self.inlet_composition, dtype=np.float64)
        self._validate_composition(z, name="inlet_composition")
        feed_flow = float(self.inlet_flow)
        if feed_flow <= _FLOW_EPSILON:
            self.distillate_flow = 0.0
            self.bottoms_flow = 0.0
            self.distillate_composition = z.copy()
            self.bottoms_composition = z.copy()
            self.minimum_stages = 0.0
            self.minimum_reflux_ratio = 0.0
            self.actual_stages = 0.0
            self.actual_reflux_ratio = 0.0
            self.underwood_theta = 0.0
            self.relative_volatility = np.ones_like(z)
            self.condenser_duty = 0.0
            self.reboiler_duty = 0.0
            return

        lk = int(self.light_key_index)
        hk = int(self.heavy_key_index)
        lk_rec = float(self.configured_light_key_distillate_recovery_target)
        hk_bottoms_rec = float(self.configured_heavy_key_bottoms_recovery_target)

        flash = package.flash_tp(
            T=float(self.inlet_temperature),
            P=float(self.inlet_pressure),
            z=tuple(cast(list[float], z.tolist())),
        )
        k_values = self._extract_k_values(flash, int(self.n_species))

        k_hk = float(k_values[hk])
        if k_hk <= 0.0:
            raise ValueError(
                "Heavy-key K-value must be positive for relative volatility estimation."
            )
        alpha = np.clip(k_values / k_hk, _SMALL_POSITIVE, 1.0e12)
        alpha_hk = float(alpha[hk])
        alpha_lk = float(alpha[lk])
        if alpha_lk <= alpha_hk:
            raise ValueError(
                "Key component consistency failed: selected light key is not more volatile than heavy key "
                + "at feed conditions."
            )

        hk_distillate_recovery = 1.0 - hk_bottoms_rec
        split = np.empty_like(z)
        for idx in range(int(self.n_species)):
            if idx == lk:
                recovery = lk_rec
            elif idx == hk:
                recovery = hk_distillate_recovery
            else:
                alpha_i = float(alpha[idx])
                if alpha_i >= alpha_lk:
                    recovery = min(0.999, lk_rec + 0.5 * (1.0 - lk_rec))
                elif alpha_i <= alpha_hk:
                    recovery = max(0.001, 0.5 * hk_distillate_recovery)
                else:
                    interpolation = log(alpha_i / alpha_hk) / log(alpha_lk / alpha_hk)
                    recovery = hk_distillate_recovery + interpolation * (
                        lk_rec - hk_distillate_recovery
                    )
            split[idx] = min(max(recovery, 0.001), 0.999)

        feed_components = feed_flow * z
        distillate_component = np.clip(feed_components * split, 0.0, None)
        bottoms_component = np.clip(feed_components - distillate_component, 0.0, None)

        distillate_flow = float(np.sum(distillate_component))
        bottoms_flow = float(np.sum(bottoms_component))
        if distillate_flow <= _FLOW_EPSILON or bottoms_flow <= _FLOW_EPSILON:
            raise ValueError(
                "Shortcut distillation produced a degenerate split with near-zero product flow."
            )

        x_d = self._safe_normalize(distillate_component, z)
        x_b = self._safe_normalize(bottoms_component, z)

        n_min = self._fenske_n_min(
            x_d_lk=float(x_d[lk]),
            x_b_lk=float(x_b[lk]),
            x_d_hk=float(x_d[hk]),
            x_b_hk=float(x_b[hk]),
            alpha_lk=alpha_lk,
        )

        q = min(max(1.0 - float(flash.vapor_fraction), 0.0), 1.0)
        theta = self._solve_underwood_theta(
            z=z,
            alpha=alpha,
            q=q,
            alpha_hk=alpha_hk,
            alpha_lk=alpha_lk,
        )

        denominator = alpha - theta
        signed_denominator = np.where(
            np.abs(denominator) < _SMALL_POSITIVE,
            np.where(denominator >= 0.0, _SMALL_POSITIVE, -_SMALL_POSITIVE),
            denominator,
        )
        r_min = float(np.sum(x_d * alpha / signed_denominator) - 1.0)
        if not isfinite(r_min) or r_min <= 0.0:
            raise ValueError(
                "Underwood minimum reflux ratio is non-physical. Check key recoveries and feed state."
            )

        if float(self.configured_reflux_ratio_target) > 0.0:
            r_actual = float(self.configured_reflux_ratio_target)
        else:
            r_actual = float(self.configured_minimum_reflux_ratio_factor) * r_min
        if r_actual <= r_min:
            raise ValueError("R_actual must be greater than R_min for Gilliland stage estimation.")

        n_actual = self._gilliland_n_actual(n_min, r_min, r_actual)
        if n_actual <= n_min:
            raise ValueError("N_actual must be greater than N_min for physical feasibility.")

        z_d = tuple(cast(list[float], x_d.tolist()))
        z_b = tuple(cast(list[float], x_b.tolist()))
        feed_tuple = tuple(cast(list[float], z.tolist()))

        h_feed = float(flash.enthalpy_molar)
        h_d_liq = float(
            package.enthalpy(
                T=float(self.inlet_temperature), P=float(self.inlet_pressure), z=z_d, phase="liquid"
            )
        )
        h_b_liq = float(
            package.enthalpy(
                T=float(self.inlet_temperature), P=float(self.inlet_pressure), z=z_b, phase="liquid"
            )
        )
        try:
            h_d_vap = float(
                package.enthalpy(
                    T=float(self.inlet_temperature),
                    P=float(self.inlet_pressure),
                    z=z_d,
                    phase="vapor",
                )
            )
        except ValueError:
            h_d_vap = float(
                package.flash_tp(
                    T=float(self.inlet_temperature), P=float(self.inlet_pressure), z=z_d
                ).enthalpy_molar
            )

        reflux_flow = r_actual * distillate_flow
        condenser_duty = -max(0.0, (distillate_flow + reflux_flow) * max(h_d_vap - h_d_liq, 0.0))
        total_balance_heat = distillate_flow * h_d_liq + bottoms_flow * h_b_liq - feed_flow * h_feed
        reboiler_duty = max(0.0, total_balance_heat - condenser_duty)

        self.distillate_flow = distillate_flow
        self.bottoms_flow = bottoms_flow
        self.distillate_composition = x_d
        self.bottoms_composition = x_b
        self.minimum_stages = n_min
        self.minimum_reflux_ratio = r_min
        self.actual_stages = n_actual
        self.actual_reflux_ratio = r_actual
        self.underwood_theta = theta
        self.relative_volatility = alpha
        self.condenser_duty = condenser_duty
        self.reboiler_duty = reboiler_duty

        _ = package.flash_tp(
            T=float(self.inlet_temperature), P=float(self.inlet_pressure), z=feed_tuple
        )


__all__ = ["SHORTCUT_DISTILLATION_PORTS", "ShortcutDistillation"]
