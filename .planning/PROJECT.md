# ModularSimulator

## What This Is

ModularSimulator is a simulation-first backend for educational chemical-process gameplay and classroom tooling. It provides a grounded substrate for composing unit operations, connected-plant hydraulics, controls, and flowsheets, then exposes that substrate through backend session and gameplay-facing service layers.

## Core Value

Deliver a grounded, composable process-simulation backend that stays physically credible enough for teaching while still usable as a realtime game substrate.

## Current Milestone: v1.0 Kernel stability

**Goal:** Decide on a more stable backend simulation kernel for complex flowsheets, with physical correctness and game-usable performance as the top constraints.

**Target features:**
- Analyze where the current unit micro-step plus connection macro-step split can create stale-coupling and non-physical states
- Compare kernel directions, including the current split approach versus a flowsheet-wide coupled solve
- Produce a migration roadmap toward the chosen kernel direction

## Requirements

### Validated

- ✓ Users can assemble and run explicit flowsheets with feeds, sinks, junctions, and connected unit processes — current substrate and canonical examples
- ✓ Users can simulate instrumented unit operations with sensors, calculations, and controllers — current component and unit-process runtime
- ✓ Users can run a connected-plant orchestration layer with hydraulic compilation and macro-step coupling — current connection/runtime stack
- ✓ User-facing clients can drive the backend through `PlantBackendSession`, gameplay services, and the HTTP game API — current playable vertical slice

### Active

- [x] Analyze failure modes in the current split unit-step / connection macro-step kernel, especially stale hydraulic decisions and non-physical inventories
- [x] Compare candidate kernel architectures for complex flowsheets, including whole-flowsheet coupled stepping versus the current split runtime
- [x] Define a migration roadmap toward a more stable backend kernel that preserves game-usable simulation performance

### Out of Scope

- Batch-first gameplay — explicitly deferred beyond the current live slice and unrelated to backend kernel stability
- Stochastic equipment failure, fouling, and staffing systems — deferred beyond phase 1 and not needed for this milestone decision
- Multi-plant vertical integration — separate product expansion, not part of stabilizing the core flowsheet kernel
- Open-ended chemistry sandboxing — separate domain expansion, not required to choose the next kernel direction
- Frontend/client feature work — this milestone is focused on backend simulation-kernel decisions and roadmaping

## Context

The existing brownfield codebase already includes a flowsheet builder, connected-plant topology and hydraulics, runtime-editing APIs, gameplay/session layers, and a Godot-facing API/client slice. The current connected runtime uses per-unit process stepping followed by a connection-layer macro coupling sequence (hydraulics solve, transport update, boundary propagation), which creates a real concern that stale hydraulic decisions may lag rapidly changing unit states. The planning baseline for this repo starts here: the current milestone is focused on understanding those failure modes, comparing kernel directions, and choosing a path that remains fast enough for game-backend use.

## Constraints

- **Tech stack**: Python 3.13 simulation backend with SciPy, FastAPI, Pydantic, and existing connection/runtime modules — the milestone should work with the current substrate rather than assuming a greenfield rewrite
- **Physical correctness**: The backend kernel must avoid non-physical states such as negative inventory or stale-pressure-driven flows — this is the primary stability driver for the milestone
- **Performance**: Candidate directions must stay viable for a realtime game backend — a kernel that takes minutes of compute for seconds of game time is unacceptable
- **Compatibility**: Existing flowsheet, connection, and gameplay-facing layers are live substrate consumers — migration should account for those integration points even if internals change

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Start planning baseline at milestone v1.0 | `.planning/PROJECT.md` and milestone history were not yet initialized for this brownfield repo | — Pending |
| Prioritize kernel stability and performance over new feature expansion | The current concern is backend correctness and suitability for complex flowsheets in game use | — Pending |
| Evaluate whole-flowsheet coupled stepping as a first-class option | The user explicitly wants to test whether the current split-step architecture is the wrong direction | — Pending |
| Score benchmark candidates per workload while publishing the real split baseline | Phase 3 review showed that mixed-workload latency gates and a synthetic baseline stub produce non-credible benchmark evidence | Phase 3 reports now aggregate workload-level results and instantiate the network's configured split adapter path |
| Narrow Phase 3 workload claims to transport-history-sensitive disturbance and topology-reroute evidence | The benchmark canon now carries honest delay-sensitive and restart/reconfiguration coverage, but it does not yet wire a full closed-loop controller benchmark | Phase 3 roadmap and requirement text now match the implemented workload seeds and checkpoint reroute behavior |
| Keep `hybrid_coupled` as the default kernel direction while separating architecture direction from solver-stack migration | Phase 4 needs one evidence-backed kernel direction without forcing an immediate solver rewrite or facade break | The reusable decision gate, public wrapper, and docs now lock the default direction to `hybrid_coupled` and preserve `PlantBackendSession` / `CandidateKernelAdapter` |
| Leave SciPy only after gate misses plus solver-core dominance, with `sundials4py` before PETSc | Phase 4 research favored a lighter Python-native escalation before a higher-complexity PETSc path | The decision gate and roadmap now require gate evidence plus `solver_core_fraction >= 0.5`, recommend `sundials4py` first, and keep `petsc4py` later-only |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-30 after Phase 4 completion and verification handoff*
