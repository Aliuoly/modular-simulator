from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias, cast

VALIDATION_FAILURE_CODE = "VALIDATION_FAILURE"
INVARIANT_FAILURE_CODE = "INVARIANT_FAILURE"
REVISION_MISMATCH_CODE = "REVISION_MISMATCH"
IDEMPOTENCY_CONFLICT_CODE = "IDEMPOTENCY_CONFLICT"
COMPATIBILITY_FAILURE_CODE = "COMPATIBILITY_FAILURE"
CLI_ARGUMENT_ISSUE_CODE = "CLI_ARGUMENT_ISSUE"


RevisionDetails: TypeAlias = dict[str, str | None]
DiagnosticPayload: TypeAlias = dict[str, object]


def revision_details(*, expected: object, actual: object) -> RevisionDetails:
    return {
        "expected": None if expected is None else str(expected),
        "actual": None if actual is None else str(actual),
    }


def build_diagnostic_payload(
    *,
    code: str,
    message: str,
    path: str | None = None,
    hint: str | None = None,
    revision: RevisionDetails | None = None,
) -> DiagnosticPayload:
    return {
        "code": code,
        "message": message,
        "path": path,
        "hint": hint,
        "revision": revision,
    }


class DiagnosticValueError(ValueError):
    payload: DiagnosticPayload

    def __init__(self, payload: DiagnosticPayload) -> None:
        self.payload = payload
        super().__init__(str(payload.get("message", "diagnostic error")))


class DiagnosticRuntimeError(RuntimeError):
    payload: DiagnosticPayload

    def __init__(self, payload: DiagnosticPayload) -> None:
        self.payload = payload
        super().__init__(str(payload.get("message", "diagnostic error")))


def diagnostic_value_error(
    *,
    code: str,
    message: str,
    path: str | None = None,
    hint: str | None = None,
    revision: RevisionDetails | None = None,
) -> DiagnosticValueError:
    return DiagnosticValueError(
        build_diagnostic_payload(
            code=code,
            message=message,
            path=path,
            hint=hint,
            revision=revision,
        )
    )


def diagnostic_runtime_error(
    *,
    code: str,
    message: str,
    path: str | None = None,
    hint: str | None = None,
    revision: RevisionDetails | None = None,
) -> DiagnosticRuntimeError:
    return DiagnosticRuntimeError(
        build_diagnostic_payload(
            code=code,
            message=message,
            path=path,
            hint=hint,
            revision=revision,
        )
    )


def extract_diagnostic_payload(error: BaseException) -> DiagnosticPayload | None:
    stack: list[BaseException] = [error]
    visited: set[int] = set()
    while stack:
        current = stack.pop()
        current_id = id(current)
        if current_id in visited:
            continue
        visited.add(current_id)

        payload = _normalize_payload(getattr(current, "payload", None))
        if payload is not None:
            return payload

        if current.__cause__ is not None:
            stack.append(current.__cause__)
        if current.__context__ is not None:
            stack.append(current.__context__)
    return None


def coerce_diagnostic_payload(
    *,
    error: BaseException,
    default_code: str,
    message: str | None = None,
    path: str | None = None,
    hint: str | None = None,
    revision: RevisionDetails | None = None,
) -> DiagnosticPayload:
    payload = extract_diagnostic_payload(error)
    if payload is None:
        return build_diagnostic_payload(
            code=default_code,
            message=str(error) if message is None else message,
            path=path,
            hint=hint,
            revision=revision,
        )

    extras = {
        key: value
        for key, value in payload.items()
        if key not in {"code", "message", "path", "hint", "revision"}
    }

    payload_code = payload.get("code")
    resolved_code = payload_code if isinstance(payload_code, str) else default_code

    payload_message = payload.get("message")
    resolved_message = payload_message if isinstance(payload_message, str) else str(error)
    if message is not None:
        resolved_message = message

    payload_path = payload.get("path")
    resolved_path = payload_path if isinstance(payload_path, str) else None
    if path is not None:
        resolved_path = path

    payload_hint = payload.get("hint")
    resolved_hint = payload_hint if isinstance(payload_hint, str) else None
    if hint is not None:
        resolved_hint = hint

    payload_revision = _normalize_revision(payload.get("revision"))
    resolved_revision = payload_revision if revision is None else revision

    coerced = build_diagnostic_payload(
        code=resolved_code,
        message=resolved_message,
        path=resolved_path,
        hint=resolved_hint,
        revision=resolved_revision,
    )
    coerced.update(extras)
    return coerced


def _normalize_payload(payload: object) -> DiagnosticPayload | None:
    if not isinstance(payload, Mapping):
        return None
    mapping_payload = cast(Mapping[str, object], payload)

    code = mapping_payload.get("code")
    message = mapping_payload.get("message")
    if not isinstance(code, str) or not isinstance(message, str):
        return None

    path_raw = mapping_payload.get("path")
    path: str | None
    if path_raw is None:
        path = None
    elif isinstance(path_raw, str):
        path = path_raw
    else:
        path = str(path_raw)

    hint_raw = mapping_payload.get("hint")
    hint: str | None
    if hint_raw is None:
        hint = None
    elif isinstance(hint_raw, str):
        hint = hint_raw
    else:
        hint = str(hint_raw)

    revision = _normalize_revision(mapping_payload.get("revision"))
    normalized = build_diagnostic_payload(
        code=code,
        message=message,
        path=path,
        hint=hint,
        revision=revision,
    )
    normalized.update(
        {
            key: value
            for key, value in mapping_payload.items()
            if key not in {"code", "message", "path", "hint", "revision"}
        }
    )
    return normalized


def _normalize_revision(value: object) -> RevisionDetails | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        return None
    return revision_details(expected=value.get("expected"), actual=value.get("actual"))


__all__ = [
    "CLI_ARGUMENT_ISSUE_CODE",
    "COMPATIBILITY_FAILURE_CODE",
    "DiagnosticPayload",
    "DiagnosticRuntimeError",
    "DiagnosticValueError",
    "IDEMPOTENCY_CONFLICT_CODE",
    "INVARIANT_FAILURE_CODE",
    "REVISION_MISMATCH_CODE",
    "RevisionDetails",
    "VALIDATION_FAILURE_CODE",
    "build_diagnostic_payload",
    "coerce_diagnostic_payload",
    "diagnostic_runtime_error",
    "diagnostic_value_error",
    "extract_diagnostic_payload",
    "revision_details",
]
