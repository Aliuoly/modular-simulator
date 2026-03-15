from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import exp, pow
from typing import Literal

_MIN_TEMPERATURE_K = 1.0e-9
_MIN_EQUILIBRIUM_CONSTANT = 1.0e-12
_EXPONENT_ARGUMENT_LIMIT = 700.0


class RateLaw(ABC):
    """Nominal scalar rate law for a single reaction."""

    @abstractmethod
    def rate(self, concentrations: Mapping[str, float], temperature: float) -> float:
        pass


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
    reverse_rate_law: RateLaw | None = None
    equilibrium_constant: Callable[[float], float] | None = None
    basis: Literal["concentration", "partial_pressure"] = "concentration"

    def __post_init__(self) -> None:
        if not self.stoichiometry:
            raise ValueError("Reaction stoichiometry cannot be empty.")

        if self.reverse_rate_law is not None and self.equilibrium_constant is not None:
            raise ValueError(
                "Reaction reversible configuration is ambiguous; provide only one of reverse_rate_law or equilibrium_constant."
            )

    def rate(self, concentrations: Mapping[str, float], temperature: float) -> float:
        forward_rate = self.rate_law.rate(concentrations, temperature)

        if self.reverse_rate_law is not None:
            return forward_rate - self.reverse_rate_law.rate(concentrations, temperature)

        if self.equilibrium_constant is not None:
            equilibrium_constant = max(
                _MIN_EQUILIBRIUM_CONSTANT,
                self.equilibrium_constant(temperature),
            )
            reverse_rate = forward_rate / equilibrium_constant
            return forward_rate - reverse_rate

        return forward_rate


@dataclass(frozen=True)
class ReactionSet:
    reactions: Sequence[Reaction]

    def net_rates(
        self, concentrations: Mapping[str, float], temperature: float
    ) -> dict[str, float]:
        """Aggregate scalar per-reaction rates into net species rates."""
        net_species_rates: dict[str, float] = {}
        for reaction in self.reactions:
            reaction_rate = reaction.rate(concentrations, temperature)
            for species_name, coefficient in reaction.stoichiometry.items():
                net_species_rates[species_name] = net_species_rates.get(species_name, 0.0) + (
                    coefficient * reaction_rate
                )

        return net_species_rates


@dataclass(frozen=True)
class ArrheniusRateLaw(RateLaw):
    """Arrhenius law returning one scalar rate per reaction."""

    pre_exponential: float
    activation_energy: float
    orders: Mapping[str, float]
    gas_constant: float = 8.314

    def __post_init__(self) -> None:
        if self.pre_exponential < 0.0:
            raise ValueError("pre_exponential must be non-negative.")
        if self.gas_constant <= 0.0:
            raise ValueError("gas_constant must be positive.")

    def rate(self, concentrations: Mapping[str, float], temperature: float) -> float:
        temperature_kelvin = _safe_temperature_kelvin(temperature)
        arrhenius_term = _bounded_exponential(
            -self.activation_energy / (self.gas_constant * temperature_kelvin)
        )
        concentration_term = _rate_concentration_term(concentrations, self.orders)
        return self.pre_exponential * arrhenius_term * concentration_term


@dataclass(frozen=True)
class PowerLawRateLaw(RateLaw):
    """Power-law kinetics returning one scalar rate per reaction."""

    k_ref: float
    orders: Mapping[str, float]
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

    def rate(self, concentrations: Mapping[str, float], temperature: float) -> float:
        concentration_term = _rate_concentration_term(concentrations, self.orders)

        rate_constant = self.k_ref
        if self.E_a is not None:
            temperature_kelvin = _safe_temperature_kelvin(temperature)
            correction_exponent = (-self.E_a / self.gas_constant) * (
                (1.0 / temperature_kelvin) - (1.0 / self.T_ref)
            )
            rate_constant *= _bounded_exponential(correction_exponent)

        return rate_constant * concentration_term


__all__ = [
    "ArrheniusRateLaw",
    "PowerLawRateLaw",
    "RateLaw",
    "Reaction",
    "ReactionSet",
]
