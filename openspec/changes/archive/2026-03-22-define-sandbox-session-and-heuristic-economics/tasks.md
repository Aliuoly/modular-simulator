## Dependency gate

- [x] D0 Do not begin this pack until `define-phase1-sandbox-build-catalog` has landed:
  - `src/modular_simulation/gameplay/contracts.py` with start/catalog/tutorial contracts,
  - `src/modular_simulation/gameplay/sandbox_catalog.py`, `start_catalog.py`, `tutorial_catalog.py`, and `starts/`,
  - any required generic backend-session helpers in `src/modular_simulation/cli/backend_session.py`,
  - `tests/gameplay/test_sandbox_contracts.py` as the dependency-owned starting contract file,
  - the dependency-owned fields required here are already frozen and tested: `PlayStartDefinition.start_id/start_kind/published_signal_ids/allowed_item_ids`, `SandboxCatalogItemDefinition.item_kind`, `TutorialDefinition.start_id`, and `TutorialGoalDefinition.item_id/required_count`.

## Wave 1 — Freeze simulation-session and economics-ledger contracts with red tests first

- [x] 1.1 Extend `tests/gameplay/test_sandbox_contracts.py` with red tests covering these exact pack-2 contract shapes before implementation:
  - `SimulationSessionSnapshot`,
  - `TutorialGoalStatus`,
  - `BuildApplyResult`,
  - `InventoryLoadResult`,
  - `InventoryWithdrawalResult`,
  - `SimulationAdvanceResult`,
  - `EconomicQuote`,
  - `EquipmentPurchaseReceipt`,
  - `FeedPurchaseReceipt`,
  - `SaleReceipt`,
  - `OperatingCostResult`,
  - `CashLedgerSnapshot`,
  - `HeuristicRuleApplication`,
  - `SandboxRequestError` with stable `error_code` and `message` fields,
  - `SimulationSessionSnapshot.tutorial_completion_time_s` and `InventoryWithdrawalResult.withdrawal_id`,
  - `SaleReceipt.withdrawal_id` and the exact economics-ledger contract fields from `design.md`,
  - exact type/nullability/literal annotations for `session_kind`, `active_tutorial_id`, `tutorial_completion_time_s`, and `EconomicQuote.subject_kind`.
- [x] 1.2 Add red tests in `tests/gameplay/test_economics_ledger.py` covering these exact semantics before implementation:
  - the frozen equipment rule ids and reference tables,
  - each exact purchase/install cost anchor for `place_heater_cooler`, `place_flash_drum`, `place_heat_exchanger`, `place_component_separator`, `install_line_pump`, `install_line_valve`, and `install_line_heat_actuator`,
  - the exact fixed-price entries for `install_sampled_delayed_sensor`, `install_pid_controller`, `place_merge_junction_2x1`, and `place_split_junction_1x2`,
  - the exact `build_process_line` piping formula,
  - the exact feed purchase prices `feed_a = 2.0`, `feed_b = 3.0`,
  - the exact product sale prices `product_a = 8.0`, `product_b = 12.0`,
  - the exact heating-steam and pump-electricity formulas,
  - default starting cash for the one sandbox,
  - rule applications expose rule names and basis snapshots rather than hidden coefficients.
- [x] 1.3 Add red tests in `tests/gameplay/test_sandbox_session.py` covering these exact state transitions before implementation:
  - `start_sandbox()` starts `phase1_process_sandbox_v1`,
  - `start_tutorial(...)` starts the exact tutorial start bound to the tutorial id and rejects unknown tutorial ids with `SandboxRequestError(error_code="unknown_tutorial", ...)`,
  - `install_catalog_item(...)` rejects no-active-session, unknown items, unsupported starts, invalid config, and missing equipment receipts when a ledger is active,
  - `load_feed_inventory(...)` rejects tutorial feed loading, invalid quantity, unknown material, and missing procurement receipts when a ledger is active,
  - `advance(dt_s)` advances elapsed time, updates feed/product inventory deltas, and rejects no-active-session, invalid `dt_s`, and `insufficient_feed_inventory`,
  - `withdraw_product_inventory(...)` rejects no-active-session, unknown products, invalid quantities, and insufficient product inventory,
  - tutorial completion is reported through `tutorial_completion_time_s` with no score field.
- [x] 1.4 Add red tests in `tests/gameplay/test_tutorial_timing.py` covering these exact semantics before implementation:
  - tutorial goals complete only from the frozen goal-count records,
  - completion reporting uses elapsed time to final goal completion,
  - no score field is present in tutorial result contracts.
- [x] 1.5 Verify the red boundary with:
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py tests/gameplay/test_economics_ledger.py tests/gameplay/test_sandbox_session.py tests/gameplay/test_tutorial_timing.py`
  - Expected evidence: session/economics tests fail before the implementation exists.

## Wave 2 — Implement the simulation session and separate economics ledger

- [x] 2.1 Extend `src/modular_simulation/gameplay/contracts.py` only with the frozen pack-2 session/economics result types and `SandboxRequestError`.
- [x] 2.2 Create `src/modular_simulation/gameplay/sandbox_session.py` with the exact simulation-facing methods and rejection semantics frozen in `design.md`.
- [x] 2.3 Create `src/modular_simulation/gameplay/economics.py` with the exact ledger-facing methods, price tables, and operating-cost heuristics frozen in `design.md`.
- [x] 2.4 Consume `src/modular_simulation/gameplay/sandbox_catalog.py`, `start_catalog.py`, `tutorial_catalog.py`, and `starts/` as read-only dependency-owned inputs; do not author or “fix” catalog/start/tutorial payloads in this pack.
- [x] 2.5 Touch `src/modular_simulation/cli/backend_session.py` only if a failing substrate test demonstrates that pack 1’s generic helper surface is still insufficient; any such edit must remain generic and fully covered by substrate tests.

## Wave 3 — Verify explicit handoffs between simulation and economics

- [x] 3.1 Extend `tests/gameplay/test_sandbox_session.py` to cover receipt-gated installs, receipt-gated feed loading, product withdrawal, and explicit inventory/economics handoffs.
- [x] 3.2 Extend `tests/gameplay/test_economics_ledger.py` to cover cash-balance transitions from equipment purchases, feed purchases, operating-cost accrual, and product sales, including `record_product_sale(withdrawal_id)` consuming only prior withdrawal tokens.
- [x] 3.2a In the same ledger tests, assert replay of a previously consumed `withdrawal_id` is rejected with `SandboxRequestError(error_code="unknown_withdrawal_id", ...)` so sale handoffs are single-use.
- [x] 3.3 Add `tests/integration/test_sandbox_session_smoke.py` with these fixed smoke-test cases:
  - sandbox case: open the cash ledger, quote and record `build_process_line` with `length_m = 3.0` and `radius_m = 0.05`, install it, quote and record one `feed_a` procurement, load that inventory, and step once,
  - tutorial case: start `heater_flash_guided_build_v1`, satisfy its three frozen goal records, and verify completion time is reported without any score field,
  - recycle tutorial case: start `recycle_purge_tradeoff_v1`, satisfy its frozen goals, advance once, withdraw one produced product inventory slice from the seeded recycle start, record one sale via the returned `withdrawal_id`, and verify replay of the same token is rejected while sale quoting remains in the economics layer rather than the simulation layer.
- [x] 3.4 Add `examples/dynamic_api_cli/sandbox_backend_minimal.py` showing the canonical split flow: start the sandbox, open the cash ledger, buy one build item, install it, buy feed inventory, step once, withdraw one product slice, then sell it through the economics ledger.
- [x] 3.5 Run the targeted matrix:
  - `uv run pytest tests/gameplay/test_sandbox_contracts.py`
  - `uv run pytest tests/gameplay/test_economics_ledger.py`
  - `uv run pytest tests/gameplay/test_sandbox_session.py`
  - `uv run pytest tests/gameplay/test_tutorial_timing.py`
  - `uv run pytest tests/integration/test_sandbox_session_smoke.py`
  - `uv run python examples/dynamic_api_cli/sandbox_backend_minimal.py`
  - `uv run pytest tests/cli/test_backend_session.py -k "session or revision or checkpoint"`
  - Expected evidence: simulation and economics remain decoupled, heuristics are deterministic and named, and tutorial completion is time-based rather than score-based.

## Wave 4 — Sync docs to the simulation/economics split

- [x] 4.1 Update `docs/game_backend_overview.md` with the one-sandbox plus tutorial-challenge model and the simulation/economics split.
- [x] 4.2 Update `docs/plant_backend_session_user_guide.md` only as needed to point readers to the higher-level simulation session and economics ledger without moving gameplay policy into that guide.
- [x] 4.3 Re-run `uv run pytest tests/test_game_backend_positioning.py` after doc updates to keep repository framing aligned.
