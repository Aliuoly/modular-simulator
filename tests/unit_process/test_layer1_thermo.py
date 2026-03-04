# pyright: reportMissingTypeStubs=false

import math

from modular_simulation.thermodynamics.property_package import (
    PengRobinsonPackage,
    create_property_package,
)
from modular_simulation.thermodynamics.species import ActiveSpeciesRegistry


def test_flash_tp_returns_physically_valid_result() -> None:
    package = PengRobinsonPackage(species_ids=("7732-18-5", "64-17-5"))
    result = package.flash_tp(T=350.0, P=101_325.0, z=(0.5, 0.5))

    assert result.phase in {"vapor", "liquid", "two-phase"}
    assert 0.0 <= result.vapor_fraction <= 1.0
    assert math.isfinite(result.enthalpy_molar)
    assert math.isfinite(result.entropy_molar)

    if result.vapor_composition is not None:
        assert math.isclose(sum(result.vapor_composition), 1.0, rel_tol=0.0, abs_tol=1.0e-6)

    if result.liquid_composition is not None:
        assert math.isclose(sum(result.liquid_composition), 1.0, rel_tol=0.0, abs_tol=1.0e-6)

    if result.vapor_density is not None:
        assert result.vapor_density > 0.0

    if result.liquid_density is not None:
        assert result.liquid_density > 0.0


def test_flash_ph_round_trip_matches_flash_tp_temperature() -> None:
    package = PengRobinsonPackage(species_ids=("7732-18-5", "64-17-5"))

    reference = package.flash_tp(T=350.0, P=101_325.0, z=(0.5, 0.5))
    from_enthalpy = package.flash_ph(P=101_325.0, H=reference.enthalpy_molar, z=(0.5, 0.5))

    assert abs(reference.temperature - from_enthalpy.temperature) < 0.1


def test_flash_ps_round_trip_matches_flash_tp_temperature() -> None:
    package = PengRobinsonPackage(species_ids=("7732-18-5", "64-17-5"))

    reference = package.flash_tp(T=350.0, P=101_325.0, z=(0.5, 0.5))
    from_entropy = package.flash_ps(P=101_325.0, S=reference.entropy_molar, z=(0.5, 0.5))

    assert abs(reference.temperature - from_entropy.temperature) < 0.1


def test_flash_methods_expose_cache_info_with_hits() -> None:
    package = PengRobinsonPackage(species_ids=("7732-18-5", "64-17-5"))

    _ = package.flash_tp(T=350.0, P=101_325.0, z=(0.5, 0.5))
    _ = package.flash_tp(T=350.0, P=101_325.0, z=(0.5, 0.5))

    info = package.flash_tp.cache_info()
    assert info.hits >= 1
    assert info.maxsize == 128


def test_pure_water_near_boiling_condition_returns_high_vapor_fraction() -> None:
    package = PengRobinsonPackage(species_ids=("7732-18-5",))
    result = package.flash_tp(T=375.0, P=101_325.0, z=(1.0,))

    assert result.vapor_fraction >= 0.95
    assert result.phase in {"vapor", "two-phase"}


def test_scalar_helpers_and_factory_use_registry_cas_ordering() -> None:
    registry = ActiveSpeciesRegistry.from_names(["water", "ethanol"])
    package = create_property_package(registry, model="PR")

    assert package.species_cas == registry.cas_list

    mw = package.molecular_weight((0.5, 0.5))
    assert 30.0 < mw < 35.0

    h = package.enthalpy(T=350.0, P=101_325.0, z=(0.5, 0.5), phase="two-phase")
    s = package.entropy(T=350.0, P=101_325.0, z=(0.5, 0.5), phase="two-phase")
    rho_l = package.density(T=350.0, P=101_325.0, z=(0.5, 0.5), phase="liquid")
    cp_v = package.heat_capacity_cp(T=350.0, P=101_325.0, z=(0.5, 0.5), phase="vapor")

    assert math.isfinite(h)
    assert math.isfinite(s)
    assert rho_l > 0.0
    assert cp_v > 0.0
