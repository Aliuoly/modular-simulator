# Decisions
- 2026-02-21: Documented descriptor-based wiring approach for subsystem installers and the to_binding() bridge to ProcessBinding.
- 2026-02-21: Kept queue semantics in runtime orchestrator and codified policy in runtime.py + contract tests rather than changing ConnectionNetwork request ingestion.
- 2026-02-21: Chose canonical JSON fingerprint of mutation payloads for deterministic idempotency conflict detection.

- 2026-02-21: Enforced scope hygiene by restoring only explicitly flagged out-of-scope tracked files, leaving Task 1 contract files and current-plan notes as the sole intended tracked deltas.

- 2026-02-21: Implemented namespacing at PointRegistry add-time via optional `subsystem_namespace`/`published_tag` parameters to keep existing non-namespaced registration call sites unchanged and preserve Task 1 hot-install/runtime behavior.
- 2026-02-21: Chosen collision invariant is published-tag ownership uniqueness across subsystems (not last-writer-wins), while same-subsystem duplicates remain guarded by existing registry key uniqueness checks.

- 2026-02-21: For gate cleanup, reverted `uv.lock` via source-controlled restore only, leaving intended Task 2/3/5 code and tests untouched.
- 2026-02-21: Kept installer effects strictly subsystem-local by delegating wiring through the local System.add_component and local point registry context only.
- 2026-02-21: Deterministic invalid-tag behavior is prevalidated at subsystem API boundaries with explicit SensorConfigurationError/ControllerConfigurationError messages before install attempts.
- 2026-02-21: Introduced `ConnectedPlantPhaseHooks` with one hook per contract phase to keep the Task 4 orchestrator explicit and thin while deferring plant-calculation business logic to later tasks.
- 2026-02-21: Deferred same-connected-macro-step runtime queue application by partitioning queue entries into step-entry snapshot vs newly queued entries, then restoring deferred entries ahead of post-runtime queued work for next-barrier determinism.
- 2026-02-21: Scope cleanup fixed by restoring only `uv.lock` to pre-task content and leaving Task 4 + existing Task 1/2/3/5 deltas intact.

- 2026-02-21: Plant calculation API shape is `ConnectedPlantOrchestrator.add_calculation(calculation_id, input_tags, output_tags, evaluate)` with strict output-tag collision checks against both published subsystem measurements and previously registered plant outputs.
- 2026-02-21: Dependency resolution intentionally runs during plant phase execution (not registration) so calculations can be registered out of order and still resolve deterministically before evaluation.
