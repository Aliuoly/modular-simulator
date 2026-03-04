# pyright: reportMissingTypeStubs=false

import math
from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from modular_simulation.thermodynamics.kinetics import (
    ArrheniusRateLaw,
    EquilibriumConstantLaw,
    PowerLawRateLaw,
    RateLaw,
    Reaction,
    ReactionSet,
)


def test_arrhenius_rate_matches_manual_calculation() -> None:
    law = ArrheniusRateLaw(
        pre_exponential=1.0e10,
        activation_energy=80_000.0,
        orders={"A": 1.0},
        key_species="A",
    )

    temperature = 350.0
    concentrations = {"A": 1.5, "B": 0.5}
    result = law.rate(concentrations, temperature)

    expected = 1.0e10 * math.exp(-80_000.0 / (8.314 * temperature)) * 1.5
    assert math.isclose(result["A"], expected, rel_tol=1.0e-10)


def test_power_law_rate_matches_expected_value_with_temperature_correction() -> None:
    law = PowerLawRateLaw(
        k_ref=0.5,
        T_ref=300.0,
        E_a=20_000.0,
        orders={"A": 1.0, "B": 0.5},
        key_species="A",
    )

    temperature = 330.0
    concentrations = {"A": 2.0, "B": 9.0}
    result = law.rate(concentrations, temperature)

    expected_k: float = 0.5 * math.exp((-20_000.0 / 8.314) * ((1.0 / 330.0) - (1.0 / 300.0)))
    expected: float = expected_k * 2.0 * math.sqrt(9.0)
    assert math.isclose(result["A"], expected)


def test_reaction_set_sums_multiple_reaction_contributions_in_order() -> None:
    reaction_one = Reaction(
        name="A->B",
        stoichiometry={"A": -1.0, "B": 1.0},
        rate_law=PowerLawRateLaw(k_ref=0.5, orders={"A": 1.0}, key_species="A"),
    )
    reaction_two = Reaction(
        name="B->C",
        stoichiometry={"B": -1.0, "C": 1.0},
        rate_law=PowerLawRateLaw(k_ref=0.3, orders={"B": 1.0}, key_species="B"),
    )

    reaction_set = ReactionSet(reactions=[reaction_one, reaction_two])
    rates = reaction_set.net_rates({"A": 2.0, "B": 1.0, "C": 0.0}, 300.0)

    assert math.isclose(rates["A"], -1.0)
    assert math.isclose(rates["B"], 0.7)
    assert math.isclose(rates["C"], 0.3)
    assert list(rates.keys()) == ["A", "B", "C"]


def test_protocol_accepts_callable_with_matching_signature() -> None:
    @dataclass(frozen=True)
    class ConstantLaw:
        def rate(self, concentrations: Mapping[str, float], temperature: float) -> dict[str, float]:
            del concentrations, temperature
            return {"A": 2.0}

    custom_law: RateLaw = ConstantLaw()
    reaction_set = ReactionSet(
        reactions=[Reaction(name="A->B", stoichiometry={"A": -1.0, "B": 1.0}, rate_law=custom_law)]
    )

    rates = reaction_set.net_rates({"A": 5.0}, 298.15)
    assert math.isclose(rates["A"], -2.0)
    assert math.isclose(rates["B"], 2.0)


def test_rate_laws_handle_missing_concentrations_and_zero_temperature_stably() -> None:
    law = ArrheniusRateLaw(
        pre_exponential=10.0,
        activation_energy=1_000.0,
        orders={"A": 1.0, "B": 2.0},
        key_species="A",
    )

    result = law.rate({"A": 1.0}, 0.0)
    assert math.isclose(result["A"], 0.0)


def test_negative_order_requires_positive_concentration() -> None:
    law = PowerLawRateLaw(k_ref=1.0, orders={"A": -1.0}, key_species="A")

    with pytest.raises(ValueError, match="must be positive"):
        _ = law.rate({}, 300.0)


def test_reaction_set_rejects_ambiguous_multi_term_rate_law_output() -> None:
    @dataclass(frozen=True)
    class AmbiguousLaw:
        def rate(self, concentrations: Mapping[str, float], temperature: float) -> dict[str, float]:
            del concentrations, temperature
            return {"r_forward": 1.0, "r_reverse": 0.5}

    reaction = Reaction(name="A<->B", stoichiometry={"A": -1.0, "B": 1.0}, rate_law=AmbiguousLaw())
    reaction_set = ReactionSet(reactions=[reaction])

    with pytest.raises(ValueError, match="exactly one rate term"):
        _ = reaction_set.net_rates({"A": 1.0, "B": 1.0}, 300.0)


def test_equilibrium_constant_law_computes_net_rate_from_forward_rate() -> None:
    forward_law = PowerLawRateLaw(k_ref=2.0, orders={"A": 1.0}, key_species="A")
    equilibrium_law = EquilibriumConstantLaw(
        K_eq=lambda temperature: 5.0 + 0.0 * temperature,
        forward_rate_law=forward_law,
        key_species="A",
    )

    result = equilibrium_law.rate({"A": 1.5}, 320.0)
    assert math.isclose(result["A"], 2.4)
