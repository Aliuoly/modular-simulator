## Dependency gate

- [x] D0 Do not continue implementation until this revised stagewise change pack is the active source of truth for `ModularSimulator-9tr.5.1`.

## Wave 1 — Rewrite the red proof tests first

- [x] 1.1 Rewrite `tests/integration/test_backend_gas_starter_causal_proof.py` around a backend-only `StagewiseDistillationColumn` proof assembled through current backend/runtime surfaces.
- [x] 1.2 Add a red disturbance test that requires condenser-duty and reboiler-duty manipulations to drive multi-step evolution in:
  - reflux-drum holdup,
  - bottoms-sump holdup,
  - at least one product or selected stage composition,
  - at least one realized duty/flow readout.
- [x] 1.3 Add a red honesty test that fails if the proof report claims realistic pressure control, realistic thermosyphon/pump reboiler circulation, or other deferred realism not actually modeled.
- [x] 1.4 Run the red boundary:
  - `uv run pytest tests/integration/test_backend_gas_starter_causal_proof.py`
  - Expected evidence: stagewise proof tests fail before the rewrite lands.

## Wave 2 — Implement the bounded stagewise proof without widening gameplay/public contracts

- [x] 2.1 Rewrite `examples/dynamic_simulation_demos/backend_gas_starter_causal_proof.py` as a stagewise-column proof harness.
   - Assemble the proof directly through backend/runtime surfaces.
   - Center the disturbance story on `condenser_duty_request_W` and `reboiler_duty_request_W`.
   - Treat product withdrawals as passive readouts unless fresh evidence shows a withdrawal seam is genuinely needed.
- [x] 2.2 Remove or revert FlashDrum/HoldingTank-specific proof scaffolding that is no longer needed.
  - Delete `_ProofObservabilityProvider` and failed gas-loop/holdup-proxy logic if the stagewise proof no longer uses them.
  - Revert any prior runtime or observability modifications unless the stagewise proof still proves they are needed.
- [x] 2.3 Keep proof reporting honest.
  - The proof harness must emit or expose demonstrated-vs-deferred claims alongside recorded histories.
  - If the proof still relies on the current unit-internal `Q/lambda` sump-to-reboiler surrogate, the report must name that limitation and reference follow-up `ModularSimulator-9tr.5.2`.

## Wave 3 — Make the stagewise evidence pass

- [x] 3.1 Make all backend proof tests pass in `tests/integration/test_backend_gas_starter_causal_proof.py`.
- [x] 3.2 Re-run narrow existing stagewise runtime regressions:
  - `uv run pytest tests/integration/test_dynamic_process_network_workflow.py -k "stagewise or duty"`
- [x] 3.3 Run the full affected verification set:
   - `uv run pytest tests/integration/test_backend_gas_starter_causal_proof.py`
   - `uv run python examples/dynamic_simulation_demos/backend_gas_starter_causal_proof.py`

## Wave 4 — Independent review gate before closure

- [x] 4.1 Run `hybrid-code-reviewer` and `simulation-advisor` in parallel on the implemented stagewise proof.
- [x] 4.2 Do not close implementation until both reviews are non-blocking and final evidence still shows:
   - backend-only scope,
   - genuine multi-step holdup/composition response after disturbance,
   - explicit demonstrated vs deferred claims,
   - no gameplay/Godot/public contract widening,
   - no fake connection-layer sump/reboiler control seam,
   - no prescribed bottoms draw rate presented as the main story.

## Wave 5 — Closure hygiene

- [x] 5.1 Sync the implemented delta into live `openspec/specs/session/spec.md` after code, verification, and review are complete.
- [x] 5.2 Update Beads task `ModularSimulator-9tr.5.1` with final evidence and only then close it.
- [x] 5.3 Keep follow-up `ModularSimulator-9tr.5.2` open if the final proof still depends on the current internal sump-to-reboiler surrogate realism boundary.
