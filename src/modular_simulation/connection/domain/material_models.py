from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class DensityModel(BaseModel, ABC):  # pyright: ignore[reportUnsafeMultipleInheritance]
    """Nominal base for user-facing density models with Pydantic validation."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @abstractmethod
    def density(self, *, pressure: float, temperature: float) -> float:
        """Evaluate density from the supplied thermodynamic state."""
        ...


class IncompressibleDensityModel(DensityModel):
    """Validate and serialize a user-configured constant-density material model."""

    density_kg_per_m3: float = Field(gt=0.0, description="Constant fluid density")

    def density(self, *, pressure: float, temperature: float) -> float:
        del pressure, temperature
        return self.density_kg_per_m3


class IdealGasDensityModel(DensityModel):
    """Validate and serialize a user-configured ideal-gas density material model."""

    specific_gas_constant_j_per_kg_k: float = Field(
        gt=0.0,
        description="Specific gas constant used in rho = P / (R_specific * T)",
    )

    def density(self, *, pressure: float, temperature: float) -> float:
        if pressure <= 0.0:
            raise ValueError("Pressure must be positive for ideal-gas density evaluation.")
        if temperature <= 0.0:
            raise ValueError("Temperature must be positive for ideal-gas density evaluation.")
        return pressure / (self.specific_gas_constant_j_per_kg_k * temperature)
