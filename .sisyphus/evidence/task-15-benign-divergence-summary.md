# Task 15 Benign Divergence Summary

Plan: `process-unit-misalignment-remediation`
Task: `15 - Refresh benign-divergence documentation and the final evidence bundle`

## Intent

- Group 6 stays documentation-only.
- No runtime behavior, controller surface, solver path, or persistence behavior changed in Task 15.
- The low-severity Pass 2 rows from `.sisyphus/evidence/task-9-pass2-register.md` remain intentional, bounded, and protected by existing tests.

## Documentation-Only Benign Divergences

| register_row | divergence | severity | status | why it remains intentional | protecting tests |
| --- | --- | --- | --- | --- | --- |
| B1 | `HeaterCooler` and `FlashDrum` zero-flow thermal handling differs by mode intent | `low` | `documentation-only, intentional` | `HeaterCooler` duty mode is energy-addition/removal logic, so zero-duty coverage preserves inlet state and zero-flow duty-style behavior is not treated like a temperature-target flash. `FlashDrum` isothermal mode still allows thermodynamic flash calculations from a temperature setpoint. The difference reflects mode intent, not a contract bug. | `tests/unit_process/test_layer4_heater_cooler.py::test_zero_duty_leaves_state_unchanged`, `tests/unit_process/test_layer4_flash_drum.py::test_binary_isothermal_flash`, `tests/unit_process/test_layer4_flash_drum.py::test_vf_boundary_compositions_are_valid` |
| B2 | composition fallback differs between holdup and pass-through models | `low` | `documentation-only, intentional` | Holdup reactors keep internally modeled inventory and can fall back from reactor state, while pass-through and split units preserve feed-driven composition semantics when an outlet leg reaches zero flow. That difference follows model class responsibilities and stays acceptable. | `tests/unit_process/test_layer4_cstr.py::test_first_order_steady_state`, `tests/unit_process/test_layer4_pfr.py::test_first_order_matches_analytical`, `tests/unit_process/test_layer4_conversion_reactor.py::test_50pct_conversion_mass_balance`, `tests/unit_process/test_layer4_distillation.py::test_mass_balance_closure`, `tests/unit_process/test_layer4_flash_drum.py::test_binary_isothermal_flash`, `tests/unit_process/test_layer4_component_separator.py::test_component_separator_zero_flow_outlet_composition_is_stable` |
| B3 | `HeatExchanger` arrangement parsing remains alias-friendly | `low` | `documentation-only, intentional` | Arrangement aliases are limited to known, deterministic names and still reject unknown inputs. That keeps external integrations usable without widening runtime semantics or silently accepting malformed selector values. | `tests/unit_process/test_layer4_heat_exchanger.py::test_flow_arrangements_supported`, `tests/unit_process/test_layer4_heat_exchanger.py::test_heat_exchanger_legacy_conductance_aliases_warn_but_canonical_does_not`, `tests/unit_process/test_layer4_heat_exchanger.py::test_heat_exchanger_unknown_conductance_name_fails_explicitly` |

## Intentional Divergences That Still Remain

1. `HeaterCooler` zero-flow and `FlashDrum` isothermal behavior remain intentionally different because one models direct duty intent and the other models equilibrium at a requested flash state.
2. Reactor-family composition fallback and pass-through composition fallback remain intentionally different because the units do not share the same state model.
3. `HeatExchanger` keeps bounded arrangement alias acceptance because it improves compatibility without changing exchanger physics or introducing silent parser drift.

## Audit Notes

- Source register: `.sisyphus/evidence/task-9-pass2-register.md`
- Sequencing guardrail: `.sisyphus/evidence/task-10-two-pass-backlog.md`
- Runtime-safety evidence remains anchored in Task 11 and Task 12 artifacts.
- Compatibility and naming-coherence evidence remains anchored in Task 13 and Task 14 artifacts.
