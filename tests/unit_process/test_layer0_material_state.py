# pyright: reportMissingTypeStubs=false, reportMissingImports=false

import pytest
from pydantic import ValidationError

from modular_simulation.connection.state import MaterialState, PortCondition


def test_material_state_canonical_constructor_remains_valid() -> None:
    state = MaterialState(
        pressure=101325.0,
        temperature=298.15,
        mole_fractions=(0.8, 0.2),
    )

    assert state.species_ids is None
    assert not state.has_thermo_metadata


def test_material_state_enhanced_constructor_supports_thermo_metadata() -> None:
    state = MaterialState(
        pressure=101325.0,
        temperature=298.15,
        mole_fractions=(0.5, 0.5),
        species_ids=("7732-18-5", "64-17-5"),
        phase="liquid",
        enthalpy_molar=-285830.0,
        entropy_molar=69.95,
    )

    assert state.has_thermo_metadata
    assert state.phase == "liquid"
    assert state.enthalpy_molar == -285830.0
    assert state.entropy_molar == 69.95


def test_material_state_species_length_mismatch_fails_validation() -> None:
    with pytest.raises(
        ValidationError, match="species_ids length must match mole_fractions length"
    ):
        _ = MaterialState(
            pressure=101325.0,
            temperature=298.15,
            mole_fractions=(0.5, 0.5),
            species_ids=("7732-18-5",),
        )


def test_material_state_with_thermo_preserves_base_fields() -> None:
    base = MaterialState(
        pressure=101325.0,
        temperature=298.15,
        mole_fractions=(0.4, 0.6),
    )
    enhanced = base.with_thermo(
        species_ids=("7732-18-5", "64-17-5"),
        phase="two-phase",
        enthalpy_molar=-15000.0,
        entropy_molar=120.0,
    )

    assert base.species_ids is None
    assert enhanced.species_ids == ("7732-18-5", "64-17-5")
    assert enhanced.phase == "two-phase"
    assert enhanced.pressure == base.pressure
    assert enhanced.temperature == base.temperature
    assert enhanced.mole_fractions == base.mole_fractions


def test_material_state_from_legacy_constructor_is_absent() -> None:
    assert not hasattr(MaterialState, "from_legacy")

    with pytest.raises(AttributeError, match="from_legacy"):
        _ = getattr(MaterialState, "from_legacy")


def test_material_state_equality_and_hash_include_thermo_fields() -> None:
    base = MaterialState(
        pressure=101325.0,
        temperature=298.15,
        mole_fractions=(0.5, 0.5),
        species_ids=("7732-18-5", "64-17-5"),
        phase="liquid",
    )
    same = MaterialState(
        pressure=101325.0,
        temperature=298.15,
        mole_fractions=(0.5, 0.5),
        species_ids=("7732-18-5", "64-17-5"),
        phase="liquid",
    )
    different = MaterialState(
        pressure=101325.0,
        temperature=298.15,
        mole_fractions=(0.5, 0.5),
        species_ids=("7732-18-5", "64-17-5"),
        phase="vapor",
    )

    assert base == same
    assert hash(base) == hash(same)
    assert base != different


def test_port_condition_supports_optional_species_ids() -> None:
    state = MaterialState(
        pressure=101325.0,
        temperature=298.15,
        mole_fractions=(0.3, 0.7),
    )
    port = PortCondition(
        state=state,
        species_ids=("7732-18-5", "64-17-5"),
        through_molar_flow_rate=1.2,
    )

    assert port.species_ids == ("7732-18-5", "64-17-5")


def test_port_condition_species_length_mismatch_fails_validation() -> None:
    state = MaterialState(
        pressure=101325.0,
        temperature=298.15,
        mole_fractions=(0.3, 0.7),
    )

    with pytest.raises(
        ValidationError, match="species_ids length must match state.mole_fractions length"
    ):
        _ = PortCondition(
            state=state,
            species_ids=("7732-18-5",),
            through_molar_flow_rate=1.2,
        )
