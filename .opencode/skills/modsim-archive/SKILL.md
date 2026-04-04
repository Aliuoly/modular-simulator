---
name: modsim-archive
description: Archive a completed modsim change after checking evidence, review state, Beads closure, and spec sync needs.
license: MIT
compatibility: Requires openspec CLI, Beads CLI, and the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: modsim-contract
---

Archive a completed modsim change only when closure is supported by evidence.

**Input**: An optional change name. If omitted, infer it only when the current context is unambiguous.

**Steps**

1. Resolve the target change.
2. Run `openspec status --change "<name>" --json` and inspect required artifact completion.
3. Read `beads-identity.md` and inspect linked Beads closure state.
4. Confirm verification evidence and independent review exist.
5. Confirm realism review passed when required.
6. Assess whether delta spec sync is still needed.
7. Confirm landing state or intentional staging state.
8. Archive the change only after warning on incomplete evidence and getting confirmation when needed.

**Output**

Report:
- `Change:` name
- `Archive path:` target location
- `Specs:` synced, skipped, or not needed
- `Beads:` closure state summary
- `Warnings:` explicit warnings carried into archive, if any

**Guardrails**

- Archive is evidence-driven, not checkbox-driven.
- Do not use `tasks.md` checkboxes as the archive gate.
- Preserve `.openspec.yaml` when moving the change directory.
- Show explicit warnings before archiving incomplete work.
