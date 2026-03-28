# Progression

## Purpose

This capability defines gas-first sandbox progression for the main phase-1 world, including staged unlock structure, research submission rules, and progression snapshot semantics.

## Requirements

### Requirement: Main-World Progression Uses An Exact Gas-First Stage Ladder With Batched Unlocking
The main free-play sandbox SHALL use exactly this staged sweet-wet-gas progression ladder, with the first two stages available as the starter batch and the final two stages unlocked together by one mixed-product research milestone:

- `gas_inlet_separation_v1`
  - title `Inlet gas separation`
  - initial starter-batch stage for `phase1_process_sandbox_v1`
  - available item ids `("place_inlet_gas_separator", "build_process_line")`
- `teg_dehydration_v1`
  - title `TEG dehydration`
  - starter-batch stage available immediately in `phase1_process_sandbox_v1`
  - available item ids `("place_teg_contactor", "place_rich_glycol_flash_tank", "place_lean_rich_glycol_exchanger", "place_teg_regenerator", "install_glycol_circulation_pump")`
- `jt_low_temperature_separation_v1`
  - title `JT / low-temperature separation`
  - unlocked only by `unlock_cold_recovery_train_v1`
  - available item ids `("place_gas_gas_exchanger", "install_jt_valve", "place_low_temperature_separator")`
- `condensate_stabilization_v1`
  - title `Condensate stabilization`
  - unlocked only by `unlock_cold_recovery_train_v1`
  - available item ids `("place_condensate_stabilizer",)`

#### Scenario: Stage order is fixed
- **WHEN** a contributor inspects the progression catalog for the main sandbox
- **THEN** those exact four stage ids, titles, and stage-to-item mappings exist in that exact order

#### Scenario: Starter batch availability is fixed
- **WHEN** a caller starts `phase1_process_sandbox_v1`
- **THEN** `gas_inlet_separation_v1` and `teg_dehydration_v1` are already unlocked starter-batch stages
- **AND** `jt_low_temperature_separation_v1` and `condensate_stabilization_v1` remain locked behind `unlock_cold_recovery_train_v1`

### Requirement: Research Unlocks Use One Exact Batched Inventory Submission Recipe
The abstract research submission action SHALL use exactly this research id and inventory recipe:

- `unlock_cold_recovery_train_v1`
  - target stages `("jt_low_temperature_separation_v1", "condensate_stabilization_v1")`
  - required product quantities `{"separator_gas": 20.0, "unstabilized_condensate": 10.0, "dry_gas": 20.0}`

#### Scenario: Research recipes are frozen exactly
- **WHEN** a contributor inspects a research unlock definition
- **THEN** its research id, target stage ids, and required product quantities match the exact frozen recipe above

#### Scenario: Research submission must match the exact recipe
- **WHEN** a caller submits missing, extra, non-numeric, non-positive, or quantity-mismatched product amounts for an otherwise known research id
- **THEN** the request is rejected with `SandboxRequestError(error_code="invalid_quantity", ...)`, consumes no inventory, and unlocks no new stage

### Requirement: Progression Snapshot Shape Is Stable
`ProgressionSnapshot` SHALL expose exactly `active_stage_id`, `unlocked_stage_ids`, `available_item_ids`, and `available_research_ids`.

#### Scenario: Progression contract shape is fixed before implementation
- **WHEN** a contributor inspects the progression-facing gameplay contracts
- **THEN** those exact fields are present and no separate client-only unlock schema is required to discover current stage state

### Requirement: Main-World Progression Snapshot Semantics Are Frozen
For `phase1_process_sandbox_v1`:

- `active_stage_id` SHALL mean the highest unlocked stage in the fixed gas-first ladder.
- `available_item_ids` SHALL be the cumulative unlocked subset of the main-world `allowed_item_ids`, preserving stage order and keeping `build_process_line` at the tail.
- `available_research_ids` SHALL contain only the next batched research unlock id for the current state, or `()` after the cold-recovery/stabilization batch is unlocked.
- The batched research id SHALL be visible from sandbox start so the player can plan toward the mixed-product milestone without hidden discovery.

#### Scenario: Starter progression snapshot is exact
- **WHEN** a caller starts `phase1_process_sandbox_v1`
- **THEN** `active_stage_id = "teg_dehydration_v1"`
- **AND** `unlocked_stage_ids = ("gas_inlet_separation_v1", "teg_dehydration_v1")`
- **AND** `available_item_ids = ("place_inlet_gas_separator", "place_teg_contactor", "place_rich_glycol_flash_tank", "place_lean_rich_glycol_exchanger", "place_teg_regenerator", "install_glycol_circulation_pump", "build_process_line")`
- **AND** `available_research_ids = ("unlock_cold_recovery_train_v1",)`

#### Scenario: Successful research unlock advances to the exact cold-recovery snapshot
- **WHEN** `unlock_cold_recovery_train_v1` succeeds
- **THEN** `active_stage_id = "condensate_stabilization_v1"`
- **AND** `unlocked_stage_ids = ("gas_inlet_separation_v1", "teg_dehydration_v1", "jt_low_temperature_separation_v1", "condensate_stabilization_v1")`
- **AND** `available_item_ids = ("place_inlet_gas_separator", "place_teg_contactor", "place_rich_glycol_flash_tank", "place_lean_rich_glycol_exchanger", "place_teg_regenerator", "install_glycol_circulation_pump", "place_gas_gas_exchanger", "install_jt_valve", "place_low_temperature_separator", "place_condensate_stabilizer", "build_process_line")`
- **AND** `available_research_ids = ()`

### Requirement: Research Submission Is Sandbox-Only And Inventory-Backed
The progression system SHALL expose one abstract inventory-submission action `submit_research_unlock(...)` for the active sandbox and SHALL not require a placeable research building in this pack.

#### Scenario: Sandbox research consumes product inventory and unlocks the next exact batch
- **WHEN** the active session is `phase1_process_sandbox_v1`, the requested research id is currently available, and the submitted product inventory satisfies the frozen mixed-product recipe
- **THEN** the session consumes the submitted product inventory and the resulting progression snapshot includes both newly unlocked cold-recovery/stabilization stages and their item ids

#### Scenario: Tutorial sessions do not expose research submission
- **WHEN** a caller attempts research submission during a tutorial session
- **THEN** the request is rejected with a stable progression-unavailable error rather than treating tutorials as part of the main unlock ladder

### Requirement: The Batched Research Recipe Is Reachable From The Starter Batch
The main sandbox SHALL keep the batched research recipe reachable from the starter batch without requiring later-stage items.

#### Scenario: Starter examples can satisfy the mixed-product research recipe
- **WHEN** the player uses the starter-batch example-backed inlet-separation and dehydration topologies, buys `sweet_wet_gas`, and advances finite positive simulation time
- **THEN** the session can accumulate enough `separator_gas`, `unstabilized_condensate`, and `dry_gas` to satisfy `unlock_cold_recovery_train_v1`

#### Scenario: Post-unlock cold-recovery examples remain aligned with unlocked products
- **WHEN** the player uses the stage-3 and stage-4 example-backed topologies after `unlock_cold_recovery_train_v1`
- **THEN** the session can still accumulate `ngl_liquids` and `stabilized_condensate` through the newly unlocked qualifying paths

### Requirement: Locked Main-World Items Are Rejected Before Unlock
Main-world catalog items that belong to later stages SHALL remain unavailable until the exact prerequisite research unlock succeeds.

#### Scenario: Supported-but-locked item is rejected clearly
- **WHEN** a caller attempts to install a main-world gas item that is valid for `phase1_process_sandbox_v1` but not yet listed in the current progression snapshot’s `available_item_ids`
- **THEN** the install request is rejected with `SandboxRequestError(error_code="item_locked", ...)`

### Requirement: Proxy Gameplay Units Are Explicitly Part Of The Progression Contract
The gas-first ladder SHALL use high-fidelity real-world unit names even when the initial implementation maps those units onto currently available proxy substrates.

#### Scenario: Proxy boundary is explicit instead of implied
- **WHEN** a contributor inspects the progression and catalog documentation for `place_teg_contactor`, `place_teg_regenerator`, or `place_condensate_stabilizer`
- **THEN** the artifact explicitly states that the gameplay name is real-world while the initial backend implementation may use a current substrate proxy rather than a dedicated absorber or column model
