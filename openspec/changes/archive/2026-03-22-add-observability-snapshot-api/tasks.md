## 1. Freeze the observability snapshot contract with red tests first

- [x] 1.1 Extend `tests/connection/test_network_api.py` with red tests that freeze a new public `ConnectionNetwork` observability snapshot shape distinct from `save_runtime_snapshot()`, including exact top-level sections for `schema`, `graph_revision`, `runtime`, `queue`, and `observables`.
- [x] 1.2 Extend `tests/cli/test_backend_session.py` with red tests that freeze a thin `PlantBackendSession` forwarding method for the observability snapshot and assert it stays additive to the existing topology/checkpoint facade rather than replacing those APIs.
- [x] 1.3 Add or extend integration coverage in `tests/integration/test_dynamic_process_network_workflow.py` to assert published subsystem measurements and plant-calculation outputs appear in the substrate snapshot after a live workflow step.
- [x] 1.4 Verify the red boundary with:
  - `uv run pytest tests/connection/test_network_api.py -k "observability or snapshot"`
  - `uv run pytest tests/cli/test_backend_session.py -k "topology or checkpoint or observability"`
  - `uv run pytest tests/integration/test_dynamic_process_network_workflow.py`
  - Expected evidence: the new observability tests fail before the implementation exists.
  - Evidence captured on 2026-03-22 in the worktree:
    - network matrix: `13 failed, 7 deselected`, all failing with `AttributeError: 'ConnectionNetwork' object has no attribute 'get_observability_snapshot'`
    - session matrix: `10 failed, 4 passed, 58 deselected`, all new failures due to missing `PlantBackendSession.get_observability_snapshot`
    - integration matrix: `5 failed, 1 passed`, all new failures due to missing `ConnectionNetwork.get_observability_snapshot`

## 2. Implement the substrate-owned observability snapshot API

- [x] 2.1 Add the public observability snapshot owner method to `src/modular_simulation/connection/topology/network.py`, keeping the contract separate from persistence snapshots and returning only serializable, policy-free data.
- [x] 2.2 Add the minimal snapshot assembly support needed under `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py` and/or `src/modular_simulation/connection/runtime/runtime.py` so network-owned snapshot generation can read runtime state, normalized published measurements, and plant-calculation outputs without leaking live mutable structures.
- [x] 2.3 Add the thin forwarding facade to `src/modular_simulation/cli/backend_session.py` so callers can request the observability snapshot through `PlantBackendSession` without moving gameplay or economics policy into the facade.
- [x] 2.4 Keep the first slice limited to substrate-owned runtime and observability state; do not add pricing, tutorial progression, feed/product business semantics, or installed-asset provenance fields in this pack.

## 3. Verify the owner boundary and artifact alignment

- [x] 3.1 Run the targeted verification matrix:
  - `uv run pytest tests/connection/test_network_api.py -k "observability or snapshot"`
  - `uv run pytest tests/cli/test_backend_session.py -k "topology or checkpoint or observability"`
  - `uv run pytest tests/integration/test_dynamic_process_network_workflow.py`
  - Expected evidence: the new substrate snapshot is stable, serializable, and forwarded by `PlantBackendSession`.
-   - Evidence captured on 2026-03-22 in the worktree after the implementation and review fixes:
    - `uv run pytest tests/connection/test_network_api.py -k "observability or snapshot"` → `13 passed, 7 deselected`
    - `uv run pytest tests/cli/test_backend_session.py -k "topology or checkpoint or observability"` → `14 passed, 58 deselected`
    - `uv run pytest tests/integration/test_dynamic_process_network_workflow.py` → `7 passed`
    - supplemental contract check: `uv run pytest tests/connection/test_connected_plant_orchestrator.py -k "numeric or publication_adapter_and_collision_policy or publication_adapter_and_namespaced_lookup"` → `3 passed, 5 deselected`
    - independent code review: `hybrid-code-reviewer` returned `APPROVED` after confirming real normalized published measurements, plant-calculation outputs, copy-safety, numeric output validation, and exact top-level snapshot keys.
- [x] 3.2 Update this change’s OpenSpec task checkboxes with the verification evidence once the code passes.
- [x] 3.3 Sync the settled capability into `openspec/specs/` and keep the `sandbox-session-and-heuristic-economics` boundary text aligned with the new substrate-owned observability surface.
