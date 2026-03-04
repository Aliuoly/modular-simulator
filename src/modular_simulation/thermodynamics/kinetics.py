from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import exp, pow
from typing import Literal, Protocol

_MIN_TEMPERATURE_K = 1.0e-9
_MIN_EQUILIBRIUM_CONSTANT = 1.0e-12
_EXPONENT_ARGUMENT_LIMIT = 700.0


class RateLaw(Protocol):
    def rate(self, concentrations: Mapping[str, float], temperature: float) -> dict[str, float]: ...


def _bounded_exponential(exponent_argument: float) -> float:
    limited_argument = max(
        -_EXPONENT_ARGUMENT_LIMIT, min(_EXPONENT_ARGUMENT_LIMIT, exponent_argument)
    )
    return exp(limited_argument)


def _safe_temperature_kelvin(temperature: float) -> float:
    return max(_MIN_TEMPERATURE_K, temperature)


def _rate_concentration_term(
    concentrations: Mapping[str, float], orders: Mapping[str, float]
) -> float:
    concentration_term = 1.0
    for species_name, order in orders.items():
        concentration = max(0.0, concentrations.get(species_name, 0.0))
        if concentration == 0.0:
            if order < 0.0:
                raise ValueError(
                    f"Concentration for species '{species_name}' must be positive for negative reaction order."
                )
            if order == 0.0:
                continue
            return 0.0
        concentration_term *= pow(concentration, float(order))
    return concentration_term


@dataclass(frozen=True)
class Reaction:
    name: str
    stoichiometry: Mapping[str, float]
    rate_law: RateLaw
    basis: Literal["concentration", "partial_pressure"] = "concentration"

    def __post_init__(self) -> None:
        if not self.stoichiometry:
            raise ValueError("Reaction stoichiometry cannot be empty.")


@dataclass(frozen=True)
class ReactionSet:
    reactions: Sequence[Reaction]

    def net_rates(
        self, concentrations: Mapping[str, float], temperature: float
    ) -> dict[str, float]:
        net_species_rates: dict[str, float] = {}
        for reaction in self.reactions:
            reaction_rate_terms = reaction.rate_law.rate(concentrations, temperature)
            if not reaction_rate_terms:
                raise ValueError(f"Reaction '{reaction.name}' returned no rate terms.")
            if len(reaction_rate_terms) != 1:
                raise ValueError(
                    f"Reaction '{reaction.name}' must return exactly one rate term for stoichiometric aggregation."
                )

            reaction_rate = next(iter(reaction_rate_terms.values()))
            for species_name, coefficient in reaction.stoichiometry.items():
                contribution = coefficient * reaction_rate
                if species_name in net_species_rates:
                    net_species_rates[species_name] += contribution
                else:
                    net_species_rates[species_name] = contribution

        return net_species_rates


@dataclass(frozen=True)
class ArrheniusRateLaw:
    pre_exponential: float
    activation_energy: float
    orders: Mapping[str, float]
    key_species: str
    gas_constant: float = 8.314

    def __post_init__(self) -> None:
        if self.pre_exponential < 0.0:
            raise ValueError("pre_exponential must be non-negative.")
        if self.gas_constant <= 0.0:
            raise ValueError("gas_constant must be positive.")

    def rate(self, concentrations: Mapping[str, float], temperature: float) -> dict[str, float]:
        temperature_kelvin = _safe_temperature_kelvin(temperature)
        arrhenius_term = _bounded_exponential(
            -self.activation_energy / (self.gas_constant * temperature_kelvin)
        )
        concentration_term = _rate_concentration_term(concentrations, self.orders)
        reaction_rate = self.pre_exponential * arrhenius_term * concentration_term
        return {self.key_species: reaction_rate}


@dataclass(frozen=True)
class PowerLawRateLaw:
    k_ref: float
    orders: Mapping[str, float]
    key_species: str
    T_ref: float = 298.15
    E_a: float | None = None
    gas_constant: float = 8.314

    def __post_init__(self) -> None:
        if self.k_ref < 0.0:
            raise ValueError("k_ref must be non-negative.")
        if self.T_ref <= 0.0:
            raise ValueError("T_ref must be positive.")
        if self.gas_constant <= 0.0:
            raise ValueError("gas_constant must be positive.")

    def rate(self, concentrations: Mapping[str, float], temperature: float) -> dict[str, float]:
        concentration_term = _rate_concentration_term(concentrations, self.orders)

        rate_constant = self.k_ref
        if self.E_a is not None:
            temperature_kelvin = _safe_temperature_kelvin(temperature)
            correction_exponent = (-self.E_a / self.gas_constant) * (
                (1.0 / temperature_kelvin) - (1.0 / self.T_ref)
            )
            rate_constant *= _bounded_exponential(correction_exponent)

        return {self.key_species: rate_constant * concentration_term}


@dataclass(frozen=True)
class EquilibriumConstantLaw:
    K_eq: Callable[[float], float]
    forward_rate_law: RateLaw
    key_species: str
    minimum_equilibrium_constant: float = _MIN_EQUILIBRIUM_CONSTANT

    def __post_init__(self) -> None:
        if self.minimum_equilibrium_constant <= 0.0:
            raise ValueError("minimum_equilibrium_constant must be positive.")

    def rate(self, concentrations: Mapping[str, float], temperature: float) -> dict[str, float]:
        forward_terms = self.forward_rate_law.rate(concentrations, temperature)
        if self.key_species not in forward_terms:
            raise ValueError(
                f"Forward rate law did not return required key species '{self.key_species}'."
            )

        forward_rate = forward_terms[self.key_species]
        equilibrium_constant = max(self.minimum_equilibrium_constant, self.K_eq(temperature))
        reverse_rate = forward_rate / equilibrium_constant
        return {self.key_species: forward_rate - reverse_rate}


__all__ = [
    "ArrheniusRateLaw",
    "EquilibriumConstantLaw",
    "PowerLawRateLaw",
    "RateLaw",
    "Reaction",
    "ReactionSet",
]
