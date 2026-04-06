## Change

- Name: `upgrade-stagewise-backend-realism`
- Schema: `modsim-contract`

## Beads Epic

- Epic ID: `ModularSimulator-4af`
- Last sync note: `2026-04-05: refreshed Beads linkage after duplicate Wave 1 task cleanup; authoritative Wave 1 task is ModularSimulator-4af.2, duplicate ModularSimulator-4af.1 was closed, and related context remains linked to ModularSimulator-9tr.5 and ModularSimulator-9tr.6`

## Child Tasks

- `ModularSimulator-4af.2`: Write failing stagewise realism tests
- `ModularSimulator-4af.3`: Implement stronger stagewise core closures
- `ModularSimulator-4af.4`: Make withdrawals network-compatible and conservative
- `ModularSimulator-4af.5`: Refresh backend proof and observability evidence
- `ModularSimulator-4af.6`: Run independent realism review gate
- `ModularSimulator-4af.7`: Verify, sync specs, and close out change

## Planning Map

- `Dependency gate` -> `ModularSimulator-4af`
- `Wave 1 — Write the failing realism and seam tests first` -> `ModularSimulator-4af.2`
- `Wave 2 — Replace the old stagewise core closures` -> `ModularSimulator-4af.3`
- `Wave 3 — Make product withdrawals network-compatible and conservative` -> `ModularSimulator-4af.4`
- `Wave 4 — Refresh proof/example and runtime observability evidence` -> `ModularSimulator-4af.5`
- `Wave 5 — Independent review gate` -> `ModularSimulator-4af.6`
- `Wave 6 — Verification and closure hygiene` -> `ModularSimulator-4af.7`

## Notes

- Beads is the live execution ledger for status, blockers, execution notes, and closure.
- `tasks.md` remains the planning breakdown.
- Historical cleanup: duplicate Wave 1 task `ModularSimulator-4af.1` was retired during linkage refresh; use `ModularSimulator-4af.2` as the only active Wave 1 task.
- Related context links:
  - `ModularSimulator-9tr.5` keeps the broader gameplay-topology-causality thread.
  - `ModularSimulator-9tr.6` keeps the later control-facing column-planning thread.
