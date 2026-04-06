## Why

The live distillation contract currently freezes `StagewiseDistillationColumn` as the only runtime distillation path. That is useful for the repo's reduced-order baseline, but it leaves no contract-backed way to implement and compare literature-grounded column models whose governing equations are taken directly from published dynamic distillation papers.

Howard (1970) and Gani, Ruiz, Cameroni (1986) are now source-verified strongly enough to freeze a planning contract with explicit equations. Adding them as sibling runtime models creates honest comparison baselines without replacing the current stagewise model or reopening any shortcut-shim path.

## What Changes

- Add two paper-faithful dynamic distillation model classes alongside the existing stagewise model:
  - `Howard1970DistillationColumn`
  - `Gani1986DistillationColumn`
- Keep `StagewiseDistillationColumn` as the existing reduced-order runtime baseline.
- Modify the `units-and-components` contract so runtime distillation is no longer stagewise-only, while still forbidding any `ShortcutDistillation` class, alias, or compatibility shim.
- Freeze the governing-equation contract for the Howard and Gani model families in `specs/units-and-components/spec.md` and preserve equation provenance and first-slice boundaries in `design.md`.
- For Howard constant-volume holdup, freeze the executable first slice around direct Howard Eqs. (26) through (29); treat Eq. (30) as an optional coefficient-family shorthand only when it is recovered exactly from source evidence or derived deterministically from the direct equations.
- Keep this change backend-only:
  - no gameplay/catalog/start widening,
  - no automatic replacement of stagewise units,
  - no new shortcut runtime pathway,
  - no new connection-capability contract unless implementation later proves the existing runtime demand seam insufficient.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `units-and-components`: expand the runtime distillation contract so `StagewiseDistillationColumn` coexists with two explicit paper-faithful sibling models, and freeze the Howard/Gani governing equations, closures, and first-slice scope boundaries in equation-bearing specs.

## Impact

- Expected code focus:
  - `src/modular_simulation/unit_processes/separation/howard1970_distillation.py`
  - `src/modular_simulation/unit_processes/separation/gani1986_distillation.py`
  - `src/modular_simulation/unit_processes/separation/__init__.py`
  - `src/modular_simulation/unit_processes/__init__.py`
  - likely new regression/integration coverage under `tests/unit_process/` and `tests/integration/`
  - likely a comparison/demo entrypoint under `examples/dynamic_simulation_demos/`
- Expected live spec update:
  - `openspec/specs/units-and-components/spec.md`
- Governing equations must remain explicit in:
  - `openspec/changes/add-paper-faithful-dynamic-distillation-models/specs/units-and-components/spec.md`
  - `openspec/changes/add-paper-faithful-dynamic-distillation-models/design.md`
- Existing connection/runtime seams are expected to be reused rather than redefined, especially:
  - `src/modular_simulation/connection/runtime/process_stream_io.py`
  - `src/modular_simulation/unit_processes/separation/stagewise_distillation.py`
