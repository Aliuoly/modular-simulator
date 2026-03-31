---
phase: 1
slug: failure-semantics-acceptance-gates
status: executed
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-29
updated: 2026-03-31
---

# Phase 1 — Validation Strategy

> Phase 1 has been fully executed. All four plans completed with summaries. 30 Phase 1 tests pass, 63 combined regression tests pass. Nyquist compliance can now be claimed.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 target |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1 -q` |
| **Full suite command** | `uv run --python 3.13 --active --no-sync python -m pytest tests/connection tests/phase1 -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1 -q`
- **After every plan wave:** Run `uv run --python 3.13 --active --no-sync python -m pytest tests/connection tests/phase1 -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | KERN-01 | collect/environment | `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1 --collect-only -q` | ✅ exists | ✅ green |
| 01-01-02 | 01 | 0 | KERN-01,KERN-02,KERN-03,KERN-05 | collect/integration | `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1 -q` | ✅ exists | ✅ green |
| 01-02-01 | 02 | 1 | KERN-03 | unit/integration | `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1/test_structural_rejection.py -q` | ✅ exists | ✅ green |
| 01-02-02 | 02 | 1 | KERN-03 | integration | `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1/test_structural_rejection.py tests/connection/test_error_catalog.py -q` | ✅ exists | ✅ green |
| 01-03-01 | 03 | 1 | KERN-01 | integration | `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1/test_failure_taxonomy.py -q` | ✅ exists | ✅ green |
| 01-03-02 | 03 | 1 | KERN-01 | integration | `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1/test_failure_taxonomy.py tests/connection/test_runtime_persistence_contract.py -q` | ✅ exists | ✅ green |
| 01-04-01 | 04 | 2 | KERN-02 | integration | `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1/test_macro_step_acceptance.py -q` | ✅ exists | ✅ green |
| 01-04-02 | 04 | 2 | KERN-05 | integration | `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1/test_physical_acceptance.py -q` | ✅ exists | ✅ green |
| 01-04-03 | 04 | 2 | KERN-02,KERN-05 | integration | `uv run --python 3.13 --active --no-sync python -m pytest tests/phase1/test_macro_step_acceptance.py tests/phase1/test_physical_acceptance.py -q` | ✅ exists | ✅ green |

*Status: ✅ green · ❌ red · ⚠️ flaky · ⬜ pending*

---

## Requirement Coverage

| Requirement | Covered By | Status | Notes |
|-------------|------------|--------|-------|
| `KERN-01` | `tests/phase1/test_failure_taxonomy.py`, `tests/connection/test_runtime_persistence_contract.py` | COVERED | Runtime diagnostics classify into four locked failure families with replay-hash and scenario-matrix evidence. |
| `KERN-02` | `tests/phase1/test_macro_step_acceptance.py` | COVERED | Macro-step acceptance transaction with rollback-on-reject, verified across accepted/rejected/second-run-after-rejection scenarios. |
| `KERN-03` | `tests/phase1/test_structural_rejection.py`, `tests/connection/test_error_catalog.py` | COVERED | Structural pre-step rejection routing with barrier failure translation, verified across compile/invariant/hydraulic/barrier sources. |
| `KERN-05` | `tests/phase1/test_physical_acceptance.py` | COVERED | Plant-level physical guards for negative inventory, invalid composition, non-finite values, and masking/fallback evidence. |

---

## Wave 0 Requirements

- [x] `tests/phase1/test_failure_taxonomy.py` — stubs for `KERN-01`
- [x] `tests/phase1/test_macro_step_acceptance.py` — stubs for `KERN-02`
- [x] `tests/phase1/test_structural_rejection.py` — stubs for `KERN-03`
- [x] `tests/phase1/test_physical_acceptance.py` — stubs for `KERN-05`
- [x] `pip3 install -e . pytest` — framework install in a Python 3.13 environment

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Replay fixture realism review | KERN-01 | Scenario realism depends on choosing representative plant cases, not just executable tests | Review each Phase 1 fixture manifest and confirm it covers one of the four locked scenario classes with an explicit expected failure family. |
| Accepted-state publication audit | KERN-02 | Non-observability readers may still bypass the publication buffer and need code inspection | Read changed runtime/session call sites and confirm no public consumer reads in-flight mutable candidate state during a rejected macro-step. |

---

## Validation Audit 2026-03-31

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 9 |
| Escalated | 0 |

### Audit Notes

- Phase 1 execution completed: all four plans (01-01 through 01-04) have summaries and passing tests.
- 30 Phase 1 tests pass across four test modules.
- 63 combined regression tests pass when running Phase 1 alongside connection tests.
- All implementation files now exist: `phase1_failure_semantics.py`, `structural_rejection.py`, `phase1_runtime_diagnostics.py`, `macro_step_acceptance.py`, `plant_physical_acceptance.py`.
- Barrier message prefix regression was auto-fixed during execution; rollback prefix preserved for backward compatibility.
- `uv --active --no-sync` required for verification due to unconditional PETSc dependency in `uv` sync.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ✅ Phase 1 execution validated — 2026-03-31
