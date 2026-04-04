# Priority Assignment Rules

## Priority Logic

### P0 - Infrastructure Or Blockers

- infrastructure and setup tasks
- migrations, schema changes, or config prerequisites
- environment configuration
- dependency installation that blocks the rest of the change

### P1 - Core Work

- core business logic
- implementation waves
- tests and documentation needed to finish the change cleanly
- API or service-layer work

### P2 - Polish

- UI polish
- non-critical enhancements
- optional cleanup or documentation refinement

## Type Detection Rules

### `task`

- setup
- configure
- refactor
- improve
- test
- validate

### `feature`

- implement
- add
- create

### `chore`

- document
- cleanup
- remove deprecated work

### `epic`

- the parent container for a single OpenSpec change

## Complexity Labels

### `complexity:low`

- straightforward setup or validation work

### `complexity:medium`

- standard implementation or integration work

### `complexity:high`

- refactors, migrations, redesigns, or cross-cutting changes

## Priority Adjustment

### Raise priority by one level when the planning wave or task mentions:

- urgent
- critical
- blocking
- security

### Lower priority by one level when the planning wave or task mentions:

- nice-to-have
- future
- optional
- enhancement
