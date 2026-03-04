from __future__ import annotations

from typing import ClassVar, override

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


COMPOSITION_ABS_TOL = 1e-9


class MaterialState(BaseModel):
    pressure: float = Field(description="Absolute pressure at the boundary")
    temperature: float = Field(description="Absolute temperature at the boundary")
    mole_fractions: tuple[float, ...] = Field(
        min_length=1,
        description="Material composition as mole fractions ordered by component index",
    )
    species_ids: tuple[str, ...] | None = Field(
        default=None,
        description="Optional species identifiers aligned with mole_fractions ordering",
    )
    phase: str | None = Field(
        default=None,
        description="Optional phase hint: vapor, liquid, two-phase",
    )
    enthalpy_molar: float | None = Field(
        default=None,
        description="Optional molar enthalpy in J/mol",
    )
    entropy_molar: float | None = Field(
        default=None,
        description="Optional molar entropy in J/mol/K",
    )

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @field_validator("mole_fractions")
    @classmethod
    def _validate_mole_fraction_range(
        cls, value: tuple[float, ...], info: ValidationInfo
    ) -> tuple[float, ...]:
        del info
        for fraction in value:
            if fraction < 0.0 or fraction > 1.0:
                raise ValueError("All mole fractions must be between 0.0 and 1.0.")
        return value

    @model_validator(mode="after")
    def _validate_mole_fraction_sum(self) -> "MaterialState":
        composition_sum = sum(self.mole_fractions)
        if abs(composition_sum - 1.0) > COMPOSITION_ABS_TOL:
            raise ValueError("Mole fractions must sum to 1.0.")
        if self.species_ids is not None and len(self.species_ids) != len(self.mole_fractions):
            raise ValueError("species_ids length must match mole_fractions length")
        return self

    @property
    def has_thermo_metadata(self) -> bool:
        return self.species_ids is not None

    def with_thermo(
        self,
        species_ids: tuple[str, ...] | None = None,
        phase: str | None = None,
        enthalpy_molar: float | None = None,
        entropy_molar: float | None = None,
    ) -> "MaterialState":
        return type(self)(
            pressure=self.pressure,
            temperature=self.temperature,
            mole_fractions=self.mole_fractions,
            species_ids=species_ids,
            phase=phase,
            enthalpy_molar=enthalpy_molar,
            entropy_molar=entropy_molar,
        )

    @classmethod
    def from_legacy(
        cls,
        pressure: float,
        temperature: float,
        mole_fractions: tuple[float, ...],
    ) -> "MaterialState":
        return cls(
            pressure=pressure,
            temperature=temperature,
            mole_fractions=mole_fractions,
        )

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MaterialState):
            return NotImplemented
        return (
            self.pressure,
            self.temperature,
            self.mole_fractions,
            self.species_ids,
            self.phase,
            self.enthalpy_molar,
            self.entropy_molar,
        ) == (
            other.pressure,
            other.temperature,
            other.mole_fractions,
            other.species_ids,
            other.phase,
            other.enthalpy_molar,
            other.entropy_molar,
        )

    @override
    def __hash__(self) -> int:
        return hash(
            (
                self.pressure,
                self.temperature,
                self.mole_fractions,
                self.species_ids,
                self.phase,
                self.enthalpy_molar,
                self.entropy_molar,
            )
        )


class PortCondition(BaseModel):
    state: MaterialState
    species_ids: tuple[str, ...] | None = Field(
        default=None,
        description="Optional species identifiers aligned with state.mole_fractions",
    )
    through_molar_flow_rate: float = Field(
        description="Signed through-flow at the port; positive/negative values indicate direction",
    )
    macro_step_time_s: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional macro-step timestamp in seconds",
    )

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def _validate_species_length(self) -> "PortCondition":
        if self.species_ids is not None and len(self.species_ids) != len(self.state.mole_fractions):
            raise ValueError("species_ids length must match state.mole_fractions length")
        return self
