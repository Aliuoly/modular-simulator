---
name: modsim-continue
description: Create or update the next ready artifact for an existing modsim OpenSpec change.
license: MIT
compatibility: Requires openspec CLI and the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: modsim-contract
---

Create or update the next ready artifact for an existing modsim change.

**Input**: An optional change name. If omitted, infer it only when the current context is unambiguous.

**Steps**

1. Resolve the target change.
2. Run `openspec status --change "<name>" --json`.
3. If all artifacts are complete, stop and suggest the next workflow step.
4. If one or more artifacts are ready, select the next ready artifact.
5. Run `openspec instructions <artifact-id> --change "<name>" --json`.
6. Read completed dependency artifacts first.
7. Update exactly one artifact.
8. Re-run status and report what is now unlocked.

**Output**

Report:
- `Change:` name
- `Artifact:` file created or updated
- `Progress:` current artifact status
- `Unlocked:` next artifacts or apply readiness

**Guardrails**

- Create one artifact per invocation.
- Never skip dependency order.
- Ask only when missing information materially changes the artifact.
