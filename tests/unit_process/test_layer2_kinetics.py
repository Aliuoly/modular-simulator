# pyright: reportMissingTypeStubs=false, reportMissingImports=false

import math
from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from modular_simulation.thermodynamics import (
    ArrheniusRateLaw,
    PowerLawRateLaw,
    RateLaw,
    Reaction,
    ReactionSet,
)


@dataclass(frozen=True)
class ConstantRateLaw(RateLaw):
    rate_value: float

    def rate(self, concentrations: Mapping[str, float], temperature: float) -> float:
        del concentrations, temperature
        return self.rate_value


def test_arrhenius_rate_matches_manual_calculation() -> None:
    law = ArrheniusRateLaw(
        pre_exponential=1.0e10,
        activation_energy=80_000.0,
        orders={"A": 1.0},
    )

    temperature = 350.0
    concentrations = {"A": 1.5, "B": 0.5}
    result = law.rate(concentrations, temperature)

    expected = 1.0e10 * math.exp(-80_000.0 / (8.314 * temperature)) * 1.5
    assert math.isclose(result, expected, rel_tol=1.0e-10)


def test_power_law_rate_matches_expected_value_with_temperature_correction() -> None:
    law = PowerLawRateLaw(
        k_ref=0.5,
        T_ref=300.0,
        E_a=20_000.0,
        orders={"A": 1.0, "B": 0.5},
    )

    temperature = 330.0
    concentrations = {"A": 2.0, "B": 9.0}
    result = law.rate(concentrations, temperature)

    expected_k: float = 0.5 * math.exp((-20_000.0 / 8.314) * ((1.0 / 330.0) - (1.0 / 300.0)))
    expected: float = expected_k * 2.0 * math.sqrt(9.0)
    assert math.isclose(result, expected)


def test_reaction_set_sums_multiple_reaction_contributions_in_order() -> None:
    reaction_one = Reaction(
        name="A->B",
        stoichiometry={"A": -1.0, "B": 1.0},
        rate_law=PowerLawRateLaw(k_ref=0.5, orders={"A": 1.0}),
    )
    reaction_two = Reaction(
        name="B->C",
        stoichiometry={"B": -1.0, "C": 1.0},
        rate_law=PowerLawRateLaw(k_ref=0.3, orders={"B": 1.0}),
    )

    reaction_set = ReactionSet(reactions=[reaction_one, reaction_two])
    rates = reaction_set.net_rates({"A": 2.0, "B": 1.0, "C": 0.0}, 300.0)

    assert math.isclose(rates["A"], -1.0)
    assert math.isclose(rates["B"], 0.7)
    assert math.isclose(rates["C"], 0.3)
    assert list(rates.keys()) == ["A", "B", "C"]


def test_reaction_set_accepts_nominal_rate_law_subclass() -> None:
    custom_law: RateLaw = ConstantRateLaw(rate_value=2.0)
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
    )

    result = law.rate({"A": 1.0}, 0.0)
    assert math.isclose(result, 0.0)


def test_negative_order_requires_positive_concentration() -> None:
    law = PowerLawRateLaw(k_ref=1.0, orders={"A": -1.0})

    with pytest.raises(ValueError, match="must be positive"):
        _ = law.rate({}, 300.0)


def test_reaction_equilibrium_constant_computes_net_rate_from_forward_rate() -> None:
    equilibrium_reaction = Reaction(
        name="A<->B",
        stoichiometry={"A": -1.0, "B": 1.0},
        rate_law=PowerLawRateLaw(k_ref=2.0, orders={"A": 1.0}),
        equilibrium_constant=lambda temperature: 5.0 + 0.0 * temperature,
    )

    result = equilibrium_reaction.rate({"A": 1.5}, 320.0)
    assert math.isclose(result, 2.4)


def test_reaction_supports_explicit_reverse_rate_law() -> None:
    reaction = Reaction(
        name="A<->B",
        stoichiometry={"A": -1.0, "B": 1.0},
        rate_law=PowerLawRateLaw(k_ref=2.0, orders={"A": 1.0}),
        reverse_rate_law=PowerLawRateLaw(k_ref=0.5, orders={"B": 1.0}),
    )

    result = reaction.rate({"A": 1.5, "B": 0.4}, 320.0)
    assert math.isclose(result, 2.8)


def test_reaction_rejects_ambiguous_reversible_configuration() -> None:
    with pytest.raises(
        ValueError, match="provide only one of reverse_rate_law or equilibrium_constant"
    ):
        _ = Reaction(
            name="A<->B",
            stoichiometry={"A": -1.0, "B": 1.0},
            rate_law=PowerLawRateLaw(k_ref=2.0, orders={"A": 1.0}),
            reverse_rate_law=PowerLawRateLaw(k_ref=0.5, orders={"B": 1.0}),
            equilibrium_constant=lambda temperature: 5.0 + 0.0 * temperature,
        )
