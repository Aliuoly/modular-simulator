
- 2026-02-18: Chose a frozen-dataclass topology domain with validation in `TopologyGraph.__post_init__` to match existing connection module style and fail fast before any compile/runtime integration.
- 2026-02-18: Defined duplicate-edge identity by endpoint pair (`source node.port -> target node.port`) independent of `edge_id`, so semantically duplicated links are rejected even when IDs differ.
- 2026-02-18: Implemented endpoint validation at node+port granularity and differentiated unknown-node vs unknown-port messaging for assertable diagnostics.

- 2026-02-19: Introduced `HydraulicCompileLifecycle` with explicit `compile`, `compile_candidate`, and `activate` methods so candidate reconfiguration validation is pure by default and only explicit activation mutates runtime-facing state.
- 2026-02-19: Standardized compile failures as `GraphCompileError` with sorted, tuple-based `GraphCompileDiagnostic` payloads to keep assertions deterministic and stable across repeated runs.
- 2026-02-19: Kept explicit inlet setter (`set_inlet` / `bind_inlets`) and outlet getter (`get_outlet`) APIs, but upgraded outlet binding schema to structured dictionaries so role-aware normalization and composition validation happen in one deterministic path.
- 2026-02-19: Enforced outlet composition compatibility by requiring identical composition tuple length across all outlet bindings in a bind call, raising an assertable `BindingError` payload when lengths differ.

- 2026-02-19: Chose facade-level endpoint grammar `'<node>.<port>' or '<boundary_id>'` with a strict rule that processes must always be dotted, to eliminate ambiguous endpoint resolution and keep parse errors deterministic.
- 2026-02-19: Kept `step`, `save_runtime_snapshot`, and `resume_from_snapshot` as explicit guarded placeholders that fail closed until runtime orchestrator wiring lands, avoiding premature runtime coupling in Task 3.
- 2026-02-19: Made `compile()` delegate-only: assemble `TopologyGraph`, materialize `ProcessBinding` artifacts, then optionally call `HydraulicCompileLifecycle` via an injected hydraulic system builder so no solver math is embedded in the facade.

- 2026-02-19: Kept junction runtime integration adapter-only by introducing `mix_junction_runtime_states(topology, edge_states, edge_flow_rates, previous_junction_states, epsilon)` that delegates mixing/fallback to `mix_junction_state` instead of adding new mixing logic.
- 2026-02-19: Standardized deterministic runtime traversal for junction integration by sorting both junction IDs and edge IDs before building per-junction `PortCondition` maps and returning ordered result keys.
- 2026-02-19: Chose fail-fast runtime validation for missing incident edge data (`<edge_id>:state` / `<edge_id>:flow_rate`) scoped per junction to keep runtime diagnostics explicit and assertable.

- 2026-02-19: Chose to keep the bridge contract solver-native by returning a `HydraulicSolverInputs` bundle that carries a reordered `HydraulicSystemDefinition` plus index maps, instead of introducing a parallel equation schema.
- 2026-02-19: Kept bridge execution as a non-invasive adapter (`solve_compiled_hydraulic_graph`) that forwards solver options unchanged to `solve_hydraulic_system`, ensuring pressure-reference/connected-component diagnostics stay identical to existing behavior.

- 2026-02-19: Implemented transport runtime as a thin adapter (`update_transport_runtime_states`) that calls `update_lag_transport_state` per edge, instead of introducing any new transport equations, to preserve canonical lag behavior by construction.
- 2026-02-19: Treated previous edge flow as first-class runtime state by accepting `previous_edge_flow_rates` and returning updated flow history each macro-step, ensuring deterministic and explicit sign-change tracking continuity.
- 2026-02-19: Added explicit post-update runtime invariant checks (finite temperature/fractions, fraction bounds, and normalized composition sum) to fail fast on invalid model outputs before orchestration consumes edge states.

- 2026-02-19: Chose queue schema normalization at ingress (`request_id`, optional `idempotency_key`, explicit `mutations[]`) in `ConnectionNetwork.queue_reconfiguration`, while deferring structural validation to barrier-time so queueing remains lightweight and deterministic.
- 2026-02-19: Chose barrier batch atomicity over per-request partial success: all queued mutations are applied against a snapshotted network/runtime state and any mutation/compile failure triggers full rollback with a stable `reconfiguration transaction rollback: request '<id>' mutation <n> failed: ...` error surface.

- 2026-02-19: Introduced a dedicated runtime persistence contract (`schema_marker=connection.runtime.snapshot`, `schema_version=1`) instead of reusing the lightweight v1 runtime snapshot payload, so contract evolution and compatibility checks are explicit.
- 2026-02-19: Enforced restore-time graph revision matching against the active compiled network revision to prevent replaying runtime snapshots onto incompatible topology revisions.
- 2026-02-19: Chose full atomic rollback for restore activation (runtime clock/index, committed idempotency keys, queue content, and network counters) with process-state sink rollback on any activation exception.

- 2026-02-19: Kept Task 9 orchestration as a thin composition layer over `run_macro_coupling_step` rather than duplicating sequence/Picard logic, so runtime and connection-layer bookkeeping semantics stay aligned by construction.
- 2026-02-19: Added injectable runtime stage hooks (hydraulics, transport+mixer, boundary propagation) with deterministic default implementations, preserving prior mutation-contract behavior while enabling sequence-parity TDD coverage.

- 2026-02-19: Enforced barrier-only semantics for runtime snapshot capture by rejecting `save_runtime_snapshot` while `_macro_step_active` is true, matching the existing restore-time barrier guard posture.
