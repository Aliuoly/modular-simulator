## Context

- The first proof attempt used `FlashDrum` plus `HoldingTank` proxies and was rejected because its evidence was mostly algebraic/hydraulic re-solving with only one-step proxy lag.
- `StagewiseDistillationColumn` is already a true dynamic `ProcessModel` with differential stage inventories plus reflux-drum and bottoms-sump inventories.
- `tests/unit_process/test_layer4_stagewise_distillation.py` already proves multi-step transient evolution, inventory closure, duty-driven condenser/reboiler causality, and holdup-bounded withdrawals.
- `tests/integration/test_dynamic_process_network_workflow.py` already proves connected-runtime state projection for stagewise columns through `ConnectionNetwork` observability.
- The current stagewise model is honest for material-balance-first holdup dynamics, but not for realistic pressure-control dynamics, rigorous thermal realism, or physical thermosyphon/pump-loop reboiler circulation.
- The user explicitly required that the sump story be treated seriously: no fake connection-layer flow controller, and if an internal-only sump/reboiler fallback remains necessary, it must be documented honestly and tracked in follow-up issue `ModularSimulator-9tr.5.2`.

## Goals / Non-Goals

**Goals**
- Deliver one backend-only proof harness centered on `StagewiseDistillationColumn` through current backend/runtime surfaces.
- Demonstrate multi-step top/bottom holdup response plus changing product/stage composition after duty-driven disturbances.
- Keep the proof explicitly material-balance-first and holdup-driven.
- Report demonstrated vs deferred claims honestly.

**Non-Goals**
- Replacing gameplay topology heuristics with runtime-coupled product generation.
- Adding Godot/client/UI commands, public gameplay APIs, or new sandbox start behavior.
- Claiming dynamic top-pressure control, rigorous enthalpy closure, or physically detailed reboiler circulation hydraulics.
- Introducing a connection-layer or public actuator seam for sump-to-reboiler circulation.
- Treating ratio fields as live actuation knobs.

## Decisions

1. **The proof stays on backend substrate surfaces, not gameplay starts.**
   - Assemble and step the proof through existing backend/runtime surfaces only.
   - `SandboxSessionRuntime`, `RealtimeGameService`, start catalogs, and gameplay progression remain unchanged.

2. **The proof unit is `StagewiseDistillationColumn`, not `FlashDrum`.**
   - The proof must rely on the in-repo dynamic stagewise model because it already provides differential tray inventory, reflux-drum holdup, and bottoms-sump holdup.
   - The earlier FlashDrum/HoldingTank proof path is discarded as the primary basis.

3. **The proof centers on holdup-driven top and bottom material-balance dynamics.**
   - Required observed variables should include:
     - `reflux_drum_holdup_mol`
     - `bottoms_sump_holdup_mol`
     - `distillate_flow_mol_s`
     - `bottoms_flow_mol_s`
     - `realized_condensed_flow_mol_s`
     - `realized_reboiler_boilup_flow_mol_s`
     - selected stage or product compositions
   - The proof should treat these as runtime-owned process-state observations, not gameplay reconstruction.

4. **Duty requests are the primary physically honest disturbance seams.**
   - `condenser_duty_request_W` and `reboiler_duty_request_W` are the main required manipulation handles.
   - Passive product-flow readouts may be observed, but withdrawal manipulation is not the center of this proof.
   - `reflux_ratio` and `boilup_ratio` remain non-actuating reference/derived values, not live manipulation handles.

5. **Bottoms behavior must avoid a fake prescribed boundary-rate story as the main realism claim.**
   - The preferred proof path is to let the bottoms sump evolve from tray downflow, duty-driven boilup, and any honest holdup-owned withdrawal behavior already present in the stagewise model.
   - The proof report should not frame prescribed bottoms draw or withdrawal manipulation as the main evidence story.
   - If the final proof still relies on the current internal-only sump/reboiler circulation simplification, that simplification must remain unit-internal, never appear in the connection layer, and must be called out explicitly in the proof report.
   - Because the current model still uses an internal `Q/lambda` boilup surrogate rather than a physical thermosyphon/pump loop, follow-up issue `ModularSimulator-9tr.5.2` tracks that realism gap.

6. **The proof must stay honest about what the current stagewise model does not prove.**
   - Forbidden claims include:
      - realistic top-pressure control,
      - realistic thermosyphon or pump-loop reboiler circulation,
      - rigorous enthalpy-coupled condenser/reboiler behavior,
      - design-meaningful temperature realism,
   - Allowed claims are limited to holdup-owned top/bottom material-balance dynamics under the current constant-molar-overflow and `Q/lambda` surrogate closures.

7. **Controller proof is no longer a required completion gate for this change.**
   - The proof may retain a clearly bounded separate controller/command-bridge appendix only if it does not dilute the main stagewise dynamics story.
   - Completion does not depend on distillation closed-loop controller proof; that remains deferred.

8. **Verification must prove multi-step evolution after a disturbance, not instant plateau-only behavior.**
   - Tests and the proof report must show that selected inventories and compositions continue evolving over multiple successive steps after at least one disturbance.
   - A proof that only shows immediate step jumps to a new plateau is not sufficient.

## Proposed Proof Shape

### Recommended bounded topology
- One `StagewiseDistillationColumn` assembled through existing backend/runtime surfaces
- Feed boundary source(s)
- Distillate and bottoms sink boundaries
- No required external reflux loop unless repo-backed evidence shows it adds value without weakening honesty

### Required manipulations
- `condenser_duty_request_W`
- `reboiler_duty_request_W`
- optional one holdup-owned withdrawal seam if needed for the proof narrative and verified honestly

### Required observations
- `reflux_drum_holdup_mol`
- `bottoms_sump_holdup_mol`
- `distillate_flow_mol_s`
- `bottoms_flow_mol_s`
- `realized_condensed_flow_mol_s`
- `realized_reboiler_boilup_flow_mol_s`
- selected product and/or feed-stage composition keys already published through `process_state_values`

## Risks / Trade-offs

- **Stagewise temperature and pressure semantics are simplified.**
  - Mitigation: keep claims on holdup/material-balance dynamics, not pressure-control or thermal-design realism.
- **The current bottoms-to-reboiler story remains an internal surrogate.**
  - Mitigation: keep it unit-internal, document it honestly, and track the realism gap in `ModularSimulator-9tr.5.2`.
- **Prior FlashDrum-proof code touched runtime and observability files.**
  - Mitigation: remove or revert those edits unless the stagewise proof still needs them with fresh evidence.

## Verification Strategy

- TDD should lead the rewrite.
- Add or rewrite the dedicated backend proof test module so it fails until the stagewise proof harness exists and shows genuine multi-step response.
- Required verification commands:
  - `uv run pytest tests/integration/test_backend_gas_starter_causal_proof.py`
  - `uv run pytest tests/integration/test_dynamic_process_network_workflow.py -k "stagewise or duty"`
  - `uv run python examples/dynamic_simulation_demos/backend_gas_starter_causal_proof.py`
- Expected evidence:
  - proof plant assembles through existing backend/runtime surfaces,
  - condenser/reboiler duty disturbances cause multi-step evolution in top/bottom holdup and composition/flow observables,
  - proof report names demonstrated vs deferred realism claims,
  - no gameplay, Godot, or public-session contract widening occurs,
  - if an internal-only sump/reboiler simplification remains in the final proof narrative, the report explicitly names it and references `ModularSimulator-9tr.5.2` as the realism follow-up.
