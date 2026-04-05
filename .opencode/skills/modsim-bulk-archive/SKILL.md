---
name: modsim-bulk-archive
description: Archive multiple completed modsim changes with conflict detection, evidence checks, and linked Beads closure review.
license: MIT
compatibility: Requires openspec CLI, Beads CLI, and the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: modsim-contract
---

Archive multiple completed modsim changes in one operation.

**Input**: No change name required. Prompt for explicit selection.

**Steps**

1. Run `openspec list --json` and gather active changes.
2. Let the user choose which changes to archive.
3. For each selected change, inspect:
   - artifact status
   - linked Beads closure state
   - verification and review state
   - persisted packet-level implementation and review notes in linked Beads items
   - delta spec coverage
4. Detect capability conflicts across selected changes.
5. Resolve conflicts using repo evidence and a justified sync order.
6. Show a consolidated readiness table.
7. Confirm whether to archive all selected changes or only fully ready ones.
8. Sync specs as needed, then archive each confirmed change.
9. Report archived, skipped, failed, and conflict-resolution outcomes.

**Output**

Report:
- `Archived:` changes archived successfully
- `Skipped:` changes intentionally skipped
- `Failed:` changes that could not be archived
- `Conflicts:` capability conflicts and chosen resolution

**Guardrails**

- Always prompt for selection.
- Detect conflicts before archiving.
- Use evidence from code, review, and Beads closure state.
- Do not use `tasks.md` checkboxes as the batch archive gate.
