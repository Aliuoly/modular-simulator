## Change

- Name: `add-paper-faithful-dynamic-distillation-models`
- Schema: `modsim-contract`

## Beads Epic

- Epic ID: `ModularSimulator-6l3`
- Last sync note: `2026-04-06T02:25:41Z: created epic plus child tasks for Waves 1-6; wave mapping is authoritative even though Beads child numbering does not match wave numbering.`

## Child Tasks

- `ModularSimulator-6l3.1`: Wave 1 — failing paper-faithful tests and seam checks
- `ModularSimulator-6l3.6`: Wave 2 — implement Howard 1970 model slice
- `ModularSimulator-6l3.2`: Wave 3 — implement Gani 1986 model slice
- `ModularSimulator-6l3.5`: Wave 4 — prove runtime coexistence and comparison evidence
- `ModularSimulator-6l3.3`: Wave 5 — realism and equation-fidelity review gate
- `ModularSimulator-6l3.4`: Wave 6 — verification and closeout

## Planning Map

- `Dependency gate` -> `ModularSimulator-6l3`
- `Wave 1 — Write the failing paper-faithful tests and seam checks first` -> `ModularSimulator-6l3.1`
- `Wave 2 — Implement the Howard 1970 model slice` -> `ModularSimulator-6l3.6`
- `Wave 3 — Implement the Gani 1986 model slice` -> `ModularSimulator-6l3.2`
- `Wave 4 — Prove runtime coexistence and comparison evidence` -> `ModularSimulator-6l3.5`
- `Wave 5 — Independent realism and equation-fidelity review gate` -> `ModularSimulator-6l3.3`
- `Wave 6 — Verification and closure hygiene` -> `ModularSimulator-6l3.4`

## Notes

- Beads is the live execution ledger for status, blockers, execution notes, and closure.
- `tasks.md` remains the planning breakdown.
- Delegated implementation and review agents append packet-level notes to linked child tasks before returning.
- The orchestrator owns final `closed` and top-level `blocked` status transitions.
- Child-task IDs are intentionally recorded by planning-wave mapping, not by Beads suffix order.
