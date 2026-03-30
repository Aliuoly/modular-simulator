# Phase 5: Runnable solver candidates - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 05-runnable-solver-candidates
**Areas discussed:** Candidate depth, Harness selection flow, Delay-state fidelity, Comparison readiness

---

## Candidate depth

| Option | Description | Selected |
|--------|-------------|----------|
| Runnable sundials + PETSc | Deliver a runnable SUNDIALS-backed path and a runnable PETSc-backed path in Phase 5. | |
| Runnable sundials, PETSc spike | Deliver a runnable SUNDIALS path now and keep PETSc at spike level only. | |
| Runnable sundials only | Deliver only the first post-SciPy path in Phase 5. | |
| SUNDIALS + PETSc (Recommended) | Lock a real SUNDIALS-backed candidate first and pair it with a real PETSc comparison path after ecosystem research. | ✓ |
| SUNDIALS + broader alt | Lock SUNDIALS first and leave the second slot open for another researched candidate. | |
| Open candidate bake-off | Keep the concrete candidates unlocked for more research. | |

**User's choice:** `SUNDIALS + PETSc (Recommended)`
**Notes:** The user first broadened scope with "Anything is fair game, even non python solutions" and asked for online research, then raised Julia-based solvers. External research confirmed Julia SciML as credible, but the user accepted the recommended milestone-closing set of a real SUNDIALS-backed path plus a real PETSc-backed path.

---

## Harness selection flow

| Option | Description | Selected |
|--------|-------------|----------|
| Registry + explicit IDs (Recommended) | Add a small candidate registry/factory keyed by stable IDs and let the wrapper run an explicit selected set. | |
| Auto-discover installed | Probe the environment for available solver backends and run whatever is installed. | |
| Hard-code comparison set | Keep wiring local to the example wrapper and hard-code the comparison factories there for now. | ✓ |

**User's choice:** `Hard-code comparison set`
**Notes:** This intentionally keeps Phase 5 focused on getting the real candidates runnable instead of adding a reusable registry layer before the milestone comparison exists.

---

## Delay-state fidelity

| Option | Description | Selected |
|--------|-------------|----------|
| Full restore parity (Recommended) | Require each candidate to support checkpoint restore and delay-state round-trip parity from comparable accepted snapshots. | ✓ |
| Warm-start parity only | Require comparable warm-start behavior but allow weaker restore support initially. | |
| Fresh-start allowed | Allow reinitialization from model state instead of replaying comparable delay-state snapshots. | |

**User's choice:** `Full restore parity (Recommended)`
**Notes:** This preserves the fairness contract from Phases 2 and 3 and prevents Phase 5 from claiming same-workload comparison on weaker startup conditions.

---

## Comparison readiness

| Option | Description | Selected |
|--------|-------------|----------|
| Runnable + same canon (Recommended) | The split baseline, SUNDIALS candidate, and PETSc candidate all run the fixed three-workload canon through the same harness and produce comparable reports, even if some are disqualified. | ✓ |
| Runnable + partial canon | All candidates run, but only on a subset of the canon in Phase 5. | |
| Adapters only | Implement adapters and smoke checks now, leaving full same-workload comparison for later. | |

**User's choice:** `Runnable + same canon (Recommended)`
**Notes:** The user wants milestone completion, so adapters-only or partial-canon evidence was treated as insufficient.

---

## the agent's Discretion

- Exact binding choice or integration layer for the SUNDIALS-backed path.
- Exact binding choice or integration layer for the PETSc-backed path.
- Exact local API shape for the hard-coded comparison set in the Phase 5 benchmark/example entry points.

## Deferred Ideas

- Julia-based solver comparison path.
- Broader non-SciPy ecosystem bake-off beyond the locked SUNDIALS and PETSc set.
