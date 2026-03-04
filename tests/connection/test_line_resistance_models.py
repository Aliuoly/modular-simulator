from __future__ import annotations

import pytest

from modular_simulation.connection.domain_contracts import ResistanceConfig
from modular_simulation.connection.hydraulic_compile import (
    GraphCompileDiagnostic,
    GraphCompileError,
    resolve_line_resistance,
)


def test_resistance_is_derived_from_geometry_with_provenance() -> None:
    resistance = ResistanceConfig(mode="derived", radius_m=0.05, length_m=2.0)

    resolved = resolve_line_resistance(line_id="line_feed", resistance=resistance)
    expected_derived = 2.0 / (0.05**4)

    assert resolved.line_id == "line_feed"
    assert abs(resolved.active_value - expected_derived) < 1.0e-12
    assert abs(resolved.derived_value - expected_derived) < 1.0e-12
    assert resolved.provenance == "derived"


def test_manual_override_precedence_is_deterministic_when_provided() -> None:
    resistance = ResistanceConfig(
        mode="derived",
        radius_m=0.05,
        length_m=2.0,
        manual_value=12_500.0,
    )

    resolved = resolve_line_resistance(line_id="line_feed", resistance=resistance)
    expected_derived = 2.0 / (0.05**4)

    assert abs(resolved.active_value - 12_500.0) < 1.0e-12
    assert abs(resolved.derived_value - expected_derived) < 1.0e-12
    assert resolved.provenance == "manual_override"


@pytest.mark.parametrize(
    ("radius_m", "length_m", "expected_detail_key"),
    (
        (0.0, 1.0, "radius_m"),
        (1.0, 0.0, "length_m"),
    ),
)
def test_invalid_geometry_is_rejected_with_structured_deterministic_error(
    radius_m: float,
    length_m: float,
    expected_detail_key: str,
) -> None:
    invalid_config = ResistanceConfig.model_construct(
        mode="derived",
        radius_m=radius_m,
        length_m=length_m,
        manual_value=None,
    )

    runs: list[tuple[GraphCompileDiagnostic, ...]] = []
    for _ in range(2):
        with pytest.raises(GraphCompileError) as error:
            _ = resolve_line_resistance(line_id="line_invalid", resistance=invalid_config)
        runs.append(error.value.diagnostics)

    assert runs[0] == runs[1]
    diagnostic = runs[0][0]
    assert diagnostic.code == "invalid_line_geometry"
    assert ("line_id", "line_invalid") in diagnostic.details
    assert any(detail_key == expected_detail_key for detail_key, _ in diagnostic.details)
