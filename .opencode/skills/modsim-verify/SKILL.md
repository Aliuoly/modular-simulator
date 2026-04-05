---
name: modsim-verify
description: Review an implementation against its modsim OpenSpec contract, linked Beads work, and required evidence.
license: MIT
compatibility: Requires openspec CLI and the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: modsim-contract
---

Verify whether an implementation satisfies the change contract and is ready to close.

**Input**: An optional change name. If omitted, infer it only when the current context is unambiguous.

**Steps**

1. Resolve the target change.
2. Run `openspec status --change "<name>" --json`.
3. Run `openspec instructions apply --change "<name>" --json` and read all `contextFiles`.
4. Read `beads-identity.md` when present and inspect linked execution evidence.
5. Check **Completeness**:
   - required artifacts
   - linked Beads state
   - verification evidence
   - review prerequisites
6. Check **Correctness**:
   - requirements and scenarios
   - code paths and tests
   - behavioral edge cases
7. Check **Coherence**:
   - design alignment
   - repo pattern alignment
   - Beads linkage consistency
8. If `simulation-realism-required: true` is present, include realism review.
9. Persist the review verdict, evidence summary, and next action to the linked Beads task before returning.

**Output**

Report exactly:
- `VERDICT: approved` or `VERDICT: changes-requested`
- `Spec compliance:` short assessment
- `Strengths:` brief bullets
- `Issues:` grouped by severity with file references
- `Realism assessment:` when required
- `Realism issues:` when required
- `Next action:` one short recommendation

**Guardrails**

- Prefer direct evidence over inference.
- Treat unmet requirements as more important than style issues.
- Do not approve stale or missing evidence.
- Append review notes but leave final `closed` and top-level `blocked` transitions to the orchestrator or archive flow.
