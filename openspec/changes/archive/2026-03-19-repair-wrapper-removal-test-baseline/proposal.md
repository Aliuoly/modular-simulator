## Why

The repository's canonical high-level API intentionally removed `Pump`, `Valve`, `Mixer`, and `Splitter` from `modular_simulation.unit_processes`, but two older unit-test modules still import those wrapper symbols from the canonical surface. A fresh `uv run pytest` now stops during collection in `tests/unit_process/test_hydraulic_elements.py` and `tests/unit_process/test_stream_port_io.py` before the broader regression suite can run.

## What Changes

- Repair stale unit-test imports so canonical regression files no longer rely on removed wrapper units through any import path outside the dedicated migration-guidance coverage.
- Preserve the intended behavior coverage by making explicit per-test dispositions: keep supported `HeaterCooler`/reactor/separation/heat-exchanger coverage in place, rewrite pump/valve assertions to use direct hydraulic element classes or line-install primitives, and retire `Mixer`/`Splitter` unit-behavior coverage from canonical unit-process regression files because those wrappers are no longer part of the supported canonical surface.
- Restore full-suite collection so unrelated baseline failures, if any remain, are surfaced as runtime/test failures rather than being hidden behind stale import errors.

## Capabilities

### Modified Capabilities
- `flowsheet-junction-line-api`: Clarify that canonical regression coverage must not import removed wrapper units outside dedicated migration tests.

## Impact

- Affected tests: `tests/unit_process/test_hydraulic_elements.py`, `tests/unit_process/test_stream_port_io.py`, and `tests/unit_process/test_layer4_pump_valve.py`; `tests/unit_process/test_canonical_wrapper_removal.py` remains the dedicated verification guard for wrapper-removal migration guidance.
- Affected public behavior: none; this change keeps the existing wrapper-removal contract intact rather than reintroducing wrapper APIs.
- Verification impact: `uv run pytest` must collect cleanly, and targeted unit-process regression files must pass without importing removed wrapper symbols from canonical or internal package paths outside dedicated migration tests.
