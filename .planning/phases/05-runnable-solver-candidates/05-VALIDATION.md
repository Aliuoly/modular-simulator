---
phase: 5
slug: runnable-solver-candidates
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-03-30
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run python -m pytest tests/connection/test_runnable_candidate_contracts.py tests/connection/test_sundials_kernel_adapter.py tests/connection/test_petsc_kernel_adapter.py tests/connection/test_examples_benchmarks.py -q` |
| **Full suite command** | `uv run python -m pytest tests/connection/test_runnable_candidate_contracts.py tests/connection/test_sundials_kernel_adapter.py tests/connection/test_petsc_kernel_adapter.py tests/connection/test_examples_benchmarks.py tests/connection/test_benchmark_harness.py tests/connection/test_benchmark_reporting.py tests/connection/test_kernel_direction_decision_example.py -q` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/connection/test_runnable_candidate_contracts.py tests/connection/test_sundials_kernel_adapter.py tests/connection/test_petsc_kernel_adapter.py tests/connection/test_examples_benchmarks.py -q`
- **After every plan wave:** Run `uv run python -m pytest tests/connection/test_runnable_candidate_contracts.py tests/connection/test_sundials_kernel_adapter.py tests/connection/test_petsc_kernel_adapter.py tests/connection/test_examples_benchmarks.py tests/connection/test_benchmark_harness.py tests/connection/test_benchmark_reporting.py tests/connection/test_kernel_direction_decision_example.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | SOLV-06 | contract | `uv run python -m pytest tests/connection/test_runnable_candidate_contracts.py -q` | ❌ | ⬜ pending |
| 05-01-02 | 01 | 1 | SOLV-06 | contract/config | `uv run python -m pytest tests/connection/test_runnable_candidate_contracts.py -q` | ❌ | ⬜ pending |
| 05-02-01 | 02 | 2 | DELY-05 | adapter | `uv run python -m pytest tests/connection/test_sundials_kernel_adapter.py -q` | ❌ | ⬜ pending |
| 05-02-02 | 02 | 2 | SOLV-06 | adapter/runtime | `uv run python -m pytest tests/connection/test_sundials_kernel_adapter.py tests/connection/test_benchmark_harness.py -q` | ❌ | ⬜ pending |
| 05-03-01 | 03 | 2 | DELY-05 | adapter | `uv run python -m pytest tests/connection/test_petsc_kernel_adapter.py -q` | ❌ | ⬜ pending |
| 05-03-02 | 03 | 2 | SOLV-06 | adapter/runtime | `uv run python -m pytest tests/connection/test_petsc_kernel_adapter.py tests/connection/test_benchmark_harness.py -q` | ❌ | ⬜ pending |
| 05-04-01 | 04 | 3 | PERF-06 | wrapper/report | `uv run python -m pytest tests/connection/test_examples_benchmarks.py -q` | ✅ | ⬜ pending |
| 05-04-02 | 04 | 3 | PERF-06 | wrapper/report | `uv run python -m pytest tests/connection/test_examples_benchmarks.py tests/connection/test_kernel_direction_decision_example.py tests/connection/test_benchmark_reporting.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 35s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
