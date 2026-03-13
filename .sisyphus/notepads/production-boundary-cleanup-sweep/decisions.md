# Decisions

## 2026-03-13 — Reconcile recovered boundary cleanup with discoverability refactor

Recovered from session evidence and Oracle review:

### Compatible and keep

- Public immutable connection query models and deterministic query APIs (tasks 1/2)
- Migration off private `ConnectionNetwork` reads (tasks 3/4)
- Typed schema/ingress validation for runtime snapshot, checkpoint, reconfiguration, and CLI/runtime boundaries (tasks 15/16)
- Quickstart ergonomics and example migration (`from_single_process`, `for_system`, tasks 17-19)

Why:

- These strengthen owner-led discoverability instead of fighting it.
- They reduce private-field leakage across CLI/runtime/examples.
- They improve public API clarity at the exact boundaries discoverability work cares about.

### Compatible but reframe

- `ProcessModel` / `StreamPortIO` / `HydraulicElementLike` cleanup wave (tasks 6-13)

Why:

- Keep only the parts that improve public contracts, owner clarity, or discoverability.
- Deprioritize internal churn that only reshapes private numeric kernels without making the public owner-led API easier to discover or reason about.

### Conflicts / superseded

- The old contradictory audit that blocked task 3 should not be preserved as a modern acceptance gate.
- Any cleanup-first framing that competes with the desired discoverability/ownership direction is superseded.

### Convergence point

- Task 17 is the cleanest convergence point between the recovered plan and the desired discoverability refactor.
- Owner-led quickstart helpers are discoverability work and boundary-cleanup work at the same time.

## 2026-03-13 — Reconciled completion boundary

- All recoverable and discoverability-compatible tasks from the reconstructed sweep are now completed on current `main`.
- The remaining unchecked items in the reconstructed plan are archival placeholders whose exact wording was never recoverable from session history.
- Those placeholder items are intentionally left non-executable rather than guessed into existence.

### Completed recoverable scope

- Public query models and deterministic query APIs
- Migration off private `ConnectionNetwork` reads
- Typed ingress/schema validation for live/runtime/checkpoint/reconfiguration boundaries
- Quickstart ergonomics and dynamic API example migration
- Removal of `StreamPortIO` from production typing paths in connection/flowsheet code
- Required hydraulic/demo example cleanup sufficient for compile verification
