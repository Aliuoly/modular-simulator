from __future__ import annotations

from modular_simulation.connection.hydraulics.hydraulic_compile import GraphCompileError

from .error_catalog import (
    IDEMPOTENCY_CONFLICT_CODE,
    INVARIANT_FAILURE_CODE,
    REVISION_MISMATCH_CODE,
    VALIDATION_FAILURE_CODE,
    DiagnosticPayload,
    DiagnosticRuntimeError,
    coerce_diagnostic_payload,
)
from .phase1_failure_semantics import FailureFamily

STRUCTURAL_PRE_STEP_BARRIER_REJECTION_CODE = "STRUCTURAL_PRE_STEP_BARRIER_REJECTION"
STRUCTURAL_PRE_STEP_COMPILE_REJECTION_CODE = "STRUCTURAL_PRE_STEP_COMPILE_REJECTION"
STRUCTURAL_PRE_STEP_INVARIANT_REJECTION_CODE = "STRUCTURAL_PRE_STEP_INVARIANT_REJECTION"
STRUCTURAL_PRE_STEP_HYDRAULIC_REJECTION_CODE = "STRUCTURAL_PRE_STEP_HYDRAULIC_REJECTION"

STRUCTURAL_PRE_STEP_REJECTION_STAGE = "pre_step"
STRUCTURAL_REJECTION_FAMILY = FailureFamily.STRUCTURAL_INCONSISTENCY.value


def structural_pre_step_runtime_error(
    *,
    error: BaseException,
    code: str,
    source: str,
    default_code: str,
    path: str | None = None,
    hint: str | None = None,
) -> DiagnosticRuntimeError:
    return DiagnosticRuntimeError(
        _structural_payload(
            error=error,
            code=code,
            source=source,
            default_code=default_code,
            path=path,
            hint=hint,
        )
    )


def translate_barrier_failure(error: BaseException) -> DiagnosticRuntimeError:
    if isinstance(error, GraphCompileError):
        return structural_pre_step_runtime_error(
            error=error,
            code=STRUCTURAL_PRE_STEP_COMPILE_REJECTION_CODE,
            source="compile",
            default_code=VALIDATION_FAILURE_CODE,
            path="compile",
            hint="fix the queued structural inconsistency before retrying the pre-step macro-step",
        )

    source_payload = coerce_diagnostic_payload(error=error, default_code=VALIDATION_FAILURE_CODE)
    source_code = source_payload.get("code")
    if (
        source_code == INVARIANT_FAILURE_CODE
        or source_payload.get("structural_rejection_source") == "invariant"
    ):
        return structural_pre_step_runtime_error(
            error=error,
            code=STRUCTURAL_PRE_STEP_INVARIANT_REJECTION_CODE,
            source="invariant",
            default_code=INVARIANT_FAILURE_CODE,
        )

    if source_code in {
        REVISION_MISMATCH_CODE,
        IDEMPOTENCY_CONFLICT_CODE,
        VALIDATION_FAILURE_CODE,
    }:
        return structural_pre_step_runtime_error(
            error=error,
            code=STRUCTURAL_PRE_STEP_BARRIER_REJECTION_CODE,
            source="barrier",
            default_code=VALIDATION_FAILURE_CODE,
        )

    return structural_pre_step_runtime_error(
        error=error,
        code=STRUCTURAL_PRE_STEP_BARRIER_REJECTION_CODE,
        source="barrier",
        default_code=VALIDATION_FAILURE_CODE,
    )


def translate_hydraulic_failure(error: BaseException) -> DiagnosticRuntimeError:
    return structural_pre_step_runtime_error(
        error=error,
        code=STRUCTURAL_PRE_STEP_HYDRAULIC_REJECTION_CODE,
        source="hydraulic",
        default_code=VALIDATION_FAILURE_CODE,
        path="hydraulic.solve",
        hint="fix the hydraulic structure before retrying the pre-step macro-step",
    )


def _structural_payload(
    *,
    error: BaseException,
    code: str,
    source: str,
    default_code: str,
    path: str | None,
    hint: str | None,
) -> DiagnosticPayload:
    source_payload = coerce_diagnostic_payload(
        error=error,
        default_code=default_code,
        path=path,
        hint=hint,
    )
    payload = dict(source_payload)
    payload["source_code"] = _source_code_value(error=error, source_payload=source_payload)
    payload["code"] = code
    payload["failure_family"] = STRUCTURAL_REJECTION_FAMILY
    payload["rejection_stage"] = STRUCTURAL_PRE_STEP_REJECTION_STAGE
    payload["rejection_source"] = source
    return payload


def _source_code_value(
    *, error: BaseException, source_payload: DiagnosticPayload
) -> str | tuple[str, ...] | None:
    if isinstance(error, GraphCompileError):
        return tuple(diagnostic.code for diagnostic in error.diagnostics)
    code = source_payload.get("code")
    return code if isinstance(code, str) else None


__all__ = [
    "STRUCTURAL_PRE_STEP_BARRIER_REJECTION_CODE",
    "STRUCTURAL_PRE_STEP_COMPILE_REJECTION_CODE",
    "STRUCTURAL_PRE_STEP_HYDRAULIC_REJECTION_CODE",
    "STRUCTURAL_PRE_STEP_INVARIANT_REJECTION_CODE",
    "STRUCTURAL_PRE_STEP_REJECTION_STAGE",
    "STRUCTURAL_REJECTION_FAMILY",
    "structural_pre_step_runtime_error",
    "translate_barrier_failure",
    "translate_hydraulic_failure",
]
