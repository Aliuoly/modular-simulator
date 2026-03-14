from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any, override

import numpy as np
from numpy.typing import NDArray

from modular_simulation.measurables.process_model import ProcessModel, StateType
from modular_simulation.utils.typing import ArrayIndex, Seconds
from modular_simulation.validation.exceptions import MeasurableConfigurationError


@dataclass(frozen=True)
class UnitProcessPorts:
    inlets: tuple[str, ...]
    outlets: tuple[str, ...]


SINGLE_IO = UnitProcessPorts(("inlet",), ("outlet",))
DUAL_INLET = UnitProcessPorts(("inlet_1", "inlet_2"), ("outlet",))
TRIPLE_INLET = UnitProcessPorts(("inlet_1", "inlet_2", "inlet_3"), ("outlet",))
DUAL_OUTLET = UnitProcessPorts(("inlet",), ("outlet_1", "outlet_2"))
TRIPLE_OUTLET = UnitProcessPorts(("inlet",), ("outlet_1", "outlet_2", "outlet_3"))
ENERGY_INLET = UnitProcessPorts(("inlet", "energy_in"), ("outlet",))
ENERGY_OUTLET = UnitProcessPorts(("inlet",), ("outlet", "energy_out"))
ENERGY_IO = UnitProcessPorts(("inlet", "energy_in"), ("outlet", "energy_out"))


class AlgebraicProcessModel(ProcessModel, ABC):
    @override
    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        differential_states = [
            name
            for name, metadata in self.state_metadata_dict.items()
            if metadata.type == StateType.DIFFERENTIAL
        ]
        if differential_states:
            raise MeasurableConfigurationError(
                "AlgebraicProcessModel does not allow DIFFERENTIAL states; "
                + f"found {sorted(differential_states)!r}"
            )

    @staticmethod
    @override
    def differential_rhs(
        t: float,
        y: NDArray[np.float64],
        u: NDArray[np.float64],
        k: NDArray[np.float64],
        algebraic: NDArray[np.float64],
        y_map: dict[str, ArrayIndex],
        u_map: dict[str, ArrayIndex],
        k_map: dict[str, ArrayIndex],
        algebraic_map: dict[str, ArrayIndex],
    ) -> NDArray[np.float64]:
        del t, y, u, k, algebraic, y_map, u_map, k_map, algebraic_map
        return np.zeros(0, dtype=np.float64)

    @override
    def step(self, dt: Seconds) -> None:
        if not hasattr(self, "_params"):
            raise RuntimeError("attach_system must be called before step().")

        final_algebraic_values = self._params.algebraic_values_function(
            y=np.zeros(0, dtype=np.float64),
            u=self.boundary_view.to_array(),
            k=self._params.k,
            y_map=self._params.y_map,
            u_map=self._params.boundary_map,
            k_map=self._params.k_map,
            algebraic_map=self._params.algebraic_map,
            algebraic_size=self._params.algebraic_size,
        )
        self.algebraic_view.update_from_array(final_algebraic_values)
        self.t += dt


__all__ = [
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
]
