# Kernel Migration Roadmap

This roadmap keeps architecture direction separate from solver-stack replacement. The default direction remains `hybrid_coupled`, while stack changes require benchmark evidence from the fixed Phase 3 canon.

## Stage 1: `disciplined_scipy` hardening

- Keep the Phase 3 workload basis fixed to `ammonia_recycle_warm`, `staged_delay_control_disturbance`, and `checkpoint_restart_reconfigure`.
- Preserve the current Phase 3 benchmark fairness rules and hard gates before any stack comparison.
- Treat this stage as baseline hardening, not as proof that SciPy must be replaced.

## Stage 2: `hybrid_coupled` default direction

- Keep `hybrid_coupled` as the default kernel direction unless evidence disproves it.
- Preserve `PlantBackendSession` and the `CandidateKernelAdapter` seam so architecture work does not force a public runtime rewrite.
- Use the decision gate to separate architecture direction from solver-stack choice.

## Stage 3: `sundials4py` adapter spike

- Explore `sundials4py` first when the disciplined SciPy path misses the Phase 3 gates and profiling shows solver-core dominance.
- Keep the migration scoped to the solver layer so `PlantBackendSession` and `CandidateKernelAdapter` remain stable seams.
- Justify the spike with explicit stability improvement, latency improvement, deployment risk, and compatibility notes.

## Stage 4: `petsc4py` later only if justified

- `petsc4py` is later escalation only if benchmarks justify it after `disciplined_scipy` hardening and the `sundials4py` adapter spike.
- Reserve PETSc for cases that clearly need sparse nonlinear solver composition, preconditioning control, or other PETSc-sized machinery.
- Keep the facade-preservation rule in force even if PETSc becomes necessary.

The exact migration sequence is `disciplined_scipy` -> `hybrid_coupled` -> `sundials4py` adapter spike -> PETSc later only if justified.
