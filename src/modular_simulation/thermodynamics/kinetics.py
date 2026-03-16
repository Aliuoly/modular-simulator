from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import exp, pow
from typing import Literal, overload

from pydantic import BaseModel, field_validator

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


class Reaction(BaseModel):
    """User-instantiated reaction definition with validation.

    Responsibility:
        Encapsulate a single reaction's stoichiometry, kinetic rate law,
        and (optionally) reverse reaction or equilibrium behavior. This is
        the primary user-facing class for defining reactions in a simulation;
        validation at construction ensures well-formed reaction definitions.

    Construction patterns:
        Use the factory classmethods for common configurations:
        - Reaction.from_arrhenius(): irreversible reaction with Arrhenius kinetics
        - Reaction.from_power_law(): irreversible reaction with power-law kinetics
        - Reaction.from_reversible_arrhenius(): reversible with forward/reverse rate laws
        - Reaction.from_equilibrium(): reversible via equilibrium constant

    Attributes:
        name: Human-readable reaction identifier.
        stoichiometry: Mapping of species names to stoichiometric coefficients.
        rate_law: Forward rate law instance.
        reverse_rate_law: Optional reverse rate law (mutually exclusive with equilibrium_constant).
        equilibrium_constant: Optional K_eq(T) function (mutually exclusive with reverse_rate_law).
        basis: Rate law basis - "concentration" or "partial_pressure".
    """

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    name: str
    stoichiometry: Mapping[str, float]
    rate_law: RateLaw
    reverse_rate_law: RateLaw | None = None
    equilibrium_constant: Callable[[float], float] | None = None
    basis: Literal["concentration", "partial_pressure"] = "concentration"

    @field_validator("stoichiometry")
    @classmethod
    def _validate_stoichiometry(cls, v: Mapping[str, float]) -> Mapping[str, float]:
        if not v:
            raise ValueError("Reaction stoichiometry cannot be empty.")
        return v

    def model_post_init(self, __context: object) -> None:
        """Validate reversible configuration after all fields are set."""
        if self.reverse_rate_law is not None and self.equilibrium_constant is not None:
            raise ValueError(
                "Reaction reversible configuration is ambiguous; provide only one of reverse_rate_law or equilibrium_constant."
            )

    @overload
    @classmethod
    def from_arrhenius(
        cls,
        name: str,
        stoichiometry: Mapping[str, float],
        pre_exponential: float,
        activation_energy: float,
        orders: Mapping[str, float],
        gas_constant: float = ...,
    ) -> Reaction: ...

    @overload
    @classmethod
    def from_arrhenius(
        cls,
        name: str,
        stoichiometry: Mapping[str, float],
        pre_exponential: float,
        activation_energy: float,
        orders: Mapping[str, float],
        *,
        basis: Literal["concentration", "partial_pressure"],
    ) -> Reaction: ...

    @classmethod
    def from_arrhenius(
        cls,
        name: str,
        stoichiometry: Mapping[str, float],
        pre_exponential: float,
        activation_energy: float,
        orders: Mapping[str, float],
        gas_constant: float = 8.314,
        basis: Literal["concentration", "partial_pressure"] = "concentration",
    ) -> Reaction:
        """Factory for irreversible Arrhenius reaction.

        Example:
            >>> reaction = Reaction.from_arrhenius(
            ...     name="A -> B",
            ...     stoichiometry={"A": -1, "B": 1},
            ...     pre_exponential=1e13,
            ...     activation_energy=50000,
            ...     orders={"A": 1}
            ... )
        """
        return cls(
            name=name,
            stoichiometry=stoichiometry,
            rate_law=ArrheniusRateLaw(
                pre_exponential=pre_exponential,
                activation_energy=activation_energy,
                orders=orders,
                gas_constant=gas_constant,
            ),
            basis=basis,
        )

    @overload
    @classmethod
    def from_power_law(
        cls,
        name: str,
        stoichiometry: Mapping[str, float],
        k_ref: float,
        orders: Mapping[str, float],
        T_ref: float = ...,
        E_a: float | None = ...,
        gas_constant: float = ...,
    ) -> Reaction: ...

    @overload
    @classmethod
    def from_power_law(
        cls,
        name: str,
        stoichiometry: Mapping[str, float],
        k_ref: float,
        orders: Mapping[str, float],
        *,
        basis: Literal["concentration", "partial_pressure"],
    ) -> Reaction: ...

    @classmethod
    def from_power_law(
        cls,
        name: str,
        stoichiometry: Mapping[str, float],
        k_ref: float,
        orders: Mapping[str, float],
        T_ref: float = 298.15,
        E_a: float | None = None,
        gas_constant: float = 8.314,
        basis: Literal["concentration", "partial_pressure"] = "concentration",
    ) -> Reaction:
        """Factory for irreversible power-law reaction.

        Example:
            >>> reaction = Reaction.from_power_law(
            ...     name="A -> B",
            ...     stoichiometry={"A": -1, "B": 1},
            ...     k_ref=0.05,
            ...     orders={"A": 1.5}
            ... )
        """
        return cls(
            name=name,
            stoichiometry=stoichiometry,
            rate_law=PowerLawRateLaw(
                k_ref=k_ref,
                orders=orders,
                T_ref=T_ref,
                E_a=E_a,
                gas_constant=gas_constant,
            ),
            basis=basis,
        )

    @overload
    @classmethod
    def from_reversible_arrhenius(
        cls,
        name: str,
        stoichiometry: Mapping[str, float],
        forward_pre_exponential: float,
        forward_activation_energy: float,
        forward_orders: Mapping[str, float],
        reverse_pre_exponential: float,
        reverse_activation_energy: float,
        reverse_orders: Mapping[str, float],
        gas_constant: float = ...,
    ) -> Reaction: ...

    @overload
    @classmethod
    def from_reversible_arrhenius(
        cls,
        name: str,
        stoichiometry: Mapping[str, float],
        forward_pre_exponential: float,
        forward_activation_energy: float,
        forward_orders: Mapping[str, float],
        reverse_pre_exponential: float,
        reverse_activation_energy: float,
        reverse_orders: Mapping[str, float],
        *,
        basis: Literal["concentration", "partial_pressure"],
    ) -> Reaction: ...

    @classmethod
    def from_reversible_arrhenius(
        cls,
        name: str,
        stoichiometry: Mapping[str, float],
        forward_pre_exponential: float,
        forward_activation_energy: float,
        forward_orders: Mapping[str, float],
        reverse_pre_exponential: float,
        reverse_activation_energy: float,
        reverse_orders: Mapping[str, float],
        gas_constant: float = 8.314,
        basis: Literal["concentration", "partial_pressure"] = "concentration",
    ) -> Reaction:
        """Factory for reversible reaction with separate forward/reverse rate laws.

        Example:
            >>> reaction = Reaction.from_reversible_arrhenius(
            ...     name="A <-> B",
            ...     stoichiometry={"A": -1, "B": 1},
            ...     forward_pre_exponential=1e13,
            ...     forward_activation_energy=50000,
            ...     forward_orders={"A": 1},
            ...     reverse_pre_exponential=1e11,
            ...     reverse_activation_energy=30000,
            ...     reverse_orders={"B": 1},
            ... )
        """
        return cls(
            name=name,
            stoichiometry=stoichiometry,
            rate_law=ArrheniusRateLaw(
                pre_exponential=forward_pre_exponential,
                activation_energy=forward_activation_energy,
                orders=forward_orders,
                gas_constant=gas_constant,
            ),
            reverse_rate_law=ArrheniusRateLaw(
                pre_exponential=reverse_pre_exponential,
                activation_energy=reverse_activation_energy,
                orders=reverse_orders,
                gas_constant=gas_constant,
            ),
            basis=basis,
        )

    @classmethod
    def from_equilibrium(
        cls,
        name: str,
        stoichiometry: Mapping[str, float],
        pre_exponential: float,
        activation_energy: float,
        orders: Mapping[str, float],
        equilibrium_constant: Callable[[float], float],
        gas_constant: float = 8.314,
    ) -> Reaction:
        """Factory for reversible reaction via temperature-dependent equilibrium constant.

        Example:
            >>> def K_eq(T):
            ...     return 10 * exp(-5000 * (1/T - 1/298))
            >>> reaction = Reaction.from_equilibrium(
            ...     name="A <-> B",
            ...     stoichiometry={"A": -1, "B": 1},
            ...     pre_exponential=1e13,
            ...     activation_energy=50000,
            ...     orders={"A": 1},
            ...     equilibrium_constant=K_eq,
            ... )
        """
        return cls(
            name=name,
            stoichiometry=stoichiometry,
            rate_law=ArrheniusRateLaw(
                pre_exponential=pre_exponential,
                activation_energy=activation_energy,
                orders=orders,
                gas_constant=gas_constant,
            ),
            equilibrium_constant=equilibrium_constant,
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
