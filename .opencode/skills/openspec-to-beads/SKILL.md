---
name: openspec-to-beads
description: Create or refresh linked Beads execution items from a modsim OpenSpec change during planning or execution handoff.
license: MIT
compatibility: Requires openspec CLI, Beads CLI, and the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: modsim-contract
---

Create or refresh the Beads execution items linked to a `modsim-contract` change.

**Input**: A change name, or a planning context that clearly identifies the target change.

**Steps**

1. Resolve the target change.
2. Verify prerequisites:
   ```bash
   openspec show <change-name>
   bd list --json
   ```
3. Read:
   - `proposal.md`
   - `specs/**/*.md`
   - `design.md` when present
   - `tasks.md`
   - `beads-identity.md` when present
4. Validate the planning pack:
   - planning waves are execution-ready
   - dependencies are clear
   - verification tasks exist
   - realism review is flagged when required
   - `beads-identity.md` needs creation or refresh only when linkage is missing or stale
5. Stop and report planning defects before creating or refreshing Beads items.
6. Create or refresh one Beads epic per OpenSpec change.
7. Create or refresh child Beads tasks from the planning waves in `tasks.md`.
8. Apply dependency heuristics from `data/dependency-patterns.md`.
9. Apply priority, type, and complexity heuristics from `data/priority-rules.md`.
10. Reuse existing Beads IDs when the planning-wave mapping is still valid.
11. Write the final epic/task mapping back into `beads-identity.md`.

**Output**

Report:
- `Change:` name
- `Epic:` Beads epic ID
- `Tasks:` created or refreshed child task IDs
- `Mapping:` planning-wave to task mapping summary
- `Blocked:` planning defects that prevented sync, if any
- `Next action:` usually `modsim-apply`

**Guardrails**

- Do not sync from an incomplete or contradictory planning pack.
- Do not duplicate existing Beads tasks when the current mapping is still valid.
- Do not leave stale IDs in `beads-identity.md`.
- Do not treat Beads as the spec source of truth.
- Keep examples and templates aligned with the `modsim-*` lifecycle.
