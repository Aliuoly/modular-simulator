---
phase: 3
slug: benchmark-harness-disciplined-baseline-comparison
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-30
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run python -m pytest tests/connection/test_benchmark_contracts.py -q` |
| **Full suite command** | `uv run python -m pytest tests/connection/test_benchmark_contracts.py tests/connection/test_benchmark_harness.py tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/connection/test_benchmark_contracts.py -q`
- **After every plan wave:** Run `uv run python -m pytest tests/connection/test_benchmark_contracts.py tests/connection/test_benchmark_harness.py tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | PERF-02,SOLV-01 | contract | `uv run python -m pytest tests/connection/test_benchmark_contracts.py -q` | ❌ planned | ⬜ pending |
| 03-01-02 | 01 | 1 | PERF-02,SOLV-01 | contract | `uv run python -m pytest tests/connection/test_benchmark_contracts.py -q` | ❌ planned | ⬜ pending |
| 03-02-01 | 02 | 2 | PERF-01,DELY-04 | contract/integration | `uv run python -m pytest tests/connection/test_benchmark_harness.py -q` | ❌ planned | ⬜ pending |
| 03-02-02 | 02 | 2 | PERF-01,PERF-02,SOLV-01 | integration | `uv run python -m pytest tests/connection/test_benchmark_harness.py tests/connection/test_examples_benchmarks.py -q` | ❌ planned | ⬜ pending |
| 03-03-01 | 03 | 3 | PERF-03,PERF-04,SOLV-03 | contract | `uv run python -m pytest tests/connection/test_benchmark_reporting.py -q` | ❌ planned | ⬜ pending |
| 03-03-02 | 03 | 3 | PERF-03,PERF-04,SOLV-03 | integration/docs | `uv run python -m pytest tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q` | ❌ planned | ⬜ pending |

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
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
