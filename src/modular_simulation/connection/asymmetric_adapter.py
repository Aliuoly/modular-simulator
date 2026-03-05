from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from modular_simulation.connection.process_binding import BindingError, ProcessBinding


@dataclass(frozen=True)
class AsymmetricPortAdapter:
    process_id: str
    inlet_port: str
    outlet_ports: tuple[str, ...]
    _inlet_value: float | None = field(init=False, default=None)
    _binding_by_outlet: dict[str, ProcessBinding] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.process_id.strip():
            raise BindingError("process_id must be a non-empty string")
        if not self.inlet_port.strip():
            raise BindingError("inlet_port must be a non-empty string")
        if len(self.outlet_ports) < 2:
            raise BindingError("asymmetric adapter requires at least two outlet ports")
        if any(not port.strip() for port in self.outlet_ports):
            raise BindingError("outlet_ports must contain only non-empty strings")
        if len(set(self.outlet_ports)) != len(self.outlet_ports):
            raise BindingError("outlet_ports must be unique")

        object.__setattr__(self, "_inlet_value", None)
        object.__setattr__(
            self,
            "_binding_by_outlet",
            {
                outlet_port: ProcessBinding(
                    inlet_ports=[self.inlet_port],
                    outlet_ports=[outlet_port],
                )
                for outlet_port in self.outlet_ports
            },
        )

    def set_inlet(self, port: str, value: float) -> None:
        if port != self.inlet_port:
            raise BindingError(
                f"Unknown inlet port '{port}'. Expected one of: ['{self.inlet_port}']"
            )
        inlet_value = float(value)
        for binding in self._binding_by_outlet.values():
            binding.set_inlet(self.inlet_port, inlet_value)
        object.__setattr__(self, "_inlet_value", inlet_value)

    def bind_inlets(self, bindings: Mapping[str, float]) -> None:
        missing = [self.inlet_port] if self.inlet_port not in bindings else []
        extra = [port for port in bindings if port != self.inlet_port]
        if missing:
            raise BindingError(f"Missing inlet bindings for ports: {sorted(missing)}")
        if extra:
            raise BindingError(f"Unknown inlet bindings for ports: {sorted(extra)}")
        self.set_inlet(self.inlet_port, bindings[self.inlet_port])

    def get_outlet(
        self, port: str
    ) -> dict[str, float | tuple[float, ...] | Literal["inlet", "outlet"]]:
        binding = self._binding_by_outlet.get(port)
        if binding is None:
            raise BindingError(
                f"Unknown outlet port '{port}'. Expected one of: {list(self.outlet_ports)}"
            )
        return binding.get_outlet(port)

    def bind_outlets(self, bindings: Mapping[str, Mapping[str, object]]) -> None:
        missing = [port for port in self.outlet_ports if port not in bindings]
        extra = [port for port in bindings if port not in self._binding_by_outlet]
        if missing:
            raise BindingError(f"Missing outlet bindings for ports: {sorted(missing)}")
        if extra:
            raise BindingError(f"Unknown outlet bindings for ports: {sorted(extra)}")

        for outlet_port in self.outlet_ports:
            outlet_binding = self._binding_by_outlet[outlet_port]
            outlet_binding.bind_outlets({outlet_port: bindings[outlet_port]})

    def validate(self) -> None:
        if self._inlet_value is None:
            raise BindingError(f"Unbound inlet ports: ['{self.inlet_port}']")
        for binding in self._binding_by_outlet.values():
            binding.validate()


@dataclass(frozen=True)
class ConvergingPortAdapter:
    process_id: str
    inlet_ports: tuple[str, ...]
    outlet_port: str
    _binding_by_inlet: dict[str, ProcessBinding] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.process_id.strip():
            raise BindingError("process_id must be a non-empty string")
        if len(self.inlet_ports) < 2:
            raise BindingError("converging adapter requires at least two inlet ports")
        if any(not port.strip() for port in self.inlet_ports):
            raise BindingError("inlet_ports must contain only non-empty strings")
        if len(set(self.inlet_ports)) != len(self.inlet_ports):
            raise BindingError("inlet_ports must be unique")
        if not self.outlet_port.strip():
            raise BindingError("outlet_port must be a non-empty string")

        object.__setattr__(
            self,
            "_binding_by_inlet",
            {
                inlet_port: ProcessBinding(
                    inlet_ports=[inlet_port],
                    outlet_ports=[self.outlet_port],
                )
                for inlet_port in self.inlet_ports
            },
        )

    def set_inlet(self, port: str, value: float) -> None:
        binding = self._binding_by_inlet.get(port)
        if binding is None:
            raise BindingError(
                f"Unknown inlet port '{port}'. Expected one of: {list(self.inlet_ports)}"
            )
        binding.set_inlet(port, float(value))

    def bind_inlets(self, bindings: Mapping[str, float]) -> None:
        missing = [port for port in self.inlet_ports if port not in bindings]
        extra = [port for port in bindings if port not in self._binding_by_inlet]
        if missing:
            raise BindingError(f"Missing inlet bindings for ports: {sorted(missing)}")
        if extra:
            raise BindingError(f"Unknown inlet bindings for ports: {sorted(extra)}")
        for inlet_port in self.inlet_ports:
            self.set_inlet(inlet_port, bindings[inlet_port])

    def get_outlet(
        self, port: str
    ) -> dict[str, float | tuple[float, ...] | Literal["inlet", "outlet"]]:
        if port != self.outlet_port:
            raise BindingError(
                f"Unknown outlet port '{port}'. Expected one of: ['{self.outlet_port}']"
            )
        representative_inlet_port = self.inlet_ports[0]
        binding = self._binding_by_inlet[representative_inlet_port]
        return binding.get_outlet(self.outlet_port)

    def bind_outlets(self, bindings: Mapping[str, Mapping[str, object]]) -> None:
        missing = [self.outlet_port] if self.outlet_port not in bindings else []
        extra = [port for port in bindings if port != self.outlet_port]
        if missing:
            raise BindingError(f"Missing outlet bindings for ports: {sorted(missing)}")
        if extra:
            raise BindingError(f"Unknown outlet bindings for ports: {sorted(extra)}")

        outlet_binding = bindings[self.outlet_port]
        for inlet_port in self.inlet_ports:
            self._binding_by_inlet[inlet_port].bind_outlets({self.outlet_port: outlet_binding})

    def validate(self) -> None:
        for inlet_port in self.inlet_ports:
            self._binding_by_inlet[inlet_port].validate()


def build_process_binding(
    *, process_id: str, inlet_ports: tuple[str, ...], outlet_ports: tuple[str, ...]
) -> ProcessBinding | AsymmetricPortAdapter | ConvergingPortAdapter:
    if len(inlet_ports) == len(outlet_ports):
        return ProcessBinding(inlet_ports=list(inlet_ports), outlet_ports=list(outlet_ports))

    if len(inlet_ports) == 1 and len(outlet_ports) > 1:
        return AsymmetricPortAdapter(
            process_id=process_id,
            inlet_port=inlet_ports[0],
            outlet_ports=tuple(outlet_ports),
        )

    if len(inlet_ports) > 1 and len(outlet_ports) == 1:
        return ConvergingPortAdapter(
            process_id=process_id,
            inlet_ports=tuple(inlet_ports),
            outlet_port=outlet_ports[0],
        )

    raise BindingError(
        "Unsupported process port cardinality for connection binding: "
        + f"process '{process_id}' has {len(inlet_ports)} inlet(s) and {len(outlet_ports)} outlet(s). "
        + "Only equal cardinality, 1-inlet multi-outlet, and multi-inlet 1-outlet units are supported."
    )


__all__ = ["AsymmetricPortAdapter", "ConvergingPortAdapter", "build_process_binding"]
