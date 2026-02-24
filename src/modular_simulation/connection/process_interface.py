"""Process-facing binding exports after the connection hard switch.

Legacy adapter/manual-wiring interfaces were intentionally removed.
Use `ConnectionNetwork.compile().process_bindings[...]` and the `ProcessBinding`
API for all active connection authoring flows.
"""

from __future__ import annotations

from modular_simulation.connection.process_binding import (
    BindingError,
    OutletBinding,
    OutletRole,
    ProcessBinding,
)

_MIGRATION_NOTE = (
    "Connection process-interface compatibility boundary is break-and-replace: "
    "legacy adapter symbols were removed and are not executed in v1. "
    "Use ConnectionNetwork.compile().process_bindings['<process_id>'] and the "
    "ProcessBinding API (bind_inlets, bind_outlets, get_outlet, validate)."
)

_LEGACY_REPLACEMENTS: dict[str, str] = {
    "ProcessInterface": (
        "Use ProcessBinding from compiled network bindings. "
        "Author ports via bind_inlets/bind_outlets instead of interface protocols."
    ),
    "ProcessModelAdapter": (
        "Use ConnectionNetwork.compile().process_bindings['<process_id>'] and "
        "bind each process inlet/outlet explicitly with ProcessBinding."
    ),
    "ProcessBalanceTerm": (
        "Use ProcessBinding.get_outlet('<port_name>') and consume "
        "normalized_inlet_flow/inlet_flow/outlet_flow from the returned mapping."
    ),
}


def _legacy_api_error(name: str) -> AttributeError:
    replacement = _LEGACY_REPLACEMENTS[name]
    return AttributeError(
        f"Legacy API 'modular_simulation.connection.process_interface.{name}' was removed "
        + "by the break-and-replace migration. "
        + f"{replacement} {_MIGRATION_NOTE}"
    )


def __getattr__(name: str) -> object:
    replacement = _LEGACY_REPLACEMENTS.get(name)
    if replacement is None:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
    raise _legacy_api_error(name)


PortRole = OutletRole

__all__ = [
    "BindingError",
    "OutletBinding",
    "OutletRole",
    "PortRole",
    "ProcessBinding",
]
