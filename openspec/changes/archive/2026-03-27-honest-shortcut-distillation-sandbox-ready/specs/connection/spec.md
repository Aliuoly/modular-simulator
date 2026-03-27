## ADDED Requirements

### Requirement: Dynamic Distillation Column Uses Normal Runtime/Subnetwork Composition
The dynamic distillation-column unit SHALL be composed and stepped through the existing runtime/subsystem/network pathways, not through topology-only placeholders.

#### Scenario: Runtime stepping path is the authoritative behavior surface
- **WHEN** a dynamic distillation column is instantiated in a connected plant runtime
- **THEN** it is stepped through standard subsystem/network orchestration with runtime-owned state evolution
- **AND** behavior is not emulated by topology metadata or inventory-only heuristics.

### Requirement: Multi-Feed Port Connectivity Is Runtime-Authoritative
Connection/runtime wiring SHALL support multiple feed inputs with explicit stage assignment semantics for the dynamic distillation-column unit.

#### Scenario: Multiple connected feeds preserve assigned-stage semantics
- **WHEN** two or more feed streams are connected to the distillation-column unit
- **THEN** each feed’s runtime flow/composition is applied at its configured stage assignment/feed height
- **AND** feed routing is represented in runtime-owned process behavior rather than post-hoc output adjustment.

### Requirement: Distillation Actuation Uses Unit-Local Boundary Requests Without Controller-Binding Claims
Dynamic distillation-column actuation in this change SHALL use unit-local boundary seam fields on `StagewiseDistillationColumn` together with explicit external material-routing seams, and SHALL NOT claim controller-bindable distillation control elements in this pack.

#### Scenario: Actuation namespace remains plant-seam native
- **WHEN** condenser duty requests, reboiler duty requests, reflux return, or product routing is actuated
- **THEN** `StagewiseDistillationColumn` exposes unit-local boundary seam fields for those requests and external routing seams for material transfer
- **AND** material-line seams use repo-native namespaced endpoints such as `actuator/valve/<id>` and `actuator/pump/<id>` as the general platform contract
- **AND** `actuator/heat/<id>` remains a line-owned platform namespace, not a distillation-specific requirement in this pack
- **AND** product-line valves, reflux liquid outlet seams, and reflux-return inlet routing remain explicit runtime-owned topology
- **AND** no distillation-specific controller binding contract is introduced by this requirement.

### Requirement: Product Withdrawals Are External Holdup Withdrawals
Distillate and bottoms routing SHALL be wired as external withdrawals from reflux-drum and bottoms-sump holdups, respectively.

#### Scenario: Product withdrawal connectivity is explicit
- **WHEN** product lines are connected in runtime
- **THEN** distillate flow is withdrawn from reflux-drum holdup through explicit product-line seams
- **AND** bottoms flow is withdrawn from bottoms-sump holdup through explicit product-line seams
- **AND** both withdrawals remain liquid-phase and bounded by available owner holdup
- **AND** withdrawal behavior is not represented as implicit internal sink terms detached from external routing.

### Requirement: Ratio Fields Are Not Runtime Actuation Interfaces
Connection/runtime wiring SHALL treat `reflux_ratio` and `boilup_ratio` as initialization/reference/derived-observable semantics only.

#### Scenario: Runtime actuation does not bind ratio knobs
- **WHEN** runtime actuation interfaces are enumerated for dynamic distillation behavior
- **THEN** actuation interfaces are explicit unit-local boundary request fields plus external material-routing seams
- **AND** any exposed `reflux_ratio`/`boilup_ratio` values are derived telemetry from actual runtime flows
- **AND** `reflux_ratio`/`boilup_ratio` are not required as live actuator bindings.

### Requirement: Topology-Only Starts Do Not Qualify As Dynamic-Column Runtime Exposure
Starts that remain topology-only SHALL continue to exclude the distillation-column item from public runtime-supported build surfaces.

#### Scenario: Existing topology-only gameplay remains excluded
- **WHEN** current topology-only starts are inspected in this change
- **THEN** they do not claim dynamic distillation-column runtime behavior
- **AND** they keep existing hide/reject gating for `place_shortcut_distillation_column`.
