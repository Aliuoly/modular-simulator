## Change

- Name: `upgrade-thermo-tray-total-condenser-pressure-model`
- Schema: `modsim-contract`

## Beads Epic

- Epic ID: `ModularSimulator-388`
- Last sync note: `2026-04-09: created Beads epic and seven execution-ready child tasks from the frozen planning pack after resolving the PR bubble-plus-excess-headspace-pressure closure and Bennett-Agrawal-Cook pressure-drop provenance.`

## Child Tasks

- `ModularSimulator-388.1`: Write failing thermo tray realism tests
- `ModularSimulator-388.2`: Split thermo-tray family and restore solver seam
- `ModularSimulator-388.3`: Implement condenser headspace and subcooling physics
- `ModularSimulator-388.4`: Implement dynamic thermo-tray end-pressure treatment
- `ModularSimulator-388.5`: Refresh thermo tray demos and observability evidence
- `ModularSimulator-388.6`: Run independent thermo-tray realism review
- `ModularSimulator-388.7`: Verify, sync specs, and close thermo tray change

## Planning Map

- `Dependency gate` -> `ModularSimulator-388`
- `Wave 1 — Freeze the new contract with failing realism tests first` -> `ModularSimulator-388.1`
- `Wave 2 — Rename/split the thermo-tray unit family and restore the solver seam` -> `ModularSimulator-388.2`
- `Wave 3 — Implement total-condenser headspace, pressure, and subcooling physics` -> `ModularSimulator-388.3`
- `Wave 4 — Replace constant pressure anchors with dynamic end-pressure treatment` -> `ModularSimulator-388.4`
- `Wave 5 — Refresh demos and runtime evidence` -> `ModularSimulator-388.5`
- `Wave 6 — Independent review gate` -> `ModularSimulator-388.6`
- `Wave 7 — Verification and closure hygiene` -> `ModularSimulator-388.7`

## Dependency Notes

- Execution waves are linked in Beads as a serial dependency chain:
  - `ModularSimulator-388.2` blocks on `ModularSimulator-388.1`
  - `ModularSimulator-388.3` blocks on `ModularSimulator-388.2`
  - `ModularSimulator-388.4` blocks on `ModularSimulator-388.3`
  - `ModularSimulator-388.5` blocks on `ModularSimulator-388.4`
  - `ModularSimulator-388.6` blocks on `ModularSimulator-388.5`
  - `ModularSimulator-388.7` blocks on `ModularSimulator-388.6`

## Notes

- Beads is the live execution ledger for status, blockers, execution notes, review outcomes, and closure evidence.
- `tasks.md` remains the planning breakdown and does not carry live execution state.
- This linkage reflects the frozen planning contract after inline planner fixes removed the unresolved headspace-closure choice and aligned the spec/design pressure-drop family and headspace notation.
