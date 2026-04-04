---
name: modsim-sync
description: Sync delta specs from a modsim change into the main OpenSpec specs without losing unaffected content.
license: MIT
compatibility: Requires openspec CLI and the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: modsim-contract
---

Sync delta specs from a modsim change into the main spec set.

**Input**: An optional change name. If omitted, infer it only when the current context is unambiguous.

**Steps**

1. Resolve the target change.
2. Read delta specs under `openspec/changes/<name>/specs/*/spec.md`.
3. Read the corresponding main specs under `openspec/specs/<capability>/spec.md`.
4. Apply delta changes intelligently:
   - `ADDED`: add the new requirement or merge it if it already exists
   - `MODIFIED`: update only the intended parts and preserve unaffected scenarios
   - `REMOVED`: remove the requirement block
   - `RENAMED`: rename the requirement cleanly
5. Create a new main spec if the capability does not exist yet.
6. Report the exact capabilities and requirements changed.

**Output**

Report:
- `Change:` name
- `Capabilities:` updated capabilities
- `Changes:` requirements added, modified, removed, or renamed
- `Result:` sync complete or blocked with reason

**Guardrails**

- Read both delta and main specs before editing.
- Preserve unaffected content.
- Keep the merge idempotent.
- Ask only when the delta is genuinely ambiguous.
