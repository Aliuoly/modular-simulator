## Context

The canonical wrapper-removal change is already implemented: `modular_simulation.unit_processes.__getattr__` raises actionable `ImportError` guidance for `Pump`, `Valve`, `Mixer`, and `Splitter`, and `tests/unit_process/test_canonical_wrapper_removal.py` verifies that contract explicitly. Despite that, `tests/unit_process/test_hydraulic_elements.py` and `tests/unit_process/test_stream_port_io.py` still import removed wrapper units from the canonical package surface. A fresh `uv run pytest` therefore fails during collection before the suite reaches the intended hydraulic-element and stream-port assertions.

The important constraint is that the import guard is the desired shipped behavior. The failing files are stale tests, not evidence that the wrapper-removal implementation regressed.

## Goals / Non-Goals

**Goals**
- Remove stale canonical-surface wrapper imports from non-migration regression files.
- Preserve meaningful hydraulic-element and stream-port behavior coverage where that behavior is still relevant to supported surfaces.
- Keep wrapper-removal migration guidance tested in exactly one obvious place.
- Restore full-suite collection so any remaining baseline failures can be triaged independently.

**Non-Goals**
- Reintroduce `Pump`, `Valve`, `Mixer`, or `Splitter` to the canonical high-level API.
- Redesign hydraulic semantics, runtime coupling, or public junction/line APIs.
- Expand this change into unrelated baseline-failure cleanup once collection is restored.

## Decisions

1. Preserve the canonical import guard unchanged.
   - `src/modular_simulation/unit_processes/__init__.py` is the intended enforcement point for wrapper removal.
   - This change repairs tests to match that contract instead of weakening the guard for compatibility.

2. Keep migration-guidance assertions centralized in `tests/unit_process/test_canonical_wrapper_removal.py`.
   - Non-migration regression files should not import removed wrapper symbols just to prove they fail.
   - If extra wrapper-removal assertions are needed, they belong in the dedicated migration test module.

3. Retarget stale behavior coverage with explicit per-test dispositions.
   - In `tests/unit_process/test_hydraulic_elements.py`:
      - keep `HeaterCooler` coverage and direct `PumpHydraulicElement` / `ValveHydraulicElement` assertions,
      - rewrite `test_pump_hydraulic` to instantiate `PumpHydraulicElement` directly and assert its residual/jacobian against `default_pump_hydraulic_parameters(...)` rather than `Pump.to_hydraulic_element(...)`,
      - rewrite `test_pump_hydraulic_element_owns_default_parameters_and_bootstrap` to assert `PumpHydraulicElement.default_parameters()` and `PumpHydraulicElement.line_bootstrap()` directly,
      - rewrite `test_network_hydraulic_solve` into a lower-level hydraulic solve that keeps supported `HeaterCooler` participation but replaces removed `Valve` / `Mixer` wrapper usage with direct hydraulic primitives,
      - retire the `Mixer` / `Splitter` entries from `test_pipe_hydraulic_defaults_for_units`,
      - keep `resolve_hydraulic_element(...)` boundary-source coverage.
   - In `tests/unit_process/test_stream_port_io.py`:
      - keep supported `HeaterCooler`, `CSTR`, `PFR`, `ComponentSeparator`, `FlashDrum`, `ShortcutDistillation`, and `HeatExchanger` stream-port coverage,
      - retire `test_mixer_dynamic_inlets_and_standard_outlet_stream_io`, `test_splitter_standard_inlet_and_dynamic_outlets_stream_io`, and `test_mixer_splitter_invalid_indices_raise_clear_errors` from this canonical unit-process file,
      - move `test_pump_flow_conversion_uses_density`, `test_valve_flow_conversion_uses_density`, the pump/valve cases from `test_volumetric_units_raise_clear_error_without_property_package`, and the pump/valve cases from `test_invalid_port_names_raise_clear_errors` into `tests/unit_process/test_layer4_pump_valve.py`,
      - remove `Pump`, `Valve`, `Mixer`, and `Splitter` from the canonical-file invalid-port parametrization so the remaining checks cover only supported unit-process exports.

4. Forbid non-migration reliance on removed wrappers through any import path.
   - This change does not allow swapping `from modular_simulation.unit_processes import Mixer` for imports from `unit_processes.mixing.mixer`, `unit_processes.flow.pump`, or similar internal modules inside canonical regression files such as `tests/unit_process/test_hydraulic_elements.py` and `tests/unit_process/test_stream_port_io.py`.
   - Dedicated migration-guidance coverage (`tests/unit_process/test_canonical_wrapper_removal.py`) and already-lower-level internal suites (`tests/unit_process/test_layer4_pump_valve.py`, `tests/unit_process/test_layer4_mixer_splitter.py`) remain the only allowed places that intentionally touch removed wrapper symbols.

5. Treat restored collection as the boundary of this change.
   - Once `uv run pytest` collects successfully, any newly exposed unrelated failures remain outside this pack unless they are direct consequences of the stale-wrapper cleanup.

## Risks / Trade-offs

- Removing wrapper-based assertions may unintentionally drop useful low-level coverage.
  - Mitigation: the task pack explicitly distinguishes preserved, rewritten, and retired assertions so the implementation cannot silently lose coverage.
- Full-suite execution may expose unrelated failures after collection is restored.
  - Mitigation: keep this pack scoped to collection repair and file follow-up tracking instead of absorbing unrelated failures into the same change.

## Verification Strategy

- Red evidence: current `uv run pytest` fails during collection because the two stale test files import removed wrapper units.
- Green evidence should include:
  - `uv run pytest tests/unit_process/test_canonical_wrapper_removal.py`
  - `uv run pytest tests/unit_process/test_hydraulic_elements.py`
  - `uv run pytest tests/unit_process/test_stream_port_io.py`
  - `uv run pytest tests/unit_process/test_layer4_pump_valve.py`
  - `uv run pytest`
- Plus one repo check confirming no removed wrapper usage remains in canonical non-migration regression files:
  - `rg -n "from modular_simulation\.unit_processes( import .*\b(Pump|Valve|Mixer|Splitter)\b|\.flow\.pump import Pump|\.flow\.valve import Valve|\.mixing\.mixer import Mixer|\.separation\.splitter import Splitter)" tests/unit_process --glob '!test_canonical_wrapper_removal.py' --glob '!test_layer4_pump_valve.py' --glob '!test_layer4_mixer_splitter.py'`

The success criterion is that the suite collects cleanly without removed-wrapper imports through canonical or internal paths outside the dedicated migration tests.
