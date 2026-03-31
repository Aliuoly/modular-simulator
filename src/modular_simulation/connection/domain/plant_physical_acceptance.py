from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np


class _SubsystemAccessor(Protocol):
    @property
    def descriptor(self) -> object: ...

    def snapshot_published_measurements(self) -> Mapping[str, float]: ...


class _ProcessModelAccessor(Protocol):
    holdup_component_moles: np.ndarray
    holdup_temperature: float
    outlet_composition: np.ndarray
    temperature: float


@dataclass(frozen=True)
class PhysicalRejectionDetail:
    process_id: str
    rejection_code: str
    rejection_message: str


def evaluate_plant_physical_acceptance(
    *,
    subsystems: Sequence[object],
) -> None:
    for subsystem in subsystems:
        system = getattr(subsystem, "system", None)
        process_model = getattr(system, "process_model", None) if system is not None else None
        if process_model is None:
            continue

        descriptor = getattr(subsystem, "descriptor", None)
        process_id = (
            getattr(descriptor, "process_id", "unknown") if descriptor is not None else "unknown"
        )

        _check_physical_state(process_id=process_id, process_model=process_model)


def _check_physical_state(*, process_id: str, process_model: object) -> None:
    holdup = _safe_array(getattr(process_model, "holdup_component_moles", None))
    composition = _safe_array(getattr(process_model, "outlet_composition", None))
    temperature = getattr(process_model, "temperature", None)
    holdup_temperature = getattr(process_model, "holdup_temperature", None)

    if holdup is not None and np.any(holdup < 0.0):
        _raise_rejection(
            process_id=process_id,
            code="NEGATIVE_INVENTORY",
            message=f"process '{process_id}' holdup has negative component(s): {holdup}",
        )

    if holdup is not None and composition is not None:
        holdup_total = float(np.sum(holdup))
        comp_total = float(np.sum(composition))
        if holdup_total <= 0.0 and comp_total <= 0.0:
            _raise_rejection(
                process_id=process_id,
                code="MASKING_OR_FALLBACK_EVIDENCE",
                message=(
                    f"process '{process_id}' has zero holdup and zero composition — "
                    f"state is a masking or fallback artifact, not a physical equilibrium"
                ),
            )

    if composition is not None and composition.size > 0:
        comp_sum = float(np.sum(composition))
        if abs(comp_sum - 1.0) > 0.05:
            _raise_rejection(
                process_id=process_id,
                code="INVALID_COMPOSITION_NORMALIZATION",
                message=(
                    f"process '{process_id}' outlet composition sum {comp_sum:.6f} "
                    f"deviates from unity beyond tolerance"
                ),
            )

    for label, value in (("temperature", temperature), ("holdup_temperature", holdup_temperature)):
        if value is not None and not _is_finite(value):
            _raise_rejection(
                process_id=process_id,
                code="NON_FINITE_PLANT_STATE",
                message=f"process '{process_id}' {label} is non-finite: {value}",
            )


def _is_finite(value: object) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _safe_array(value: object) -> np.ndarray | None:
    if value is None:
        return None
    try:
        return np.asarray(value, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError):
        return None


def _raise_rejection(*, process_id: str, code: str, message: str) -> None:
    raise RuntimeError(f"[{code}] {message}")


__all__ = [
    "PhysicalRejectionDetail",
    "evaluate_plant_physical_acceptance",
]
