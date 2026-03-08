
- Task 8 note: vector-valued sensor bindings can trigger ambiguous-array validation during `System` construction; vector-write success coverage was stabilized by asserting direct `ControlElement` process-model setter writes while keeping controller dimensionality rollback checks on scalar-signal/vector-actuator wiring.
- Task 11 gotcha: mutating `PFR.total_volume` during a live `step()` path did not reliably exercise the intended differential fail-fast branch in this test harness, so runtime rejection coverage was anchored to invalid controlled `inlet_flow` for deterministic step-time validation.

- Task 13 transient failure: switching `ProcessModel.load` to `model_validate` broke ndarray-typed saved payload hydration because serialized lists bypassed unit-level coercion hooks; reverted to constructor path with targeted ndarray coercion.
- Task 15 wording constraint: the final evidence bundle must describe Task 13 compatibility behavior as staying on the normal constructor hydration path with targeted ndarray coercion, not as forced `model_validate` hydration.
