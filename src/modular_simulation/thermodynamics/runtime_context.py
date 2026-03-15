from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .kinetics import ReactionSet
from .property_package import PropertyPackage, create_property_package
from .species import ActiveSpeciesRegistry, SimulationSpeciesContext


_EMPTY_REACTION_SET = ReactionSet(reactions=())


@dataclass(frozen=True)
class SimulationRuntimeContext:
    species_registry: ActiveSpeciesRegistry
    property_package: PropertyPackage
    species_context: SimulationSpeciesContext
    reaction_sets: Mapping[str, ReactionSet] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_reaction_sets = {
            str(subsystem_id): reaction_set
            for subsystem_id, reaction_set in self.reaction_sets.items()
        }
        object.__setattr__(
            self,
            "reaction_sets",
            MappingProxyType(normalized_reaction_sets),
        )

    @classmethod
    def create(
        cls,
        species_names: list[str],
        eos_model: str = "PR",
        reactions: dict[str, ReactionSet] | None = None,
    ) -> "SimulationRuntimeContext":
        species_registry = ActiveSpeciesRegistry.from_names(species_names)
        property_package = create_property_package(species_registry, model=eos_model)
        species_context = SimulationSpeciesContext(registry=species_registry)
        reaction_sets: dict[str, ReactionSet] = {} if reactions is None else dict(reactions)
        return cls(
            species_registry=species_registry,
            property_package=property_package,
            species_context=species_context,
            reaction_sets=reaction_sets,
        )

    def get_property_package(self) -> PropertyPackage:
        return self.property_package

    def get_reactions(self, subsystem_id: str) -> ReactionSet:
        return self.reaction_sets.get(subsystem_id, _EMPTY_REACTION_SET)


__all__ = ["SimulationRuntimeContext"]
