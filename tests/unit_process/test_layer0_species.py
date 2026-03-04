# pyright: reportMissingTypeStubs=false

import math

import numpy as np
import pytest

from modular_simulation.thermodynamics.species import (
    ActiveSpeciesRegistry,
    SimulationSpeciesContext,
    resolve_species,
)


def test_resolve_species_round_trip_name_and_cas() -> None:
    water_by_name = resolve_species("water")
    water_by_cas = resolve_species("7732-18-5")

    assert water_by_name == water_by_cas
    assert water_by_name.cas == "7732-18-5"
    assert water_by_name.name == "water"
    assert math.isclose(water_by_name.mw, 18.015, rel_tol=5.0e-3)


def test_active_species_registry_construction_and_indexing() -> None:
    registry = ActiveSpeciesRegistry.from_names(["water", "ethanol", "methane"])

    assert registry.n_species == 3
    assert registry.contains("water")
    assert registry.index_of("water") == registry.index_of("7732-18-5")
    assert registry.cas_list == ("7732-18-5", "64-17-5", "74-82-8")
    assert tuple(np.round(registry.mw_array, 2)) == (18.02, 46.07, 16.04)


def test_species_projection_subsets_and_expands_composition_vectors() -> None:
    global_registry = ActiveSpeciesRegistry.from_names(["water", "ethanol", "methane"])
    local_registry = ActiveSpeciesRegistry.from_names(["ethanol", "methane"])
    projection = global_registry.get_projection_for(local_registry)

    global_fractions = np.array([0.1, 0.6, 0.3], dtype=float)
    local_fractions = projection.to_local(global_fractions)
    expanded = projection.to_global(np.array([0.6, 0.4], dtype=float))

    assert np.allclose(local_fractions, np.array([0.6, 0.3]))
    assert np.allclose(expanded, np.array([0.0, 0.6, 0.4]))


def test_projection_validates_vector_lengths() -> None:
    global_registry = ActiveSpeciesRegistry.from_names(["water", "ethanol", "methane"])
    local_registry = ActiveSpeciesRegistry.from_names(["ethanol", "methane"])
    projection = global_registry.get_projection_for(local_registry)

    with pytest.raises(ValueError, match="Global fraction vector length mismatch"):
        _ = projection.to_local(np.array([0.7, 0.3], dtype=float))

    with pytest.raises(ValueError, match="Local fraction vector length mismatch"):
        _ = projection.to_global(np.array([0.7, 0.2, 0.1], dtype=float))


def test_simulation_species_context_registers_and_retrieves_projection() -> None:
    global_registry = ActiveSpeciesRegistry.from_names(["water", "ethanol", "methane"])
    context = SimulationSpeciesContext(registry=global_registry)

    context.register_subsystem("reactor", ["ethanol", "methane"])
    projection = context.get_projection("reactor")

    global_z = projection.to_global(np.array([0.6, 0.4], dtype=float))
    assert np.allclose(global_z, np.array([0.0, 0.6, 0.4]))


def test_resolve_species_invalid_identifier_has_actionable_error() -> None:
    with pytest.raises(ValueError, match="Unable to resolve species 'notachemical'"):
        _ = resolve_species("notachemical")

    with pytest.raises(ValueError, match="Formula-only lookup can be ambiguous"):
        _ = resolve_species("C999H999")
