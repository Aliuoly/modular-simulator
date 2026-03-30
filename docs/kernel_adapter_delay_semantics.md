# Kernel Adapter Delay Semantics

This phase makes the split baseline's delay treatment explicit instead of leaving it implied by transport runtime implementation details.

## Current baseline: `external_transport_history`

- **Adapter:** `SplitKernelAdapter`
- **Declared strategy:** `external_transport_history`
- **Wrapped payload key:** `transport_runtime_state`
- **Mapped fields owned by the baseline:** `edge_states`, `previous_edge_flow_rates`, `junction_states`

The split runtime preserves today's lag and deadtime behavior by keeping delay state outside any solver-shaped state vector. The adapter captures and restores that bundle through the existing `transport_runtime_state` payload rather than renaming the live snapshot schema in Phase 2.

## Candidate strategy matrix

| Strategy | Meaning | Required mapping rule |
| --- | --- | --- |
| `external_transport_history` | Delay remains in an external history/buffer bundle equivalent to today's runtime ownership. | Publish the payload key and mapped fields explicitly. |
| `augmented_state` | Delay is moved into a candidate-owned augmented state representation. | Publish an explicit mapping from current transport-history semantics to the augmented state and define restore behavior for checkpoint reloads and runtime edits. |
| `hybrid` | Delay is split across external history and candidate-owned internal state. | Publish the split ownership, the mapping from current transport history, and restore behavior for checkpoint reloads and runtime edits. |

## Mandatory contract for future candidates

Any candidate that uses `augmented_state` or `hybrid` must:

1. Publish an explicit mapping from current `transport_runtime_state` semantics to its replacement state.
2. Define how that mapping is restored after checkpoint reloads.
3. Define how that mapping is restored and updated during `post_edit_recovery`.
4. Avoid silent fallback that discards or cold-starts delay state when a restore path is requested.

This requirement comes from Phase 2 decisions D-10 and D-11: alternative delay treatments are allowed, but they must remain explicit and safely restorable.

## Required core, not optional solver shape

Delay-semantics declarations belong to the required adapter core. Declaring `external_transport_history`, `augmented_state`, or `hybrid` does **not** imply support for optional solver capabilities such as state-vector export, residual evaluation, Jacobian access, or bounds.

The split baseline is the reference example: it publishes delay semantics and mapping metadata while honestly exposing no optional solver capabilities.
