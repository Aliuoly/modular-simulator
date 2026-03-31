---
phase: 2
slug: kernel-adapter-warm-starts-delay-state
status: audited
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-29
updated: 2026-03-30
---

# Phase 2 - Validation Strategy

> Audited Nyquist validation coverage for the completed Phase 2 execution artifacts.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_kernel_adapter_contract.py -q` |
| **Full suite command** | `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_kernel_adapter_contract.py tests/connection/test_kernel_adapter_restore.py tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py -q` |
| **Estimated runtime** | `~1s local targeted` |

---

## Sampling Rate

- **After every task commit:** Run the task-local pytest command declared in the plan verify block using `PYTHONPATH=src uv run --no-project python3 -m pytest ...`.
- **After every plan wave:** Run `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_kernel_adapter_contract.py tests/connection/test_kernel_adapter_restore.py tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py -q`.
- **Before `/gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** `~1s` for the targeted Phase 2 regression set in this workspace.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | SOLV-02 | contract | `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_kernel_adapter_contract.py -q` | ✅ | ✅ green |
| 02-01-02 | 01 | 1 | SOLV-02, DELY-02 | integration | `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_kernel_adapter_contract.py -q` | ✅ | ✅ green |
| 02-02-01 | 02 | 2 | KERN-04 | integration | `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_kernel_adapter_restore.py -q` | ✅ | ✅ green |
| 02-02-02 | 02 | 2 | KERN-04 | regression | `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_kernel_adapter_restore.py -q` | ✅ | ✅ green |
| 02-03-01 | 03 | 3 | DELY-01, DELY-02, DELY-03 | regression | `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py -q` | ✅ | ✅ green |
| 02-03-02 | 03 | 3 | DELY-01, DELY-02 | docs/contract | `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py -q` | ✅ | ✅ green |
| 02-04-01 | 04 | 4 | SOLV-02, DELY-02 | contract | `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_kernel_adapter_contract.py -q` | ✅ | ✅ green |
| 02-04-02 | 04 | 4 | SOLV-02, DELY-02 | regression | `PYTHONPATH=src uv run --no-project python3 -m pytest tests/connection/test_kernel_adapter_contract.py tests/connection/test_split_kernel_delay_mapping.py -q` | ✅ | ✅ green |

*Status: ✅ green · ❌ red · ⚠️ flaky · ⬜ pending*

---

## Requirement Coverage

| Requirement | Covered By | Status | Notes |
|-------------|------------|--------|-------|
| `SOLV-02` | `tests/connection/test_kernel_adapter_contract.py`, `tests/connection/test_split_kernel_delay_mapping.py` | COVERED | Contract tests prove core-only adapters remain valid, optional solver capabilities stay separate, and the gap-closure protocol split keeps explicit delay mapping without enlarging the required seam. |
| `KERN-04` | `tests/connection/test_kernel_adapter_restore.py` | COVERED | Canonical restore coverage verifies accepted-snapshot warm starts, explicit unsafe-restore failure, backend save/load wiring, and `post_edit_recovery` routing. |
| `DELY-01` | `tests/connection/test_split_kernel_delay_mapping.py`, `tests/connection/test_runtime_persistence_contract.py` | COVERED | Split baseline delay semantics remain explicit and round-trip safely through resume, checkpoint reload, and edit recovery paths. |
| `DELY-02` | `tests/connection/test_kernel_adapter_contract.py`, `tests/connection/test_split_kernel_delay_mapping.py`, `docs/kernel_adapter_delay_semantics.md` | COVERED | The required core declares delay semantics while mapping-aware adapters publish explicit transport-history replacement rules through `SupportsDelayStateMapping`. |
| `DELY-03` | `tests/connection/test_split_kernel_delay_mapping.py`, `tests/connection/test_runtime_persistence_contract.py` | COVERED | Adapter-visible delay bundles are restored safely after snapshot resume, checkpoint reload, and `post_edit_recovery`. |

---

## Wave 0 Requirements

Existing infrastructure covers all Phase 2 requirements. No Wave 0 gaps remain.

---

## Manual-Only Verifications

None. All Phase 2 requirements have automated verification coverage.

---

## Validation Audit 2026-03-30

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

### Audit Notes

- Existing `02-VALIDATION.md` was stale: it still reflected a draft Wave 0 plan, marked every task pending, and missed the executed gap-closure Plan `02-04`.
- Audited `02-01` through `02-04` plan and summary artifacts plus the existing `02-VERIFICATION.md` report.
- Confirmed the targeted Phase 2 test files exist and directly cover every Phase 2 requirement.
- The original `uv run python -m pytest ...` commands attempted full project dependency resolution and failed in this workspace on `petsc4py`/PETSc bootstrap because BLAS is unavailable.
- Replaced those commands with targeted audited commands using `PYTHONPATH=src uv run --no-project python3 -m pytest ...`, which isolate the Phase 2 suites from unrelated solver backend bootstrap.
- Re-ran the audited suites successfully in this workspace:
  - `tests/connection/test_kernel_adapter_contract.py`: `6 passed in 0.17s`
  - `tests/connection/test_kernel_adapter_restore.py`: `6 passed in 0.19s`
  - `tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py`: `19 passed in 0.22s`

---

## Validation Sign-Off

- [x] All tasks have automated verification commands or covered live checks
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency is documented
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** audited 2026-03-30
