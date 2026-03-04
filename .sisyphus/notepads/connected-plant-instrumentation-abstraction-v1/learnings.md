# Learnings
- 2026-02-21: Added SubsystemRuntimeDescriptor as a lightweight descriptor object binding subsystem process identity, local runtime/ports, and a publication map. Validation enforces non-empty descriptor_id/process_id and non-empty port lists with valid names.
- 2026-02-21: Created tests for the descriptor: valid descriptor wiring and rejection on missing port metadata. Descriptor can be converted to a ProcessBinding via to_binding().
- 2026-02-21: Connection runtime now exposes authoritative connected-plant phase order via CONNECTED_PLANT_PHASE_ORDER and enforces hot-install state transitions at barrier commit with deterministic FIFO queue traversal.
- 2026-02-21: Idempotency is key+payload strict: exact payload replay is skipped, but reused key with different mutation payload triggers rollback with no state change.
- 2026-02-21: Poison request at queue head blocks the entire barrier batch and preserves queued order/state until explicit maintenance action.

- 2026-02-21: QA scope-cleanup pass reverted unrelated tracked edits (.gitignore, uv.lock, two_tank example, and prior-plan notepad) while preserving Task 1 runtime contract behavior/tests.

- 2026-02-21: PointRegistry registration now supports deterministic subsystem publication keys (`<subsystem>/<published_tag>`), so plant-scoped lookups can resolve a stable namespaced key without mutating the underlying Point.tag.
- 2026-02-21: Collision policy is fail-fast at registration: the same published tag cannot be owned by different subsystems, and violation raises `MeasurableConfigurationError` with the conflicting subsystems in the message.

- 2026-02-21: QA scope hygiene fix is isolated by restoring only `uv.lock`; no dependency graph or implementation deltas were introduced.
- 2026-02-21: Added a Subsystem installer API (`add_sensor`, `add_control_element`) on the descriptor module that validates tags against a subsystem-local published process view (descriptor publication map + local process states + local non-raw registry tags).
- 2026-02-21: Subsystem phase runner (`run_sensor_phase`, `run_calculation_phase`, `run_controller_phase`, `run_process_phase`, `step`) now updates newly installed local components without direct component-level script wiring.
- 2026-02-21: Added `ConnectedPlantOrchestrator` skeleton to compose subsystem descriptors with `ConnectionRuntimeOrchestrator`; it exposes an explicit initialization path that compiles/validates process descriptor bindings before stepping.
- 2026-02-21: Connected-plant stepping enforces deferred hot-install at plant level by snapshotting queued runtime reconfigurations at step start and deferring newly queued requests to the next barrier commit point.

 - 2026-02-21: Task 6 plant calculations now execute in the plant phase from a deterministic dependency order that resolves against only subsystem descriptor `publication_map` keys plus previously resolved plant outputs.
- 2026-02-23: Updated boulder.json by appending the current session ses_372bb8011ffeqTHuPnBTRWjHQI to session_ids; ensured no duplicates and validated JSON with python3 -m json.tool.
- 2026-02-21: Unresolvable plant inputs raise an `ExceptionGroup` with per-calculation missing-input detail, making unresolved dependency failures deterministic and grouped like System calculation commissioning behavior.
- 2026-02-23: Task 7 publication adapter now resolves descriptor publication entries through subsystem lookup getters (point registry first, then process-model state) and emits deterministic namespaced keys (`<descriptor_id>/<published_tag>`) when source entries are not already namespaced.
- 2026-02-23: Plant publication snapshots can now come from `snapshot_published_measurements()` when a subsystem provides it, enabling live publication updates without descriptor-map polling rewrites and without per-tick registry cloning.
- 2026-02-23: Unit override path via `runtime_context.publication_units` is unit-safe and fail-fast; incompatible source/target units raise `MeasurableConfigurationError` with explicit published tag + source unit + target unit details.
- 2026-02-23: `connection.process_interface` now enforces break-and-replace guardrails via module-level legacy-symbol rejection; `ProcessInterface`, `ProcessModelAdapter`, and `ProcessBalanceTerm` access fails deterministically with actionable migration guidance to `ConnectionNetwork.compile().process_bindings[...]` + `ProcessBinding` methods.
- 2026-02-23: Added migration-guardrail assertions in `test_process_interface_adapter.py` to verify guidance content (what failed, why it was removed, and exact replacement API path), preventing ambiguous compatibility fallback behavior.

- 2026-02-23: Task 8 sequencing fix defers mutations queued inside the connected-plant  phase hook by splitting queue snapshots after the hook and applying only pre-step snapshot requests at the current barrier.
- 2026-02-23: Added a regression in tests/connection/test_connection_runtime_sequence.py proving coupling-hook enqueues are invisible in the same macro-step and commit deterministically at the next barrier.
- 2026-02-23: Clarification: the deferred-queue fix specifically covers enqueue operations triggered during the connection_runtime_coupling phase hook.
- Task-11 (Unit Tests for Scoped Installers and Collision Rules): Added focused tests to cover plant-scoped calculation registration and collision behavior. Positive cross-subsystem input resolution verified; collision paths validated; awaiting finalization of 11.3 negative-path coverage and full pytest confirmation.
- Task-11 (Unit Tests for Scoped Installers and Collision Rules): Added focused tests to cover plant-scoped calculation registration and collision behavior. Positive cross-subsystem input resolution verified; collision paths validated;  additional tests for namespaced tag resolution and collision semantics added under 11.3.
- 2026-02-23: Task 12 integration coverage now locks connected-plant sequencing metadata by asserting per-phase hook order, macro-step index/time progression, and runtime bookkeeping sequence invariants across deferred reconfiguration barriers.
- 2026-02-23: Task 12 parity coverage now enforces two-tank benchmark thresholds and monotonic/lag checks for both legacy and subsystem-abstraction paths, plus deterministic equality of scalar parity metadata between paths.
- 2026-02-23: Task 13 added explicit runtime barrier failure regressions in `test_runtime_mutation_contract.py` for invalid scope-like operations (`install_subsystem_sensor` unsupported), unresolved cross-subsystem endpoint references, and strict FIFO deferral where pre-step queue items commit before during-step enqueues.
- 2026-02-23: Runtime snapshot restore currently preserves committed idempotency keys but not payload fingerprints; post-restore key reuse with different payload fails deterministically with `but committed payload is unavailable` rollback messaging.
- 2026-02-23: Task 9 migration now uses real connected-plant APIs in the two-tank example: `SubsystemRuntimeDescriptor` descriptors, protocol-compatible subsystem runtimes, `ConnectionRuntimeOrchestrator` callbacks, and `ConnectedPlantOrchestrator.step(...)` for macro-step sequencing.
- 2026-02-23: Parity with legacy benchmark behavior is preserved by updating B-inlet coupling in runtime boundary propagation from Tank A's post-process state each macro-step (matching legacy one-step-lag semantics without wrapper delegation).

- 2026-02-23: Task 14 docs now set connected-plant as the default path in readme.md and LLM_CONTEXT.md, including subsystem installers (`add_sensor`, `add_control_element`), plant calculations (`ConnectedPlantOrchestrator.add_calculation`), namespaced key rules (`<subsystem>/<published_tag>`), fail-fast collision policy, and explicit break-and-replace API mapping for removed process_interface symbols.

- Sync complete: 12 checkboxes updated to reflect verified completion for tasks 7-14 and F1-F4.
