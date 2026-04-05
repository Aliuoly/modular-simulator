---
name: modsim-propose
description: Create a complete modsim OpenSpec change pack and sync linked Beads execution items when scope is stable.
license: MIT
compatibility: Requires openspec CLI and the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: modsim-contract
---

Create a full `modsim-contract` change pack and linked Beads execution items.

**Input**: A stable change request or a change name plus enough detail to build the planning pack.

**Steps**

1. Confirm the request is stable enough for planning.
2. If the request is still fuzzy, stop and route to `modsim-explore`.
3. Resolve the change name in kebab-case.
4. Create or reuse the change with:
   ```bash
   openspec new change "<name>" --schema modsim-contract
   ```
5. Run:
   ```bash
   openspec status --change "<name>" --json
   ```
   Use the result to determine artifact order and apply requirements.
6. Generate or update `proposal.md`, `specs/**/*.md`, `design.md`, `tasks.md`, and `beads-identity.md` in dependency order.
   - If the change depends on governing scientific, mathematical, thermodynamic, hydraulic, control, or economic equations, carry those equations into `specs/**/*.md` and `design.md` instead of collapsing them into prose summaries.
   - If exact equation form is still unresolved, stop and route back to `modsim-explore` instead of creating a fake-ready pack.
7. Keep `tasks.md` execution-ready with:
    - a dependency gate
    - numbered waves
    - exact files when known
    - verification commands
    - expected evidence
    - explicit TDD notes for behavior changes
    - equation-fidelity verification when specs freeze governing equations or named closures
8. Create or refresh the linked Beads epic and child tasks from the planning waves.
9. Write Beads IDs and wave mapping back into `beads-identity.md`.
10. Run `modsim-planner-self-review` as a defect-finding pass. Fix gaps, contradictions, hidden dependencies, weak verification, and likely implementation bug traps inline before continuing.
11. Re-run `openspec status --change "<name>" --json` and confirm the pack is ready for `modsim-apply`.

Use the `beads` skill when command usage or workflow details are unclear.

**Output**

Report:
- `Change:` name and path
- `Artifacts:` created or updated files
- `Beads:` epic and child task IDs
- `Ready:` say ready only if required artifacts exist, self-review passed, Beads sync succeeded, and `beads-identity.md` contains real IDs

**Guardrails**

- Keep the scope tight.
- Ask only the minimum blocking question.
- If planning reveals material uncertainty, stop and route back to `modsim-explore`.
- Do not let equation-bearing scientific requirements degrade into prose-only claims during proposal or self-review.
- Do not leave placeholder Beads IDs in the pack.
