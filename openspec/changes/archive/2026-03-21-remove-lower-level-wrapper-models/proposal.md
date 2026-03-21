## Why

The repository already removed the four deleted topology-wrapper and flow-control-wrapper classes from the canonical high-level unit-process surface, but live non-archive code still preserves those lower-level wrapper models, wrapper-specific migration messages, runtime name tables, and direct test coverage. That leaves the breaking change only partially applied and keeps the old wrapper model vocabulary alive throughout `src/`, `tests/`, and docs.

The requested direction is stricter: finish the breaking change completely so the live repository no longer ships or mentions those unit-process wrapper models anywhere outside archived history. The supported topology model must be only explicit junctions, sinks, and line-installed `PumpInstall` / `ValveInstall` / `HeatInstall` elements plus the remaining supported unit-process families.

## What Changes

- Remove the lower-level wrapper model source files and package-level import guidance for the four deleted unit-process wrapper classes from the live repository.
- Rewrite remaining tests, runtime fixtures, serializer/load handling, and default tables so they no longer depend on or mention those deleted wrapper model names.
- Tighten the flowsheet-junction spec so it no longer permits dedicated lower-level wrapper coverage in live non-archive code; archive history remains the only preserved record of the old wrapper model vocabulary.

## Capabilities

### Modified Capabilities
- `flowsheet-junction-line-api`: Strengthen wrapper-removal semantics from canonical-surface removal to full live-repository removal of the old lower-level wrapper model vocabulary and artifacts.

## Impact

- Affected source: `src/modular_simulation/unit_processes/__init__.py`, `src/modular_simulation/unit_processes/flow/__init__.py`, `src/modular_simulation/unit_processes/mixing/__init__.py`, `src/modular_simulation/unit_processes/separation/__init__.py`, `src/modular_simulation/measurables/process_model.py`, `src/modular_simulation/thermodynamics/hydraulic_adapters.py`, and removal of the lower-level wrapper modules under `src/modular_simulation/unit_processes/flow/`, `mixing/`, and `separation/`.
- Affected tests/docs: remaining non-archive tests and docs that still mention the removed wrapper model names must be rewritten or removed so supported behavior is described only in terms of junctions, sinks, line installs, supported hydraulic primitives, and supported unit-process families.
- Breaking-change impact: direct use of the old lower-level wrapper model modules is no longer supported anywhere in the live repository.
