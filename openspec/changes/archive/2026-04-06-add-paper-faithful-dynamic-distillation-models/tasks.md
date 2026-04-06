## Dependency gate

- [ ] D0 Confirm this change pack is approved, linked Beads execution items exist, and implementation starts from this pack as the active source of truth for `add-paper-faithful-dynamic-distillation-models`.

## Wave 1 — Write the failing paper-faithful tests and seam checks first

- [ ] 1.1 `simulation-realism-required: true` Add failing unit coverage in `tests/unit_process/test_layer4_howard1970_distillation.py` and `tests/unit_process/test_layer4_gani1986_distillation.py` for class construction, package exports, explicit sibling coexistence with `StagewiseDistillationColumn`, and the shared monolithic feed/product runtime seam.
- [ ] 1.2 `simulation-realism-required: true` Add equation-fidelity regression fixtures in those same test files that evaluate small synthetic states against the frozen governing equations `GE-H70-1` through `GE-H70-8` and `GE-G86-1` through `GE-G86-8`, including Howard Eq. (7), Eq. (8), Eq. (25), Eq. (28), Eq. (29), and Gani Appendix A.1–A.8 so sign, coefficient, and closure drift fails red. If Howard Eq. (30) is exposed, verify it only against the source-exact or deterministically derived family rather than invented surrogate coefficients.
- [ ] 1.3 `simulation-realism-required: true` Add failing runtime-compatibility coverage in `tests/integration/test_paper_faithful_distillation_runtime.py` for feed/product routing, explicit holdup ownership, runtime outlet-demand application, and non-widening of gameplay/start exposure.
- [ ] 1.4 Run the red boundary:
  - `uv run pytest tests/unit_process/test_layer4_howard1970_distillation.py`
  - `uv run pytest tests/unit_process/test_layer4_gani1986_distillation.py`
  - `uv run pytest tests/integration/test_paper_faithful_distillation_runtime.py`
  - Expected evidence: the new tests fail until the Howard and Gani classes, equations, and runtime seams actually exist.

## Wave 2 — Implement the Howard 1970 model slice

- [ ] 2.1 `simulation-realism-required: true` Create `src/modular_simulation/unit_processes/separation/howard1970_distillation.py` with `Howard1970DistillationColumn` as a `ProcessModel` sibling to the existing stagewise model.
- [ ] 2.2 `simulation-realism-required: true` Implement the frozen Howard plate-balance, equilibrium, efficiency, and implicit temperature-solve family from `GE-H70-1` through `GE-H70-6` without replacing them with the repo's reduced-order stagewise hydraulic or thermal closure family.
- [ ] 2.3 `simulation-realism-required: true` Implement the Howard feed-plate and constant-volume-holdup forms from `GE-H70-7` and `GE-H70-8` using the direct Eq. (28) derivative balance and Eq. (29) rearranged closure as the normative first-slice runtime path. Do not invent surrogate `F_j`/`G_j`/`K_j` families; only expose Howard Eq. (30) if it is kept source-exact or derived deterministically from the direct equations. If additional Howard specification families are discovered necessary during execution, create new Beads work instead of silently widening this pack.
- [ ] 2.4 `simulation-realism-required: true` Export `Howard1970DistillationColumn` in `src/modular_simulation/unit_processes/separation/__init__.py` and `src/modular_simulation/unit_processes/__init__.py` while keeping `StagewiseDistillationColumn` unchanged as the existing reduced-order baseline.

## Wave 3 — Implement the Gani 1986 model slice

- [ ] 3.1 `simulation-realism-required: true` Create `src/modular_simulation/unit_processes/separation/gani1986_distillation.py` with `Gani1986DistillationColumn` as a `ProcessModel` sibling to the existing stagewise model.
- [ ] 3.2 `simulation-realism-required: true` Implement the frozen single-column open-loop core ODE, definition, equilibrium, enthalpy, density, and molecular-weight family from `GE-G86-1` through `GE-G86-5` without collapsing it to the repo's stagewise reduced-order closure.
- [ ] 3.3 `simulation-realism-required: true` Implement the generic hydraulic dependency family from `GE-G86-6` together with the frozen bubble-cap appendix subset `GE-G86-8` (`A.1`–`A.8`); keep controllers, multiple columns, start-up procedures, alternate plate families, and deferred optional procedures out of scope in this pack.
- [ ] 3.4 `simulation-realism-required: true` Implement the Gani reflux-drum/reboiler balances from `GE-G86-7` and align any runtime outlet-demand handling with the existing connection/runtime seam instead of widening `openspec/specs/connection/spec.md` unless fresh evidence proves that seam insufficient.
- [ ] 3.5 `simulation-realism-required: true` Export `Gani1986DistillationColumn` in `src/modular_simulation/unit_processes/separation/__init__.py` and `src/modular_simulation/unit_processes/__init__.py`.

## Wave 4 — Prove runtime coexistence and comparison evidence

- [ ] 4.1 `simulation-realism-required: true` Add `examples/dynamic_simulation_demos/paper_faithful_distillation_comparison.py` that instantiates `StagewiseDistillationColumn`, `Howard1970DistillationColumn`, and `Gani1986DistillationColumn` side by side without claiming they share the same governing closure.
- [ ] 4.2 `simulation-realism-required: true` Expand `tests/integration/test_paper_faithful_distillation_runtime.py` so the new classes prove explicit feed/product ownership, runtime outlet-demand compatibility, and absence of any `ShortcutDistillation` compatibility path.
- [ ] 4.3 `simulation-realism-required: true` Re-check existing distillation demos, docs, and discoverability references for new ambiguity; if a broader cleanup is discovered, create follow-up Beads work rather than broadening this pack.

## Wave 5 — Independent realism and equation-fidelity review gate

- [ ] 5.1 `simulation-realism-required: true` Run `modsim-verify` plus an independent code review focused on source-equation fidelity, runtime seam compatibility, and protection against hidden shortcut-shim reintroduction.
- [ ] 5.2 `simulation-realism-required: true` Do not close implementation until review evidence is non-blocking and still shows:
  - Howard behavior follows `GE-H70-1` through `GE-H70-8`
  - Howard constant-volume holdup follows direct Eq. (28) and Eq. (29), unless any Eq. (30) shorthand used is source-exact or deterministically derived
  - Gani behavior follows `GE-G86-1` through `GE-G86-8`
  - `StagewiseDistillationColumn` remains intact as a separate reduced-order baseline
  - gameplay/start/build exposure is unchanged
  - no `ShortcutDistillation` runtime/shim pathway was reintroduced.

## Wave 6 — Verification and closure hygiene

- [ ] 6.1 `simulation-realism-required: true` Run the focused and full verification set:
  - `uv run pytest tests/unit_process/test_layer4_howard1970_distillation.py`
  - `uv run pytest tests/unit_process/test_layer4_gani1986_distillation.py`
  - `uv run pytest tests/unit_process/test_layer4_stagewise_distillation.py`
  - `uv run pytest tests/integration/test_paper_faithful_distillation_runtime.py`
  - `uv run python examples/dynamic_simulation_demos/paper_faithful_distillation_comparison.py`
  - `openspec validate --specs --strict --no-interactive`
- [ ] 6.2 Expected evidence:
  - Howard and Gani classes exist, export cleanly, and remain explicit siblings of `StagewiseDistillationColumn`
  - equation-fidelity regressions prove the implementation still matches the frozen Howard and Gani governing equations instead of a prose-only interpretation, including Howard direct Eq. (28) and Eq. (29) closure
  - the existing stagewise regression suite still passes unchanged
  - no shortcut shim is present
  - gameplay/start/build exposure remains unchanged
  - no connection-spec widening was needed unless new evidence explicitly justified it.
- [ ] 6.3 Sync live `openspec/specs/units-and-components/spec.md` after implementation and final evidence are complete, then update the linked Beads items with final verification and review notes before closure.
