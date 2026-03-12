from importlib import import_module
from pathlib import Path

POLICY_DOC = Path("docs/discoverability_ownership_policy.md")

FORBIDDEN_PUBLIC_HELPERS = {
    "modular_simulation.connection.hydraulic_solver": {
        "assemble_residual_vector",
        "assemble_sparse_jacobian_triplet",
        "assemble_unknown_vector",
        "build_index_maps",
        "triplet_to_dense",
        "solve_hydraulic_system",
    },
    "modular_simulation.connection.hydraulic_compile": {
        "apply_valve_commands_to_compiled_graph",
        "build_hydraulic_solver_inputs",
        "solve_compiled_hydraulic_graph",
        "compile_hydraulic_graph",
    },
    "modular_simulation.connection.connection_layer": {"run_macro_coupling_step"},
    "modular_simulation.connection.transport_runtime": {"update_transport_runtime_states"},
    "modular_simulation.cli.spec_workflow": {"apply_spec_delta"},
}

SANCTIONED_EXCEPTIONS = (
    "create_property_package",
    "select_transport_model",
    "update_lag_transport_state",
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
