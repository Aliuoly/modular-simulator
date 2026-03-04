import importlib

from .kinetics import (
    ArrheniusRateLaw,
    EquilibriumConstantLaw,
    PowerLawRateLaw,
    RateLaw,
    Reaction,
    ReactionSet,
)
from .property_package import (
    FlashResult,
    PengRobinsonPackage,
    PropertyPackage,
    create_property_package,
)
from .runtime_context import SimulationRuntimeContext
from .species import (
    ActiveSpeciesRegistry,
    SimulationSpeciesContext,
    Species,
    SpeciesProjection,
    resolve_species,
)

__all__ = [
    "AlgebraicProcessModel",
    "ActiveSpeciesRegistry",
    "ArrheniusRateLaw",
    "DUAL_INLET",
    "DUAL_OUTLET",
    "ENERGY_INLET",
    "ENERGY_IO",
    "ENERGY_OUTLET",
    "EquilibriumConstantLaw",
    "FlashResult",
    "PengRobinsonPackage",
    "PowerLawRateLaw",
    "PropertyPackage",
    "RateLaw",
    "Reaction",
    "ReactionSet",
    "SINGLE_IO",
    "SimulationRuntimeContext",
    "SimulationSpeciesContext",
    "Species",
    "SpeciesProjection",
    "TRIPLE_INLET",
    "TRIPLE_OUTLET",
    "UnitProcessPorts",
    "create_property_package",
    "resolve_species",
]

_ALGEBRAIC_EXPORTS = {
    "AlgebraicProcessModel",
    "DUAL_INLET",
    "DUAL_OUTLET",
    "ENERGY_INLET",
    "ENERGY_IO",
    "ENERGY_OUTLET",
    "SINGLE_IO",
    "TRIPLE_INLET",
    "TRIPLE_OUTLET",
    "UnitProcessPorts",
}


def __getattr__(name: str):
    if name in _ALGEBRAIC_EXPORTS:
        module = importlib.import_module(
            ".algebraic_process_model",
            __name__,
        )
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
