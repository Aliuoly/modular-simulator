## Change

- Name: `fix-thermo-tray-top-end-pathologies`
- Schema: `modsim-contract`

## Beads Epic

- Epic ID: `ModularSimulator-dyk`
- Last synced: `2026-04-08`

## Child Tasks

- Wave 1: `ModularSimulator-d5l` — Write failing tests for top-end pathologies
- Wave 2: `ModularSimulator-too` — Shared drum budget and reflux-request boundary
- Wave 3: `ModularSimulator-pfs` — Dry-drum temperature guard
- Wave 4: `ModularSimulator-69o` — Rerun characterization and verify end-to-end
- Wave 5: `ModularSimulator-m3k` — Review and closeout

## Planning Map

- `Dependency gate` -> `ModularSimulator-dyk` (epic)
- `Wave 1 — Write failing tests for the three top-end pathologies` -> `ModularSimulator-d5l`
- `Wave 2 — Implement the shared drum realizability budget and reflux-request boundary` -> `ModularSimulator-too`
- `Wave 3 — Implement the dry-drum temperature guard` -> `ModularSimulator-pfs`
- `Wave 4 — Rerun characterization and verify end-to-end behavior` -> `ModularSimulator-69o`
- `Wave 5 — Review and closeout` -> `ModularSimulator-m3k`

## Dependency Map

- Epic `ModularSimulator-dyk` discovered-from audit `ModularSimulator-4k3`
- Wave 1 (`ModularSimulator-d5l`) blocks Wave 2 (`ModularSimulator-too`)
- Wave 2 (`ModularSimulator-too`) blocks Wave 3 (`ModularSimulator-pfs`)
- Wave 3 (`ModularSimulator-pfs`) blocks Wave 4 (`ModularSimulator-69o`)
- Wave 4 (`ModularSimulator-69o`) blocks Wave 5 (`ModularSimulator-m3k`)

## Notes

- Beads is the live execution ledger for status, blockers, execution notes, and closure.
- `tasks.md` remains the planning breakdown, not the execution state ledger.
- This change is a follow-on bugfix to the archived `add-thermo-tray-distillation-column` change. It does not create new capabilities; it fixes three concrete top-end pathologies in the existing `ThermoTrayDistillationColumn` implementation.
- The audit evidence for these pathologies is in Beads task `ModularSimulator-4k3`.
