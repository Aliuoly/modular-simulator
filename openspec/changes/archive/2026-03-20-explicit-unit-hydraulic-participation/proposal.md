## Why

The current canonical hydraulic semantics already require unit processes to participate through declared ports, hydraulic boundary conditions, and constitutive relations, but the implementation still infers that participation from state names and metadata patterns such as `inlet_pressure`, `outlet_pressure`, `pressure_drop`, and flow-like fields. That inference keeps the solver working, but it does not provide a durable public contract for which ports are hydraulically active, which ports are passive, which port groups balance together, or when direct unit-port fan-in/fan-out is valid.

An explicit-only contract is now needed so unit hydraulic participation is declared rather than guessed. This reduces ambiguity in compile-time validation, keeps runtime pressure/flow lookup aligned with explicit port semantics, and provides a stable foundation for future unit models without expanding the solver through ad hoc metadata conventions.

## What Changes

- Define an explicit `ProcessModel.hydraulic_participation` contract for unit-process models, covering a concrete declaration schema with port roles, scalar/indexed/property-backed state references, explicit balancing declarations, affine pressure relations where the model truly owns them, and unit-owned hydraulic-element couplings where the existing model semantics already flow through `to_hydraulic_element(...)`.
- Remove heuristic inference as the canonical participation path for compile-time unit hydraulic equations and validation.
- Tighten runtime and compiled-hydraulic expectations so pressure-coupled unit ports resolve solved pressures and local flow direction from explicit port participation plus a compiled participation marker rather than fallback inference conventions.
- Require connected unit-process ports to declare participation explicitly; `hydraulic_participation=None` remains valid only for units that never contribute connected process endpoints to the hydraulic topology.
- Specify the migration and verification work needed to move supported units from inferred participation to explicit declarations.

## Capabilities

### Modified Capabilities
- `hydraulic-network-solving-semantics`: Replace inferred unit hydraulic participation with an explicit-only contract and clarify the compile/runtime guarantees that follow from that declaration model.

## Impact

- Affected code: `src/modular_simulation/flowsheet/flowsheet.py`, `src/modular_simulation/connection/runtime/thermo_coupling.py`, `src/modular_simulation/connection/hydraulics/hydraulic_compile.py`, `src/modular_simulation/connection/hydraulics/hydraulic_solver.py`, `src/modular_simulation/thermodynamics/algebraic_process_model.py`, `src/modular_simulation/measurables/process_model.py`, and the unit-process families that currently rely on inferred pressure or flow metadata (`flow/pump.py`, `flow/valve.py`, `thermal/heater_cooler.py`, `thermal/heat_exchanger.py`, `mixing/mixer.py`, `separation/splitter.py`, `separation/component_separator.py`, `separation/flash_drum.py`, `separation/shortcut_distillation.py`, `reactors/cstr.py`, `reactors/pfr.py`, `reactors/conversion_reactor.py`).
- Affected tests: `tests/connection/test_hydraulic_compile.py`, `tests/connection/test_pressure_inference.py`, `tests/connection/test_thermo_coupling_runtime_store.py`, `tests/unit_process/test_flowsheet_validation.py`, `tests/unit_process/test_hydraulic_elements.py`, `tests/unit_process/test_stream_port_io.py`, `tests/unit_process/test_asymmetric_ports.py`, `tests/unit_process/test_stream_propagation.py`, `tests/unit_process/test_layer3_coupling.py`, `tests/unit_process/test_layer4_pump_valve.py`, `tests/unit_process/test_layer4_heater_cooler.py`, `tests/unit_process/test_layer4_heat_exchanger.py`, `tests/unit_process/test_layer4_mixer_splitter.py`, `tests/unit_process/test_layer4_component_separator.py`, `tests/unit_process/test_layer4_flash_drum.py`, `tests/unit_process/test_layer4_distillation.py`, `tests/unit_process/test_layer4_cstr.py`, `tests/unit_process/test_layer4_pfr.py`, and `tests/unit_process/test_layer4_conversion_reactor.py`.
- Affected public contract: unit models that participate in hydraulics must declare that participation explicitly; inference from state naming conventions is no longer the supported canonical behavior.
