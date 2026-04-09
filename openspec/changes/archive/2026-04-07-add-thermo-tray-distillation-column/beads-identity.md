## Change

- Name: `add-thermo-tray-distillation-column`
- Schema: `modsim-contract`

## Beads Epic

- Epic ID: `ModularSimulator-29i`
- Last sync note: `2026-04-07: created Beads epic and execution-wave child tasks for the thermo-backed actual-tray planning pack; Wave 4 was recreated after one transient Dolt serialization conflict during parallel creation, and the final mapping below is authoritative.`

## Child Tasks

- `ModularSimulator-29i.4`: Write failing thermo-tray tests and startup demo
- `ModularSimulator-29i.2`: Implement thermo closures and sibling tray model
- `ModularSimulator-29i.1`: Implement startup-settle flow and narrow guards
- `ModularSimulator-29i.5`: Integrate runtime, withdrawal, and observability seams
- `ModularSimulator-29i.3`: Verify equation fidelity and close out thermo tray change

## Planning Map

- `Dependency gate` -> `ModularSimulator-29i`
- `Wave 1 — Write the failing thermo-tray tests first` -> `ModularSimulator-29i.4`
- `Wave 2 — Add the thermo closure seam and new sibling model` -> `ModularSimulator-29i.2`
- `Wave 3 — Implement startup-and-settle and narrow numerical guards` -> `ModularSimulator-29i.1`
- `Wave 4 — Integrate existing runtime seams without widening scope` -> `ModularSimulator-29i.5`
- `Wave 5 — Equation fidelity, review, and closeout` -> `ModularSimulator-29i.3`

## Dependency Map

- `ModularSimulator-29i.4` blocks `ModularSimulator-29i.2`
- `ModularSimulator-29i.2` blocks `ModularSimulator-29i.1`
- `ModularSimulator-29i.1` blocks `ModularSimulator-29i.5`
- `ModularSimulator-29i.5` blocks `ModularSimulator-29i.3`
- `ModularSimulator-29i.3` relates to `ModularSimulator-29i.4` for TDD evidence closure

## Notes

- Beads is the live execution ledger for status, blockers, execution notes, and closure.
- `tasks.md` remains the planning breakdown, not the execution state ledger.
- This change intentionally reuses the live `observability` contract; Wave 4 keeps the thermo-tray path compatible with the existing substrate snapshot rather than widening the snapshot schema.
