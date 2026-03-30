---
phase: 02
slug: kernel-adapter-warm-starts-delay-state
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-29
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py -q` |
| **Full suite command** | `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py tests/connection/test_kernel_adapter_restore.py tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py -q` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py -q`
- **After every plan wave:** Run `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py tests/connection/test_kernel_adapter_restore.py tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | SOLV-02 | contract | `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | SOLV-02, DELY-02 | integration | `uv run python -m pytest tests/connection/test_kernel_adapter_contract.py -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | KERN-04 | integration | `uv run python -m pytest tests/connection/test_kernel_adapter_restore.py -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | KERN-04 | regression | `uv run python -m pytest tests/connection/test_kernel_adapter_restore.py -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 3 | DELY-01, DELY-02, DELY-03 | regression | `uv run python -m pytest tests/connection/test_split_kernel_delay_mapping.py tests/connection/test_runtime_persistence_contract.py -q` | ✅ / ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 3 | DELY-01, DELY-02 | docs/contract | `uv run python -m pytest tests/connection/test_split_kernel_delay_mapping.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/connection/test_kernel_adapter_contract.py` — capability-first core contract, optional solver-capability protocols, telemetry, and delay-semantics expectations
- [ ] `tests/connection/test_kernel_adapter_restore.py` — canonical restore and explicit-failure expectations
- [ ] `tests/connection/test_split_kernel_delay_mapping.py` — delay-state semantics and round-trip coverage

*Existing infrastructure covers framework setup; new phase-specific tests are still required.*

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 35s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
