# Beads Sync Templates

## Epic Creation

```bash
bd create "[<change-name>] epic" \
  --type epic \
  --priority 0 \
  --labels "change:<change-name>,workflow:modsim,artifact:beads-identity" \
  --json
```

## Child Task Creation

```bash
bd create "[<change-name>] <wave-title>" \
  --priority <smart-priority> \
  --type <smart-type> \
  --labels "change:<change-name>,wave:<wave-slug>,complexity:<low|medium|high>,workflow:modsim" \
  --json
```

## Dependency Creation

### Sequential dependencies within a change

```bash
bd dep add <later-task-id> <earlier-task-id> --type blocks
```

### Related verification or documentation work

```bash
bd dep add <verification-task-id> <implementation-task-id> --type related
```

### Parent-child relationships

```bash
bd dep add <task-id> <epic-id> --type parent-child
```

### Discovered execution follow-up

```bash
bd dep add <discovery-id> <parent-task-id> --type discovered-from
```

## Linkage Rules

- reuse an existing epic ID when `beads-identity.md` already points to the right change container
- reuse an existing child task ID when the planning-wave mapping is still valid
- create a new child task only when the planning wave is new or materially changed
- update `beads-identity.md` after every create or refresh step
