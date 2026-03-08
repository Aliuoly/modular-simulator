# Draft: HeaterCooler Controller Setup Refactor

## Requirements (confirmed)
- Replace HeaterCooler's `target setpoint` argument with control-element -> controller setup.
- User language (exact): "we want control element -> controller setup, not somme arbitrary setpoint as an attribute".

## Technical Decisions
- Intent classification: Standard (cross-module refactor, not full architecture rewrite).
- Baseline direction: move outlet-temperature control responsibility out of `HeaterCooler` internals and into existing control-system abstractions (`ControlElement` + `AbstractController`).
- Preserve existing control-system wiring patterns already present in `components/control_system/*` and runtime wiring API.
- Migration strategy selected: **breaking change now** (remove target-temperature argument and internal temperature-mode logic).
- Test strategy defaulted: **tests-after** with targeted unit/integration coverage updates.

## Research Findings
- `src/modular_simulation/unit_processes/heater_cooler.py`: `target_temperature_setpoint` is a declared state and is used in both algebraic and thermodynamic `step` paths for temperature mode.
- `src/modular_simulation/components/control_system/control_element.py`: supports MV actuation by tag and wiring to controllers.
- `src/modular_simulation/components/control_system/abstract_controller.py`: already has CV/SP/MV pattern with mode management.
- `tests/unit_process/test_layer4_heater_cooler.py`: temperature-mode behavior currently depends on `target_temperature_setpoint` and will need migration.
- Test infra exists via pytest and CI (`pyproject.toml`, `.github/workflows/ci.yml`).

## Open Questions
- None blocking.

## Scope Boundaries
- INCLUDE: HeaterCooler API/logic changes, control-system wiring strategy for temperature control, impacted unit tests.
- EXCLUDE: Broad refactor of all other unit-process setpoint fields (`flash_drum`, `cstr`, `shortcut_distillation`) unless explicitly requested.
