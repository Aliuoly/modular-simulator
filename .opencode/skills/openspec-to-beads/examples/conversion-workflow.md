# OpenSpec To Beads Sync Examples

## Example 1: Planning-Time Sync For A New Change

### Context

OpenSpec change: `add-auth`

Planning pack exists with:
- `proposal.md`
- `specs/auth/spec.md`
- `design.md`
- `tasks.md`
- `beads-identity.md` with placeholder linkage

### Validation

Check before sync:
- planning waves are concrete enough to execute
- verification tasks exist
- realism review flag is present if needed
- planning-wave boundaries are clear enough for Beads task mapping

### Example Sync Output

```text
✅ Synced `add-auth` to Beads

Change: add-auth
Epic: bd-42
Tasks:
- bd-43: Wave 1 — auth schema and setup
- bd-44: Wave 2 — provider integration
- bd-45: Wave 3 — verification and closeout

Mapping:
- Wave 1 -> bd-43
- Wave 2 -> bd-44
- Wave 3 -> bd-45

Next action:
- Run `modsim-apply add-auth`
```

## Example 2: Refresh Existing Linkage After Planning Changes

### Context

OpenSpec change: `duplicate-transaction-fix`

`tasks.md` changed:
- Wave 2 was split into two executable waves
- verification task was expanded

`beads-identity.md` already contains:
- epic `bd-120`
- task mapping from the older plan

### Refresh Behavior

- keep the epic ID if the change container is still correct
- keep any Beads task whose planning-wave mapping is still valid
- create new Beads tasks only for new or materially changed waves
- update `beads-identity.md` to match the latest planning-wave map

### Example Refresh Output

```text
✅ Refreshed Beads linkage for `duplicate-transaction-fix`

Epic: bd-120
Reused tasks:
- bd-121: Wave 1 — failing regression test

Updated tasks:
- bd-122: Wave 2a — database constraint fix
- bd-126: Wave 2b — API guard and logging
- bd-123: Wave 3 — verification and closeout

Next action:
- Run `modsim-apply duplicate-transaction-fix`
```

## Example 3: Planning Defect Stops Sync

### Context

OpenSpec change: `add-oauth`

Planning pack problems:
- Wave 1 task is too broad
- no verification command is listed
- `simulation-realism-required: true` is missing even though the change affects controller behavior

### Expected Output

```text
⚠️  Cannot sync `add-oauth` to Beads yet

Planning defects:
- Wave 1 task is too broad for one execution packet
- verification commands are missing from tasks.md
- simulation-realism-required flag is missing for control behavior changes

Next action:
- Fix the planning pack with `modsim-propose add-oauth`
```
