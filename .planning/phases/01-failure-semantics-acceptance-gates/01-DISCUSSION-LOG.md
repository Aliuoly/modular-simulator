# Phase 1: Failure Semantics & Acceptance Gates - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `01-CONTEXT.md` — this log preserves the analyzed assumptions and confirmation outcome.

**Date:** 2026-03-29
**Phase:** 01-failure-semantics-acceptance-gates
**Mode:** assumptions
**Areas analyzed:** Acceptance Boundary, Structural Rejection Timing, Replay and Failure Classification Surface, Physical Acceptance Guards, Rejection Reason Format

## Assumptions Presented

### Acceptance Boundary
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Phase 1 should define the accepted/rejected state boundary at the whole connected-plant macro-step, not only inside `MacroCoupler`. | Likely | `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`, `src/modular_simulation/connection/runtime/runtime.py`, `src/modular_simulation/connection/runtime/connection_layer.py`, `.planning/codebase/ARCHITECTURE.md` |

### Structural Rejection Timing
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Under-/over-specified and structurally inconsistent flowsheet states should be rejected through compile/barrier processing before runtime stepping. | Confident | `src/modular_simulation/connection/topology/network.py`, `src/modular_simulation/connection/runtime/reconfiguration_barrier_processor.py`, `src/modular_simulation/connection/hydraulics/hydraulic_solver.py`, `src/modular_simulation/cli/backend_session.py` |

### Replay and Failure Classification Surface
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Phase 1 replay and failure classification should use the backend/runtime checkpoint seam and macro-step bookkeeping rather than gameplay-side state. | Likely | `src/modular_simulation/cli/backend_session.py`, `src/modular_simulation/connection/runtime/runtime_persistence.py`, `src/modular_simulation/connection/runtime/connection_layer.py` |

### Physical Acceptance Guards
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Phase 1 needs a new explicit plant-level physical acceptance layer because current guards are partial and some non-physical states are masked rather than rejected. | Likely | `src/modular_simulation/connection/runtime/transport_runtime.py`, `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`, `src/modular_simulation/unit_processes/thermal/heat_exchanger.py`, `src/modular_simulation/thermodynamics/algebraic_process_model.py` |

### Rejection Reason Format
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Explicit rejection reasons should extend the existing structured diagnostic-payload pattern into runtime-step failures instead of relying on generic `RuntimeError` messages. | Likely | `src/modular_simulation/connection/domain/error_catalog.py`, `src/modular_simulation/connection/runtime/reconfiguration_barrier_processor.py`, `src/modular_simulation/cli/backend_session.py`, `src/modular_simulation/connection/runtime/connection_layer.py`, `.planning/codebase/CONCERNS.md` |

## Corrections Made

No corrections — all assumptions confirmed.

## External Research

- Transactional/state-publication patterns for mixed unit-step + plant-coupling simulators, to compare full snapshot rollback versus staged candidate state or similar low-latency acceptance mechanisms.
