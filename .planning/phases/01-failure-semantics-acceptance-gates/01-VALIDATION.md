---
phase: 1
slug: failure-semantics-acceptance-gates
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-29
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 target |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --python 3.13 python -m pytest tests/phase1 --collect-only -q` |
| **Full suite command** | `python3 -m pytest tests/connection tests/persistence tests/phase1 -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --python 3.13 python -m pytest tests/phase1 --collect-only -q`
- **After every plan wave:** Run `python3 -m pytest tests/connection tests/persistence tests/phase1 -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | KERN-01 | collect/environment | `uv run --python 3.13 python -m pytest tests/phase1 --collect-only -q` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 0 | KERN-01,KERN-02,KERN-03,KERN-05 | collect/integration | `uv run --python 3.13 python --version && uv run --python 3.13 python -m pytest tests/phase1 --collect-only -q` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | KERN-03 | unit/integration | `uv run --python 3.13 python -m pytest tests/phase1/test_structural_rejection.py -q` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | KERN-03 | integration | `uv run --python 3.13 python -m pytest tests/phase1/test_structural_rejection.py tests/connection/test_error_catalog.py -q` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 1 | KERN-01 | integration | `uv run --python 3.13 python -m pytest tests/phase1/test_failure_taxonomy.py -q` | ❌ W0 | ⬜ pending |
| 01-03-02 | 03 | 1 | KERN-01 | integration | `uv run --python 3.13 python -m pytest tests/phase1/test_failure_taxonomy.py tests/connection/test_runtime_persistence_contract.py -q` | ❌ W0 | ⬜ pending |
| 01-04-01 | 04 | 2 | KERN-02 | integration | `uv run --python 3.13 python -m pytest tests/phase1/test_macro_step_acceptance.py -q` | ❌ W0 | ⬜ pending |
| 01-04-02 | 04 | 2 | KERN-05 | integration | `uv run --python 3.13 python -m pytest tests/phase1/test_physical_acceptance.py -q` | ❌ W0 | ⬜ pending |
| 01-04-03 | 04 | 2 | KERN-02,KERN-05 | integration | `uv run --python 3.13 python -m pytest tests/phase1/test_macro_step_acceptance.py tests/phase1/test_physical_acceptance.py tests/controller_contract_harness.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/phase1/test_failure_taxonomy.py` — stubs for `KERN-01`
- [ ] `tests/phase1/test_macro_step_acceptance.py` — stubs for `KERN-02`
- [ ] `tests/phase1/test_structural_rejection.py` — stubs for `KERN-03`
- [ ] `tests/phase1/test_physical_acceptance.py` — stubs for `KERN-05`
- [ ] `pip3 install -e . pytest` — framework install in a Python 3.13 environment

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Replay fixture realism review | KERN-01 | Scenario realism depends on choosing representative plant cases, not just executable tests | Review each Phase 1 fixture manifest and confirm it covers one of the four locked scenario classes with an explicit expected failure family. |
| Accepted-state publication audit | KERN-02 | Non-observability readers may still bypass the publication buffer and need code inspection | Read changed runtime/session call sites and confirm no public consumer reads in-flight mutable candidate state during a rejected macro-step. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
