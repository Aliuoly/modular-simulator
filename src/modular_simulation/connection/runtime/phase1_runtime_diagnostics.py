from __future__ import annotations

from collections.abc import Mapping, Sequence

from modular_simulation.connection.domain.error_catalog import (
    DiagnosticPayload,
    coerce_diagnostic_payload,
)
from modular_simulation.connection.domain.phase1_failure_semantics import FailureFamily

RUNTIME_DIAGNOSTIC_FAILURE_CODE = "PHASE1_RUNTIME_DIAGNOSTIC"
RUNTIME_DIAGNOSTIC_PATH = "connection.runtime.macro_coupling"

_STRUCTURAL_CODE_TOKENS = (
    "VALIDATION",
    "INVARIANT",
    "REVISION_MISMATCH",
    "IDEMPOTENCY_CONFLICT",
    "COMPATIBILITY_FAILURE",
)
_PHYSICAL_CODE_TOKENS = (
    "PHYSICAL",
    "INVENTORY",
    "COMPOSITION",
    "FINITE",
)


def classify_runtime_failure_family(
    *,
    cause: BaseException | None = None,
    bookkeeping: object | None = None,
) -> FailureFamily:
    payload = (
        None
        if cause is None
        else coerce_diagnostic_payload(
            error=cause,
            default_code=RUNTIME_DIAGNOSTIC_FAILURE_CODE,
        )
    )
    family_from_payload = _classify_payload_family(payload)
    if family_from_payload is not None:
        return family_from_payload
    if bookkeeping is not None:
        return _classify_bookkeeping_family(bookkeeping)
    return FailureFamily.STRUCTURAL_INCONSISTENCY


def build_runtime_diagnostic_payload(
    *,
    cause: BaseException,
    macro_step_time_s: float,
    macro_step_index: int | None,
    executed_sequence: Sequence[str],
    updated_port_keys: Sequence[str] = (),
    transport_fallback_keys: Sequence[str] = (),
    junction_fallback_keys: Sequence[str] = (),
    picard_gate_enabled: bool = False,
    picard_iterations_used: int = 0,
    picard_converged: bool = True,
    picard_last_residual: float | None = None,
    residual_norm: float | None = None,
) -> DiagnosticPayload:
    payload = coerce_diagnostic_payload(
        error=cause,
        default_code=RUNTIME_DIAGNOSTIC_FAILURE_CODE,
    )
    if payload.get("path") is None:
        payload["path"] = RUNTIME_DIAGNOSTIC_PATH
    if payload.get("hint") is None:
        payload["hint"] = (
            "inspect replay hashes, macro-step bookkeeping, and the selected failure family "
            "before accepting this macro-step"
        )
    payload["failure_family"] = classify_runtime_failure_family(
        cause=cause,
        bookkeeping=_BookkeepingView(
            transport_fallback_keys=transport_fallback_keys,
            junction_fallback_keys=junction_fallback_keys,
            used_fallback=bool(transport_fallback_keys or junction_fallback_keys),
            picard_gate_enabled=picard_gate_enabled,
            picard_iterations_used=picard_iterations_used,
            picard_converged=picard_converged,
            picard_last_residual=picard_last_residual,
        ),
    ).value
    payload["macro_step_time_s"] = macro_step_time_s
    payload["macro_step_index"] = macro_step_index
    payload["executed_sequence"] = list(executed_sequence)
    payload["updated_port_keys"] = list(updated_port_keys)
    payload["transport_fallback_keys"] = list(transport_fallback_keys)
    payload["junction_fallback_keys"] = list(junction_fallback_keys)
    payload["used_fallback"] = bool(transport_fallback_keys or junction_fallback_keys)
    payload["picard_gate_enabled"] = picard_gate_enabled
    payload["picard_iterations_used"] = picard_iterations_used
    payload["picard_converged"] = picard_converged
    payload["picard_last_residual"] = picard_last_residual
    payload["residual_norm"] = residual_norm
    return payload


def raise_runtime_diagnostic_error(
    *,
    cause: BaseException,
    macro_step_time_s: float,
    macro_step_index: int | None,
    executed_sequence: Sequence[str],
    updated_port_keys: Sequence[str] = (),
    transport_fallback_keys: Sequence[str] = (),
    junction_fallback_keys: Sequence[str] = (),
    picard_gate_enabled: bool = False,
    picard_iterations_used: int = 0,
    picard_converged: bool = True,
    picard_last_residual: float | None = None,
    residual_norm: float | None = None,
) -> None:
    payload = build_runtime_diagnostic_payload(
        cause=cause,
        macro_step_time_s=macro_step_time_s,
        macro_step_index=macro_step_index,
        executed_sequence=executed_sequence,
        updated_port_keys=updated_port_keys,
        transport_fallback_keys=transport_fallback_keys,
        junction_fallback_keys=junction_fallback_keys,
        picard_gate_enabled=picard_gate_enabled,
        picard_iterations_used=picard_iterations_used,
        picard_converged=picard_converged,
        picard_last_residual=picard_last_residual,
        residual_norm=residual_norm,
    )
    raise Phase1RuntimeDiagnosticError(payload) from _DiagnosticPayloadCarrier(payload)


class _DiagnosticPayloadCarrier(RuntimeError):
    payload: DiagnosticPayload

    def __init__(self, payload: DiagnosticPayload) -> None:
        self.payload = payload
        super().__init__(str(payload.get("message", "phase1 runtime diagnostic")))


class Phase1RuntimeDiagnosticError(RuntimeError):
    payload: DiagnosticPayload

    def __init__(self, payload: DiagnosticPayload) -> None:
        self.payload = payload
        super().__init__(str(payload.get("message", "phase1 runtime diagnostic")))


class _BookkeepingView:
    def __init__(
        self,
        *,
        transport_fallback_keys: Sequence[str],
        junction_fallback_keys: Sequence[str],
        used_fallback: bool,
        picard_gate_enabled: bool,
        picard_iterations_used: int,
        picard_converged: bool,
        picard_last_residual: float | None,
    ) -> None:
        self.transport_fallback_keys = tuple(transport_fallback_keys)
        self.junction_fallback_keys = tuple(junction_fallback_keys)
        self.used_fallback = used_fallback
        self.picard_gate_enabled = picard_gate_enabled
        self.picard_iterations_used = picard_iterations_used
        self.picard_converged = picard_converged
        self.picard_last_residual = picard_last_residual


def _classify_payload_family(payload: Mapping[str, object] | None) -> FailureFamily | None:
    if payload is None:
        return None

    existing_family = payload.get("failure_family")
    if isinstance(existing_family, str):
        try:
            return FailureFamily(existing_family)
        except ValueError:
            pass

    code = str(payload.get("code", "")).upper()
    path = str(payload.get("path", "")).lower()
    message = str(payload.get("message", "")).lower()
    hint = str(payload.get("hint", "")).lower()
    combined = " ".join((path, message, hint))

    if any(token in code for token in _PHYSICAL_CODE_TOKENS) or any(
        token in combined
        for token in ("holdup", "inventory", "composition", "non-finite", "negative")
    ):
        return FailureFamily.INVENTORY_OR_PHYSICAL_FEASIBILITY_BREAK

    if any(token in code for token in _STRUCTURAL_CODE_TOKENS) or any(
        token in combined
        for token in (
            "pressure reference",
            "fixed-pressure",
            "graph revision",
            "structural",
            "hydraulics.network",
            "anchor",
            "revision",
        )
    ):
        return FailureFamily.STRUCTURAL_INCONSISTENCY

    return None


def _classify_bookkeeping_family(bookkeeping: object) -> FailureFamily:
    transport_fallback_keys = tuple(
        _sequence_strings(getattr(bookkeeping, "transport_fallback_keys", ()))
    )
    junction_fallback_keys = tuple(
        _sequence_strings(getattr(bookkeeping, "junction_fallback_keys", ()))
    )
    used_fallback = bool(getattr(bookkeeping, "used_fallback", False))
    picard_gate_enabled = bool(getattr(bookkeeping, "picard_gate_enabled", False))
    picard_iterations_used = int(getattr(bookkeeping, "picard_iterations_used", 0))
    picard_converged = bool(getattr(bookkeeping, "picard_converged", True))
    picard_last_residual = getattr(bookkeeping, "picard_last_residual", None)

    if picard_gate_enabled and (not picard_converged or picard_iterations_used > 0):
        return FailureFamily.SOLVER_MASKING_OR_FAKE_STABILITY
    if used_fallback or transport_fallback_keys or junction_fallback_keys:
        return FailureFamily.STALE_HYDRAULIC_LAG
    if picard_last_residual not in (None, 0.0):
        return FailureFamily.SOLVER_MASKING_OR_FAKE_STABILITY
    return FailureFamily.STRUCTURAL_INCONSISTENCY


def _sequence_strings(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        return ()
    return tuple(str(item) for item in value)


__all__ = [
    "Phase1RuntimeDiagnosticError",
    "RUNTIME_DIAGNOSTIC_FAILURE_CODE",
    "RUNTIME_DIAGNOSTIC_PATH",
    "build_runtime_diagnostic_payload",
    "classify_runtime_failure_family",
    "raise_runtime_diagnostic_error",
]
