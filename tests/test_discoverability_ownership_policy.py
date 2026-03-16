from importlib import import_module
from pathlib import Path

POLICY_DOC = Path("docs/discoverability_ownership_policy.md")
AUDIT_DOC = Path("docs/discoverability_ownership_audit.md")

FORBIDDEN_PUBLIC_HELPERS = {
    "modular_simulation.connection.hydraulics.hydraulic_solver": {
        "assemble_residual_vector",
        "assemble_sparse_jacobian_triplet",
        "assemble_unknown_vector",
        "build_index_maps",
        "triplet_to_dense",
        "solve_hydraulic_system",
    },
    "modular_simulation.connection.hydraulics.hydraulic_compile": {
        "apply_valve_commands_to_compiled_graph",
        "build_hydraulic_solver_inputs",
        "solve_compiled_hydraulic_graph",
        "compile_hydraulic_graph",
    },
    "modular_simulation.connection.runtime.connection_layer": {"run_macro_coupling_step"},
    "modular_simulation.connection.runtime.transport_runtime": {"update_transport_runtime_states"},
    "modular_simulation.cli.spec_workflow": {"apply_spec_delta"},
}

SANCTIONED_EXCEPTIONS = (
    "create_property_package",
    "thermodynamics.hydraulic_adapters",
)


def _module_exports(module_name: str) -> tuple[str, ...]:
    module = import_module(module_name)
    return tuple(getattr(module, "__all__", ()))


def test_ownerless_helpers_not_exported() -> None:
    for module_name, forbidden in FORBIDDEN_PUBLIC_HELPERS.items():
        exports = _module_exports(module_name)
        overlapping = sorted(set(exports) & forbidden)
        assert not overlapping, (
            f"{module_name} re-exposes forbidden helpers: {', '.join(overlapping)}"
        )


def test_sanctioned_exceptions_documented() -> None:
    text = POLICY_DOC.read_text(encoding="utf-8")
    missing = [entry for entry in SANCTIONED_EXCEPTIONS if entry not in text]
    assert not missing, f"Policy doc missing sanctioned exception references: {missing}"


def test_density_material_models_expose_only_direct_concrete_types() -> None:
    module = import_module("modular_simulation.connection.domain.material_models")
    audit_text = AUDIT_DOC.read_text(encoding="utf-8")
    public_module_callables = {
        name
        for name, value in vars(module).items()
        if callable(value)
        and not isinstance(value, type)
        and getattr(value, "__module__", None) == module.__name__
        and not name.startswith("_")
    }
    public_density_types = {
        name
        for name, value in vars(module).items()
        if isinstance(value, type)
        and getattr(value, "__module__", None) == module.__name__
        and name.endswith("DensityModel")
    }

    assert public_module_callables == set()
    assert public_density_types == {
        "DensityModel",
        "IncompressibleDensityModel",
        "IdealGasDensityModel",
    }
    assert "connection.material_models" not in audit_text


def test_transport_public_surface_exposes_owner_only_types() -> None:
    module = import_module("modular_simulation.connection.domain.transport")
    public_module_callables = {
        name
        for name, value in vars(module).items()
        if callable(value)
        and not isinstance(value, type)
        and getattr(value, "__module__", None) == module.__name__
        and not name.startswith("_")
    }
    public_transport_types = {
        name
        for name, value in vars(module).items()
        if isinstance(value, type)
        and getattr(value, "__module__", None) == module.__name__
        and not name.startswith("_")
    }

    assert public_module_callables == set()
    assert public_transport_types == {
        "LagTransportState",
        "LagTransportUpdateResult",
        "MVPLagTransportModel",
        "TransportModel",
    }
