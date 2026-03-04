# Real Components Three-Tank Staged Connected Demo

## TL;DR
> **Summary**: Replace hand-coded control math in the staged three-tank example with real component-installed PID controllers, while preserving hydrostatic coupling and network valve actuation through queued mutations.
> **Deliverables**:
> - New demo module `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py`
> - Updated plotting integration in `examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py`
> - Executable acceptance evidence for lint + simulation + plotting + control-behavior assertions
> **Effort**: Medium
> **Parallel**: YES - 2 waves
> **Critical Path**: Task 1 -> Task 5 -> Task 7 -> Task 9

## Context
### Original Request
Build a real-components three-tank staged connected demo where each tank is a `System` with installed sensors/calculations/control elements, use PID-based standard controllers for level/composition/jacket loops, add an actuator bridge from controller MV to network valve mutations, preserve hydrostatic coupling and valve constraints, route SP step changes through controller SP trajectories, update plotting to consume component/controller history and bridge signals, and pass explicit acceptance commands.

### Interview Summary
- Requirements are fully specified with explicit controller targets, bridge behavior, physics retention rules, and acceptance commands.
- Scope is bounded to the new demo plus plotting update; no framework/runtime redesign is requested.
- Verification strategy is tests-after with executable command checks (no TDD requirement was requested).

### Metis Review (gaps addressed)
- Locked guardrails to avoid scope creep into core framework/runtime internals.
- Fixed ambiguity by standardizing MV hosting as dedicated command tags mapped explicitly to line IDs.
- Fixed ordering risk by requiring one canonical macro-step sequence and validating queue request count deterministically.
- Added acceptance assertions for SP step behavior, valve bounds, hydrostatic-coupled response variation, and generated plot artifact.

## Work Objectives
### Core Objective
Deliver a component-first control demo where all loop logic is executed by installed `ControlElement`/`PIDController` instances and valve actuation is performed through `ConnectionNetwork.queue_reconfiguration`, preserving existing staged physics and external usability.

### Deliverables
- `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py` with runnable API `run_three_tank_staged_connected_components(...)`.
- Updated plotting runner in `examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py` that plots PV/SP/MV from component/controller/bridge-derived histories.
- Deterministic history and summary payload fields covering SP, PV, MV, bridge queue metadata, and final valve openings.

### Definition of Done (verifiable conditions with commands)
- `uv run python -m ruff check examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py`
- `uv run python examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py`
- `uv run python examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py --step-time-s 7200 --step-target-b3 5.05`
- `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=7200.0, dt_s=10.0, final_product_target_b_mol_per_l=4.80, step_change_time_s=3600.0, step_target_b_mol_per_l=5.05); assert r['queued_valve_request_count']==int(7200.0/10.0); assert len(r['history'])>0; assert abs(r['history'][0]['target_b3_sp']-4.80)<1e-9; assert abs(r['history'][-1]['target_b3_sp']-5.05)<1e-9; assert all(0.05<=v<=1.0 for v in r['final_valve_openings'].values()); print('ok')"`
- `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=7200.0, dt_s=10.0); h=r['history']; o12=[x['open_1_to_2'] for x in h]; o23=[x['open_2_to_3'] for x in h]; assert (max(o12)-min(o12))>1e-4; assert (max(o23)-min(o23))>1e-4; print('ok')"`
- `uv run python examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py --duration-s 7200 --dt-s 10 --target-b3 4.80 --step-time-s 3600 --step-target-b3 5.05 --output /tmp/three_tank_staged_components_step.png && uv run python -c "from pathlib import Path; p=Path('/tmp/three_tank_staged_components_step.png'); assert p.exists() and p.stat().st_size>0; print('ok')"`

### Must Have
- All control loops implemented as installed component control elements; no manual per-loop error equations for MV updates.
- Dedicated MV command tags for network valves with explicit deterministic mapping table to line IDs.
- Bridge mutation path uses `queue_reconfiguration` with `set_valve_open_fraction` each macro step and valve clamping in `[0.05, 1.0]`.
- Hydrostatic coupling retained exactly as `h = V/A` and `p = p_atm + rho g h` for interstage pressure driving.
- Tank-3 composition SP step driven through controller SP trajectory APIs (or equivalent installed controller trajectory mutation), not manual branch logic.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No edits under `src/modular_simulation/**` unless a blocker is proven and documented.
- No bypass of `ConnectionNetwork.queue_reconfiguration` by mutating compiled hydraulic internals directly.
- No new generic bridge framework abstraction; keep bridge local to this example module.
- No replacement of existing topology line IDs, feed/sink boundaries, or hydrostatic helper semantics.
- No vague plotting placeholders; plotted PV/SP/MV series must be backed by concrete history keys.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after using `uv` commands + Ruff + executable assertion snippets (no manual QA).
- QA policy: every implementation task includes happy-path and failure/edge-case scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. Shared dependencies extracted into Wave 1.

Wave 1: API contract and architecture guardrails, component subsystem factories, controller configuration/SP trajectories, actuator bridge design, simulation sequencing contract.

Wave 2: end-to-end runner integration, plotting migration to component/controller histories, acceptance execution and evidence capture.

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 2, 3, 4, 5.
- Tasks 2, 3, 4, 5 block Task 6.
- Task 6 blocks Task 7 and Task 8.
- Tasks 7 and 8 block Task 9.
- Task 9 precedes Final Verification Wave.

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 5 tasks -> `deep`, `quick`, `unspecified-high`
- Wave 2 -> 3 tasks -> `unspecified-high`, `quick`
- Final Verification Wave -> 4 tasks -> `oracle`, `unspecified-high`, `unspecified-high`, `deep`

## TODOs
> Implementation + Test = ONE task. Every task includes agent-executed QA scenarios.

- [x] 1. Define component-demo contract and deterministic tag/line mapping

  **What to do**: Create the top-level structure in `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py` with canonical constants, line IDs, runner signature `run_three_tank_staged_connected_components(...)`, and explicit mapping table from controller MV tags to network line IDs (`mv_open_1_to_2`->`line_1_to_2`, `mv_open_2_to_3`->`line_2_to_3`, `mv_open_product`->`line_product`, `mv_open_feed_2`->`line_feed_2`, `mv_open_feed_3`->`line_feed_3`).
  **Must NOT do**: Do not edit `src/modular_simulation/**`, do not infer mapping from fuzzy naming, do not rename existing line IDs.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: locks API and naming decisions that all downstream tasks depend on.
  - Skills: `[]` - No external skill pack required; use existing example conventions.
  - Omitted: `[playwright, git-master]` - Not needed for non-UI planning-constrained code edits.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [2, 3, 4, 5] | Blocked By: []

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py:199` - Batch valve mutation envelope format and line ID usage.
  - Pattern: `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py:268` - Existing hand-loop section being replaced.
  - API/Type: `src/modular_simulation/connection/network.py` - `queue_reconfiguration` request structure.
  - API/Type: `src/modular_simulation/connection/runtime.py:253` - Queue/barrier semantics per macro-step.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Module defines `run_three_tank_staged_connected_components` and imports cleanly via `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components; print('ok')"`.
  - [ ] Mapping table includes all five controlled valves and only known line IDs.
  - [ ] No edits occur under `src/modular_simulation/**`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path contract load
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; print(callable(run))"`.
    Expected: Command prints `True` and exits 0.
    Evidence: .sisyphus/evidence/task-1-contract-load.txt

  Scenario: Failure on incomplete mapping
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import VALVE_MV_TO_LINE; required={'mv_open_1_to_2','mv_open_2_to_3','mv_open_product','mv_open_feed_2','mv_open_feed_3'}; assert required.issubset(set(VALVE_MV_TO_LINE)), 'missing mapping keys'; print('ok')"`.
    Expected: Passes when mapping is complete; fails with explicit missing-key assertion message if not.
    Evidence: .sisyphus/evidence/task-1-mapping-check.txt
  ```

  **Commit**: YES | Message: `feat(examples): scaffold componentized three-tank runner contract and valve mapping` | Files: [`examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py`]

- [x] 2. Build tank subsystem factories with installed PID control elements

  **What to do**: Implement per-tank `System` construction that installs sensors and control elements using the same framework style as `component_definition.py`. Configure loops: Tank-1 level->`mv_open_1_to_2`; Tank-2 level->`mv_open_2_to_3`; Tank-3 level->`mv_open_product`; Tank-2 composition trim->`mv_open_feed_2`; Tank-3 composition trim->`mv_open_feed_3`; keep jacket controllers on `T_J_in` as regular installed control elements.
  **Must NOT do**: Do not implement manual error equations for these loops; do not leave any target loop outside `control_elements`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: multi-controller configuration with strict pattern fidelity.
  - Skills: `[]` - Existing repo examples are sufficient.
  - Omitted: `[playwright]` - No browser work.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [6] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `examples/simple_irreversible_energy_balance_system/component_definition.py:33` - Canonical control element + PID wiring pattern.
  - API/Type: `src/modular_simulation/framework/system.py:168` - component install order and update lifecycle.
  - API/Type: `src/modular_simulation/components/control_system/controllers/PID_controller.py` - PID behavior and anti-windup via MV range.
  - API/Type: `src/modular_simulation/components/control_system/control_element.py:268` - controller SP/MV points published to history.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Each tank system has installed sensors and `control_elements` for required loops.
  - [ ] All five valve-driving loops are `PIDController`-backed `ControlElement`s with MV ranges constrained to `[0.05, 1.0]`.
  - [ ] Jacket loops remain installed component controllers on `T_J_in`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path control element inventory
    Tool: Bash
    Steps: Run a short script that builds systems and asserts control element MV tags include `mv_open_1_to_2`, `mv_open_2_to_3`, `mv_open_product`, `mv_open_feed_2`, `mv_open_feed_3`, and per-tank `T_J_in`.
    Expected: All required MV tags found; each mapped element uses `PIDController`.
    Evidence: .sisyphus/evidence/task-2-control-inventory.txt

  Scenario: Failure when manual-loop fallback is present
    Tool: Bash
    Steps: Run `uv run python -c "from pathlib import Path; s=Path('examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py').read_text(); banned=['err_v1','err_v2','err_v3','comp_err_2','comp_err_3']; assert all(x not in s for x in banned), 'manual loop symbol still present'; print('ok')"`.
    Expected: Command passes when manual loop equations are removed; fails with explicit assertion otherwise.
    Evidence: .sisyphus/evidence/task-2-no-hand-loop.txt
  ```

  **Commit**: YES | Message: `feat(examples): install per-tank PID control elements for staged network actuation` | Files: [`examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py`]

- [x] 3. Implement controller trajectory strategy and SP step routing

  **What to do**: Route setpoints through controller trajectories: fixed level SPs for all tank level loops, fixed composition SP for Tank-2 trim, and step-change SP for Tank-3 composition trim through controller APIs (`extend_controller_sp_trajectory` or equivalent direct trajectory update on installed controller). Keep step timing/value arguments compatible with current CLI usage.
  **Must NOT do**: Do not perform SP switching via direct manual error equations inside the simulation loop.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: targeted SP trajectory wiring and deterministic step behavior.
  - Skills: `[]` - Built-in APIs are enough.
  - Omitted: `[playwright]` - No UI verification.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [6] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - API/Type: `src/modular_simulation/framework/system.py:374` - `extend_controller_sp_trajectory` support.
  - Pattern: `examples/simple_irreversible_energy_balance_system/component_definition.py` - trajectory-centric controller setup.
  - Pattern: `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py` - step-change intent and arguments.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `step_change_time_s` and `step_target_b_mol_per_l` drive Tank-3 composition controller SP updates.
  - [ ] History contains pre-step and post-step SP values for Tank-3 composition (`target_b3_sp`) with expected transition.
  - [ ] No manual composition-error branch drives feed valve MV directly.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path SP step transition
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=7200.0, dt_s=10.0, final_product_target_b_mol_per_l=4.80, step_change_time_s=3600.0, step_target_b_mol_per_l=5.05); h=r['history']; assert abs(h[0]['target_b3_sp']-4.80)<1e-9; assert abs(h[-1]['target_b3_sp']-5.05)<1e-9; print('ok')"`.
    Expected: Command prints `ok` with SP transition reflected in history.
    Evidence: .sisyphus/evidence/task-3-sp-step.txt

  Scenario: Failure when no SP transition is applied
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=7200.0, dt_s=10.0, final_product_target_b_mol_per_l=4.80, step_change_time_s=3600.0, step_target_b_mol_per_l=5.05); vals={x['target_b3_sp'] for x in r['history']}; assert len(vals)>1, 'SP did not step'; print('ok')"`.
    Expected: Passes only when SP trajectory actually changes over time.
    Evidence: .sisyphus/evidence/task-3-sp-step-guard.txt
  ```

  **Commit**: YES | Message: `feat(examples): route composition and level objectives through controller trajectories` | Files: [`examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py`]

- [x] 4. Build actuator bridge from controller MV outputs to queued valve mutations

  **What to do**: Implement a bridge function executed once per macro step that reads the five valve-command MV values from installed control elements, clamps each value to `[0.05, 1.0]`, then submits one `batch_update` request with `set_valve_open_fraction` mutations through `ConnectionNetwork.queue_reconfiguration`. Persist per-step bridge output signals and request IDs for history/diagnostics.
  **Must NOT do**: Do not call internal runtime mutators directly; do not update hydraulic graph internals outside queued mutation path.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: bridge correctness directly controls network actuation and acceptance checks.
  - Skills: `[]` - Existing API usage is straightforward.
  - Omitted: `[playwright, git-master]` - Not needed for this implementation scope.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [6, 7] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py:199` - canonical queued batch mutation format.
  - API/Type: `src/modular_simulation/connection/network.py` - `queue_reconfiguration` input contract.
  - API/Type: `src/modular_simulation/connection/runtime.py:733` - `set_valve_open_fraction` mutation handling path.
  - API/Type: `src/modular_simulation/connection/runtime.py:931` - staged valve command update behavior.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Exactly one bridge queue request is issued per macro step.
  - [ ] Every bridge mutation uses known `line_id` and clamped `open_fraction` in `[0.05, 1.0]`.
  - [ ] Returned summary includes `queued_valve_request_count` and `last_valve_request_id`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path bridge queueing
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=600.0, dt_s=10.0); assert r['queued_valve_request_count']==60; assert isinstance(r['last_valve_request_id'], str) and r['last_valve_request_id']; print('ok')"`.
    Expected: Command prints `ok`; request count equals macro-step count.
    Evidence: .sisyphus/evidence/task-4-bridge-queue.txt

  Scenario: Failure on out-of-range bridge outputs
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=1200.0, dt_s=10.0); vals=[*r['final_valve_openings'].values()]; assert all(0.05<=v<=1.0 for v in vals), 'unclamped valve output'; print('ok')"`.
    Expected: Passes only when bridge enforces physical valve limits.
    Evidence: .sisyphus/evidence/task-4-valve-clamp.txt
  ```

  **Commit**: YES | Message: `feat(examples): add controller-to-network valve bridge using queued mutations` | Files: [`examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py`]

- [x] 5. Preserve hydrostatic pressure coupling and physical valve constraints

  **What to do**: Carry over hydrostatic helper formulas and usage (`h = V/A`, `p = p_atm + rho g h`) to compute interstage driving pressures and atmospheric receiving-side assumptions, retain bounded/nonnegative flow logic, and keep outlet/makeup valve constraints consistent with prior staged example behavior.
  **Must NOT do**: Do not flatten pressure logic into constant flows; do not remove saturation and physical lower bounds.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: direct portability task with strict formula fidelity.
  - Skills: `[]` - no extra skill dependency.
  - Omitted: `[playwright]` - no UI activity.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [6, 7] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py` - hydrostatic helpers and flow helpers.
  - Pattern: `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py:268` - current pressure-driven loop context.
  - API/Type: `examples/simple_irreversible_energy_balance_system/process_definition.py` - process input tags and units.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Hydrostatic pressure function and bounded valve flow helper are present and used in main loop.
  - [ ] Interstage flow and product/feed constraints remain nonnegative and physically bounded.
  - [ ] Simulation exhibits non-flat valve behavior over a 2-hour run (hydrostatic coupling active).

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path hydrostatic response variation
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=7200.0, dt_s=10.0); h=r['history']; o12=[x['open_1_to_2'] for x in h]; o23=[x['open_2_to_3'] for x in h]; assert (max(o12)-min(o12))>1e-4; assert (max(o23)-min(o23))>1e-4; print('ok')"`.
    Expected: Prints `ok`; interstage valve behavior is responsive, not flatlined.
    Evidence: .sisyphus/evidence/task-5-hydrostatic-variation.txt

  Scenario: Failure on negative or unbounded flow signals
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=1200.0, dt_s=10.0); h=r['history']; keys=['open_1_to_2','open_2_to_3','open_product','open_feed_2','open_feed_3']; assert all(all(0.05<=x[k]<=1.0 for x in h) for k in keys), 'valve bound violation'; print('ok')"`.
    Expected: Passes only with maintained physical limits.
    Evidence: .sisyphus/evidence/task-5-physical-bounds.txt
  ```

  **Commit**: YES | Message: `refactor(examples): retain hydrostatic and physical valve constraints in componentized runner` | Files: [`examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py`]

- [x] 6. Implement deterministic macro-step orchestration and history schema

  **What to do**: Implement one canonical macro-step order and keep it stable: (1) apply SP schedule updates, (2) compute hydrostatic pressures + flows from current states/openings, (3) write process model manipulated inputs, (4) step each tank `System` for `dt`, (5) read controller MV outputs and queue bridge valve mutations, (6) call `network.step(macro_step_time_s=dt)`, (7) sample history payload at fixed cadence including time/SP/PV/MV/bridge fields.
  **Must NOT do**: Do not reorder loop operations ad hoc across iterations; do not omit per-step queueing.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: sequencing correctness impacts control latency and determinism.
  - Skills: `[]` - Local pattern knowledge is sufficient.
  - Omitted: `[playwright]` - no browser dependency.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [7, 8] | Blocked By: [2, 3, 4, 5]

  **References** (executor has NO interview context - be exhaustive):
  - API/Type: `src/modular_simulation/framework/system.py:281` - per-step update sequence around component updates and process stepping.
  - API/Type: `src/modular_simulation/framework/system.py:168` - component update order (sensor -> calculation -> control element).
  - API/Type: `src/modular_simulation/connection/runtime.py:253` - barrier queue processing semantics.
  - Pattern: `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py` - sampled history schema and summary fields.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `queued_valve_request_count` equals `int(duration_s / dt_s)` for deterministic runs.
  - [ ] History entries include required keys: `time_h`, `target_b3_sp`, tank PVs, and five valve openings.
  - [ ] Runner returns deterministic summary structure with non-empty history.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path deterministic request count and schema
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=7200.0, dt_s=10.0); assert r['queued_valve_request_count']==720; req=['time_h','target_b3_sp','v1_l','v2_l','v3_l','b1_mol_per_l','b2_mol_per_l','b3_mol_per_l','open_1_to_2','open_2_to_3','open_product','open_feed_2','open_feed_3']; assert all(k in r['history'][-1] for k in req); print('ok')"`.
    Expected: Prints `ok`; schema and count are deterministic.
    Evidence: .sisyphus/evidence/task-6-schema-determinism.txt

  Scenario: Failure when queueing cadence drifts
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=601.0, dt_s=10.0); expected=int(601.0/10.0); assert r['queued_valve_request_count']==expected, f\"count mismatch {r['queued_valve_request_count']} != {expected}\"; print('ok')"`.
    Expected: Assertion fails if queueing is skipped or doubled.
    Evidence: .sisyphus/evidence/task-6-queue-cadence.txt
  ```

  **Commit**: YES | Message: `feat(examples): enforce deterministic staged simulation loop and history contract` | Files: [`examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py`]

- [x] 7. Finalize runner output payload from component/controller/bridge histories

  **What to do**: Finalize return payload for `run_three_tank_staged_connected_components` to include: `history`, `queued_valve_request_count`, `last_valve_request_id`, `final_valve_openings`, and final tank metrics. Ensure sampled `history` rows include controller-driven SP/PV/MV values and bridge valve signals required by plotting script.
  **Must NOT do**: Do not rely on synthetic-only fields that are detached from component/controller state; no brittle implicit key names.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: API contract stability for downstream plotting and checks.
  - Skills: `[]` - Repo-local patterns sufficient.
  - Omitted: `[playwright]` - non-UI task.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [9] | Blocked By: [6]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py` - summary + history payload baseline.
  - API/Type: `src/modular_simulation/framework/system.py:335` - history extension points.
  - API/Type: `src/modular_simulation/components/control_system/control_element.py:268` - controller SP/MV values available in history.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Runner output includes all required top-level keys and non-empty `history`.
  - [ ] `history` rows include values used by plotting (`target_b3_sp`, PVs, valve openings).
  - [ ] Final valve openings in summary match bounded bridge outputs.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path payload contract
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=3600.0, dt_s=10.0); required={'history','queued_valve_request_count','last_valve_request_id','final_valve_openings','final_b3_mol_per_l','final_v3_l'}; assert required.issubset(r.keys()); assert len(r['history'])>0; print('ok')"`.
    Expected: Prints `ok`; payload contains required keys.
    Evidence: .sisyphus/evidence/task-7-payload-contract.txt

  Scenario: Failure on missing plotting keys
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=3600.0, dt_s=10.0); required={'time_h','target_b3_sp','v1_l','v2_l','v3_l','b3_mol_per_l','open_1_to_2','open_2_to_3','open_product','open_feed_2','open_feed_3'}; assert required.issubset(r['history'][-1].keys()), 'history missing plotting fields'; print('ok')"`.
    Expected: Passes only when plotting-critical fields exist.
    Evidence: .sisyphus/evidence/task-7-history-keys.txt
  ```

  **Commit**: YES | Message: `feat(examples): stabilize componentized runner summary and history payload` | Files: [`examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py`]

- [x] 8. Update plotting script to consume componentized runner and controller-driven signals

  **What to do**: Update `examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py` to import and run `run_three_tank_staged_connected_components`, preserve existing CLI flags, and plot PV/SP/MV curves using fields sourced from component/controller/bridge history. Keep step-change vertical marker behavior and output artifact behavior.
  **Must NOT do**: Do not introduce a separate plotting script; do not remove existing CLI compatibility.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: targeted import + extraction + plotting updates.
  - Skills: `[]` - Matplotlib usage pattern already exists in file.
  - Omitted: `[frontend-ui-ux, playwright]` - static plotting script, no browser loop.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [9] | Blocked By: [6]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py` - existing subplot and CLI structure to preserve.
  - Pattern: `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py` - current output fields expected by plot script.
  - API/Type: `src/modular_simulation/plotting/time_series.py` - reusable plotting idioms if needed.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Plot script still accepts current flags including `--step-time-s` and `--step-target-b3`.
  - [ ] Plot script runs end-to-end and writes non-empty output PNG.
  - [ ] Data extraction validates presence of controller-driven SP/MV fields and fails fast with clear message if absent.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path plotting artifact generation
    Tool: Bash
    Steps: Run `uv run python examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py --duration-s 7200 --dt-s 10 --target-b3 4.80 --step-time-s 3600 --step-target-b3 5.05 --output /tmp/three_tank_staged_components_step.png` then `uv run python -c "from pathlib import Path; p=Path('/tmp/three_tank_staged_components_step.png'); assert p.exists() and p.stat().st_size>0; print('ok')"`.
    Expected: Plot file exists, non-empty, command exits 0.
    Evidence: .sisyphus/evidence/task-8-plot-artifact.txt

  Scenario: Failure on missing expected history field
    Tool: Bash
    Steps: Run `uv run python -c "from examples.simple_irreversible_energy_balance_system.three_tank_staged_connected_components import run_three_tank_staged_connected_components as run; r=run(duration_s=600.0, dt_s=10.0); assert 'target_b3_sp' in r['history'][-1], 'missing target_b3_sp for plot'; print('ok')"`.
    Expected: Assertion guarantees plot dependency contract.
    Evidence: .sisyphus/evidence/task-8-plot-contract.txt
  ```

  **Commit**: YES | Message: `feat(plotting): switch staged connected plot to componentized runner history` | Files: [`examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py`]

- [x] 9. Execute full acceptance command wave and archive evidence

  **What to do**: Run the complete acceptance suite (user-provided three commands plus deterministic assertion commands) after implementation, capture outputs in evidence files, and stop only when all checks pass. If any check fails, fix implementation and rerun until green.
  **Must NOT do**: Do not skip failed checks; do not mark complete without command output artifacts.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: integrates lint/simulation/plotting assertions as release gate.
  - Skills: `[]` - Standard CLI execution.
  - Omitted: `[playwright]` - no UI automation required.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [Final Verification Wave] | Blocked By: [7, 8]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `.github/workflows/ci.yml` - repo quality gate conventions.
  - Config: `pyproject.toml` - Ruff/pytest/mypy toolchain settings.
  - Command source: user acceptance list and plan Definition of Done section.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run python -m ruff check examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py` exits 0.
  - [ ] `uv run python examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py` exits 0.
  - [ ] `uv run python examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py --step-time-s 7200 --step-target-b3 5.05` exits 0.
  - [ ] Deterministic assertions from Definition of Done all print `ok`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path full acceptance suite
    Tool: Bash
    Steps: Execute all Definition-of-Done commands in sequence and tee outputs into `.sisyphus/evidence/task-9-*.txt`.
    Expected: Every command exits 0 and assertion snippets print `ok`.
    Evidence: .sisyphus/evidence/task-9-acceptance-wave.txt

  Scenario: Failure gate behavior
    Tool: Bash
    Steps: If any command exits non-zero, record stderr/stdout, classify failure (lint/runtime/contract), apply fix, and rerun full suite from the first command.
    Expected: Task remains open until complete rerun is fully green.
    Evidence: .sisyphus/evidence/task-9-failure-recovery.txt
  ```

  **Commit**: YES | Message: `chore(examples): validate componentized staged demo with deterministic acceptance suite` | Files: [`examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_components.py`, `examples/simple_irreversible_energy_balance_system/plot_three_tank_staged_connected_control.py`]

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit - oracle
- [x] F2. Code Quality Review - unspecified-high
- [x] F3. Real Manual QA - unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check - deep

## Commit Strategy
- Commit 1: `feat(examples): add componentized three-tank staged connected demo with PID-driven bridge actuation`
- Commit 2: `feat(plotting): source three-tank PV/SP/MV traces from component controller and bridge histories`
- Commit 3: `chore(examples): add deterministic acceptance checks for staged connected components demo`
- No amend; no force push; keep commits atomic by deliverable boundary.

## Success Criteria
- New demo runs and produces stable, bounded valve actuation with queue request count equal to macro steps.
- SP step on Tank-3 composition is visible in controller-driven trajectories and downstream PV behavior.
- Plot artifact is generated from component/controller/bridge-backed history signals and includes PV/SP/MV curves.
- All lint and executable acceptance checks pass with no manual intervention.
