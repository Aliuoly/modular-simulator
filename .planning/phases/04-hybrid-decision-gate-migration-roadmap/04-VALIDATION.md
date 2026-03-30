---
phase: 4
slug: hybrid-decision-gate-migration-roadmap
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-30
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py -q` |
| **Full suite command** | `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py tests/connection/test_kernel_direction_decision_example.py tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py -q`
- **After every plan wave:** Run `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py tests/connection/test_kernel_direction_decision_example.py tests/connection/test_benchmark_reporting.py tests/connection/test_examples_benchmarks.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | PERF-05 | contract | `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py -q` | ❌ | ⬜ pending |
| 04-01-02 | 01 | 1 | PERF-05, SOLV-05 | contract/integration | `uv run python -m pytest tests/connection/test_benchmark_decision_gate.py -q` | ❌ | ⬜ pending |
| 04-02-01 | 02 | 2 | SOLV-04 | contract/docs | `uv run python -m pytest tests/connection/test_kernel_direction_decision_example.py -q` | ❌ | ⬜ pending |
| 04-02-02 | 02 | 2 | SOLV-04, SOLV-05 | docs/integration | `uv run python -m pytest tests/connection/test_kernel_direction_decision_example.py tests/connection/test_examples_benchmarks.py -q` | ❌ | ⬜ pending |

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
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
