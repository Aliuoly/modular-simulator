## Wave 1 — Capture the red state and apply the fixed test dispositions

- [x] 1.1 Capture the current red state with `uv run pytest` and preserve the collection-error evidence showing stale `Mixer`/`Pump`/`Splitter`/`Valve` imports from `tests/unit_process/test_hydraulic_elements.py` and `tests/unit_process/test_stream_port_io.py`.
- [x] 1.2 Rewrite `tests/unit_process/test_hydraulic_elements.py` with these exact dispositions:
  - rewrite `test_pump_hydraulic` around `PumpHydraulicElement` and `default_pump_hydraulic_parameters(...)`,
  - rewrite `test_pump_hydraulic_element_owns_default_parameters_and_bootstrap` around `PumpHydraulicElement.default_parameters()` and `PumpHydraulicElement.line_bootstrap()`,
  - rewrite `test_network_hydraulic_solve` so it keeps supported `HeaterCooler` participation but uses direct hydraulic primitives instead of removed `Valve` / `Mixer` wrappers,
  - remove the `Mixer` / `Splitter` cases from `test_pipe_hydraulic_defaults_for_units`,
  - preserve the existing supported-unit and boundary-source assertions already in the file.
- [x] 1.3 Rewrite `tests/unit_process/test_stream_port_io.py` with these exact dispositions:
  - remove `test_mixer_dynamic_inlets_and_standard_outlet_stream_io`, `test_splitter_standard_inlet_and_dynamic_outlets_stream_io`, and `test_mixer_splitter_invalid_indices_raise_clear_errors`,
  - remove `Pump`, `Valve`, `Mixer`, and `Splitter` from the canonical-file invalid-port parametrization,
  - keep the existing `HeaterCooler`, `CSTR`, `PFR`, `ComponentSeparator`, `FlashDrum`, `ShortcutDistillation`, and `HeatExchanger` coverage in place.
- [x] 1.4 Move the displaced pump/valve-only stream-port assertions into `tests/unit_process/test_layer4_pump_valve.py`:
  - `test_pump_flow_conversion_uses_density`,
  - `test_valve_flow_conversion_uses_density`,
  - the pump/valve cases from `test_volumetric_units_raise_clear_error_without_property_package`,
  - the pump/valve cases from `test_invalid_port_names_raise_clear_errors`.

## Wave 2 — Verify the rewritten canonical surfaces and the allowed lower-level destination

- [x] 2.1 Run targeted verification:
  - `uv run pytest tests/unit_process/test_canonical_wrapper_removal.py`
  - `uv run pytest tests/unit_process/test_hydraulic_elements.py`
  - `uv run pytest tests/unit_process/test_stream_port_io.py`
  - `uv run pytest tests/unit_process/test_layer4_pump_valve.py`
  - Expected evidence: all four files collect and pass; the dedicated migration test still enforces removed-wrapper guidance; pump/valve lower-level coverage now lives only in the allowed lower-level suite.
- [x] 2.2 Run the canonical-regression import check:
  - `rg -n "from modular_simulation\.unit_processes( import .*\b(Pump|Valve|Mixer|Splitter)\b|\.flow\.pump import Pump|\.flow\.valve import Valve|\.mixing\.mixer import Mixer|\.separation\.splitter import Splitter)" tests/unit_process --glob '!test_canonical_wrapper_removal.py' --glob '!test_layer4_pump_valve.py' --glob '!test_layer4_mixer_splitter.py'`
  - Expected evidence: no matches.

## Wave 3 — Full-suite verification and scoped follow-up handling

- [x] 3.1 Run `uv run pytest`.
  - Expected evidence: the repository collects cleanly; if unrelated failures remain, they are reported explicitly as out-of-scope follow-ups rather than folded into this change.
- [x] 3.2 If Wave 3.1 exposes unrelated baseline failures, stay in the project root and use this exact Beads workflow:
  - `bd show ModularSimulator-1b7 --json` and confirm the parent bead is still `in_progress` before creating follow-up work,
  - `bd create --json "Investigate remaining baseline failure after wrapper cleanup" --deps "discovered-from:ModularSimulator-1b7" --description "\`uv run pytest\` still fails after collection repair; failing tests: <nodeids>"`,
  - Expected evidence: the created Beads item records the failing command, the failing nodeids, and remains explicitly linked back to `ModularSimulator-1b7`; this change stays scoped to stale wrapper-import repair only.
