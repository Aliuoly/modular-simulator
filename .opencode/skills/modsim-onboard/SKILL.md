---
name: modsim-onboard
description: Teach the repo-owned Modsim OpenSpec plus Beads workflow by walking through one real end-to-end change.
license: MIT
compatibility: Requires openspec CLI, Beads CLI, and the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: modsim-contract
---

Teach the Modsim OpenSpec + Beads workflow by walking through one real end-to-end change.

**Input**: A request for onboarding, tutorial mode, or a guided walkthrough.

**Steps**

1. Check that OpenSpec and Beads are available.
2. Explain the workflow stages:
   - `modsim-explore`
   - `modsim-propose`
   - `modsim-apply`
   - `modsim-verify`
   - `modsim-sync`
   - `modsim-archive`
3. Choose a small real task.
4. Demonstrate explore mode briefly.
5. Create a change with `modsim-contract`.
6. Draft `proposal.md`, `specs/**/*.md`, `design.md`, `tasks.md`, and `beads-identity.md`.
7. Create or refresh linked Beads work.
8. Demonstrate apply, verify, sync, and archive.
9. Explain how to resume later with `modsim-continue` or `modsim-apply`.

**Output**

Provide:
- the current phase
- the file or command being demonstrated
- the exact next step the user can run alone

**Guardrails**

- Keep the teaching task small and real.
- Keep narration light and grounded in actual files.
- Pause at natural boundaries and let the user steer.
