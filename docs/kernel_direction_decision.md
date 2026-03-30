# Kernel Direction Decision

Phase 4 is an evidence-synthesis layer over the verified Phase 3 benchmark substrate, not a new benchmark system and not an immediate solver rewrite.

The default kernel direction remains `hybrid_coupled`.

The Phase 3 workload canon used for this decision is fixed to:

- `ammonia_recycle_warm`
- `staged_delay_control_disturbance`
- `checkpoint_restart_reconfigure`

The current disciplined SciPy baseline stays acceptable when the verified Phase 3 report keeps the disciplined split candidate viable under the existing hard gates, including `minimum_rtf_gate=4.0` and the accepted-step latency budget.

Leaving SciPy requires benchmark evidence, not intuition. The minimum evidence bar is:

- representative misses on the same Phase 3 workloads and gates
- no hidden fallback or malformed telemetry invalidating the comparison
- profiling that shows solver-core dominance rather than repo-local Python glue

If the baseline stops being sufficient and the benchmark evidence shows a real solver-core limit, `sundials4py` is the first serious post-SciPy path.

`petsc4py` is not the first escalation path. PETSc/`petsc4py` is a later escalation only if benchmarks justify it after the disciplined SciPy path and the `sundials4py` path still leave a material gap.

The comparison basis for Phase 4 is the same workload canon and fairness contract across `disciplined_scipy`, `sundials4py`, and `petsc4py`.
