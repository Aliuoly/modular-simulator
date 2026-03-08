# Draft: Process Unit Library Misalignments

## Requirements (confirmed)
- Identify all other misalignments in the process unit library.
- User language (exact): "identify all other misalignments in the process unit library".

## Technical Decisions
- Focus default: control-contract misalignments (setpoint-in-model coupling, controller readiness, naming/validation inconsistencies) across `src/modular_simulation/unit_processes`.
- Output format target: severity-ranked inventory with concrete file evidence and proposed remediation groups.
- Inventory granularity: per-unit misalignment matrix (High/Medium/Low) with explicit evidence paths.
- User-selected strategy: **two-pass approach** (pass 1 = control-contract alignment set; pass 2 = broader process-model consistency audit).
- Execution default: produce one unified plan containing both passes as sequential waves.

## Research Findings
- High-confidence anti-pattern cluster:
  - `src/modular_simulation/unit_processes/heater_cooler.py` (internal mode + `target_temperature_setpoint` coupling)
  - `src/modular_simulation/unit_processes/flash_drum.py` (`thermal_mode` + `flash_temperature_setpoint` embedding)
  - `src/modular_simulation/unit_processes/cstr.py` internal level-control law (`reactor_volume` + `level_control_gain` driving `outlet_flow`)
- Medium-confidence controller-readiness gaps:
  - `src/modular_simulation/unit_processes/pfr.py` and `src/modular_simulation/unit_processes/pump.py` expose likely manipulated variables (`jacket_temperature`, `pressure_rise`) as constants.
  - `src/modular_simulation/unit_processes/component_separator.py` keeps split fractions constant-tagged.
- Likely aligned/low misalignment units: `valve.py`, `splitter.py`, `heat_exchanger.py`, `shortcut_distillation.py` (based on current control-contract pattern in this repo).
- Test landscape indicates strong unit-physics coverage but sparse controller wiring coverage tied directly to most process units (controller tests are mostly generic actuator-tag based).

## Open Questions
- None blocking.

## Scope Boundaries
- INCLUDE: process unit contracts + related tests/examples misalignments, in two passes (control-contract then broader consistency).
- EXCLUDE (default): implementation changes in this step; this is inventory + planning only.
