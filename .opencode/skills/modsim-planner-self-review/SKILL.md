---
name: modsim-planner-self-review
description: Pressure-test a modsim OpenSpec planning pack for defects, hidden risks, and execution gaps before reporting readiness.
license: MIT
compatibility: Requires the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.1"
  workflow: modsim-contract
---

Run a real self-review of a `modsim-contract` planning pack before reporting readiness.

This is a defect-finding pass, not a formatting pass. Assume an implementation agent with weak taste and limited context will execute the pack. Look for anything that would cause wrong code, scope drift, fake readiness, or stalled execution.

**Input**: An updated change pack containing `proposal.md`, `specs/**/*.md`, `design.md`, `tasks.md`, and `beads-identity.md`.

**Review Checks**

1. Contract coverage: every promised behavior, requirement, and boundary in the proposal/specs has matching design intent, task coverage, and verification evidence.
2. Scope discipline: no broadened claims, contradictory scope, or missing out-of-scope boundaries across artifacts.
3. Execution viability: waves can run in order without hidden prerequisites, missing files, impossible sequencing, or dependency deadlocks.
4. Interface consistency: names, APIs, file paths, data shapes, flags, and artifact references stay consistent across proposal, specs, design, tasks, and Beads linkage.
5. Bug traps: catch likely implementation mistakes such as missing edge cases, error paths, state transitions, integration seams, migrations/backfills, ordering hazards, or regressions that the tasks fail to cover.
6. Verification quality: commands are concrete and would actually detect the intended failure or regression instead of producing weak evidence.
7. Review routing: `simulation-realism-required: true` appears when the change touches simulation behavior, engineering heuristics, thermo, chemistry, controls, fluids, or economics realism, and the realism-sensitive areas are named clearly enough for review.
8. Beads linkage: `beads-identity.md` contains real Beads IDs, correct wave mapping, and no stale or placeholder linkage.
9. Placeholder and filler scan: remove TODOs, unresolved blanks, vague steps, and any instruction that forces executors to guess.

**Output**

Return one status:
- `Self-review: passed`
- `Self-review: fixed inline`
- `Self-review: blocked`

Then report:
- `Findings:` decisive gaps or `none`
- `Files changed:` only when fixes were made inline
- `Blocking decisions:` only when a real unresolved decision remains

**Guardrails**

- Fix issues inline before reporting readiness.
- If a real product, scope, or technical decision is still missing, return `Self-review: blocked` instead of pretending the pack is ready.
- Do not do a separate review dispatch. This is an inline pressure test.
