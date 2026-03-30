# Kernel Benchmark Harness Contract

Phase 3 benchmark reports use exactly three workload ids:

- `ammonia_recycle_warm`
- `staged_delay_control_disturbance`
- `checkpoint_restart_reconfigure`

Every candidate runs under the same checkpoint id, tolerance profile, physical-acceptance profile, telemetry contract version, and delay semantics label captured by the workload and candidate contracts.

## Hard Gates

- `minimum_rtf_gate=4.0`
- `accepted_step_p95_fraction_of_step_size=0.25`

Accepted-step latency gates use accepted attempts only. Reports compute accepted-step median, p95, and p99 without mixing in rejected attempts.

## Headline Target

- `headline_rtf_target=100.0`

This headline target is reported separately from the hard viability gate so Phase 3 can show preferred headroom without turning `100x` into the minimum pass line.

## Disqualification Reasons

Rank-blocking disqualification reasons are exactly:

- `fallback_used`
- `physical_acceptance_failure`
- `hidden_solver_failure`
- `clipping_masked_apparent_stability`
- `hidden_recovery`
- `telemetry_contract_violation`

Any candidate with one of these reasons is shown in the report but excluded from viable ranking.

## Baseline Visibility Rule

The split/SciPy baseline is always shown in the final report even when it is disqualified. Ranking excludes disqualified runs, but reporting never hides the disciplined baseline row.
