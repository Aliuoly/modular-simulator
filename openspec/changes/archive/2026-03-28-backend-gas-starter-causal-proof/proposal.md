## Why

Repo evidence shows the first backend proof attempt missed the approved intent for genuine multi-step plant dynamics:

- the FlashDrum + HoldingTank harness produced mostly algebraic or one-step proxy behavior rather than sustained multi-step transient evolution,
- the user explicitly rejected instant plateau-style response as insufficient,
- the repository already contains a stronger dynamic basis in `StagewiseDistillationColumn`, with runtime-owned reflux-drum holdup, bottoms-sump holdup, duty-driven boilup/condensation surrogates, and connected-runtime observability.

Beads task `ModularSimulator-9tr.5.1` therefore needs a bounded backend-only proof that demonstrates genuinely dynamic, holdup-driven top/bottom causality through current repo structures, without widening Godot/client/gameplay contracts.

## What Changes

- Replace the failed FlashDrum-centered proof target with a backend-only `StagewiseDistillationColumn` proof assembled through the existing backend/runtime substrate.
- Freeze the proof around the repo-backed dynamic seams the current stagewise model already supports honestly:
  - `condenser_duty_request_W`,
  - `reboiler_duty_request_W`,
  - passive product-flow readouts and holdup observations from the reflux drum and bottoms sump,
  - existing connected-runtime observability of holdup, realized duty/flow, and stage/product composition.
- Require the proof to demonstrate multi-step evolution in top and bottom inventories plus composition/flow response over several runtime steps after disturbances.
- Keep the realism contract explicit:
  - demonstrated: holdup-driven top/bottom inventory response inside the current stagewise model,
  - deferred: realistic top-pressure control, rigorous energy balance, physically explicit thermosyphon/pump reboiler circulation hydraulics, gameplay coupling, and public control/API widening.
- Record the discovered realism gap separately in Beads `ModularSimulator-9tr.5.2` if the proof continues to rely on the current internal sump-to-reboiler `Q/lambda` surrogate.

## Capabilities

### Modified Capabilities
- `session`

## Impact

- Expected implementation files:
  - `examples/dynamic_simulation_demos/backend_gas_starter_causal_proof.py` (rewrite around stagewise proof harness / report entrypoint)
  - `tests/integration/test_backend_gas_starter_causal_proof.py` (rewrite proof verification to require genuine multi-step stagewise response)
- Expected reverted-or-removed prior proof surfaces unless fresh evidence justifies them:
  - `src/modular_simulation/connection/topology/unit_process_wiring.py` (remove failed HoldingTank-only proof extension if no longer needed)
  - `src/modular_simulation/connection/runtime/runtime.py` (remove prior FlashDrum-proof runtime workaround if stagewise proof does not require it)
- Reused-but-unchanged substrate surfaces should remain the main implementation basis:
  - `src/modular_simulation/cli/backend_session.py`
  - `src/modular_simulation/connection/runtime/connected_plant_orchestrator.py`
  - `tests/integration/test_dynamic_process_network_workflow.py`
  - `tests/unit_process/test_layer4_stagewise_distillation.py`
- OpenSpec delta file:
  - `openspec/changes/backend-gas-starter-causal-proof/specs/session/spec.md`

## Explicitly Deferred

- No Godot/client work.
- No `SandboxSessionRuntime` or gameplay product-generation rewrite.
- No new public helper for arbitrary unit boundary-state mutation.
- No claim that the proof demonstrates realistic pressure-control dynamics.
- No claim that the proof demonstrates rigorous enthalpy-coupled condenser/reboiler thermal behavior.
- No claim that the proof demonstrates physical thermosyphon or pump-loop sump-to-reboiler hydraulics beyond the current unit-internal surrogate.
- No generic controller-to-network auto-staging claim for distillation; closed-loop distillation controller proof remains deferred to later work.
