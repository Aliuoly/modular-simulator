## ADDED Requirements

### Requirement: Topology-Only Starts Keep Distillation-Column Exposure Gated
Current topology-only gameplay starts SHALL continue to hide and reject `place_shortcut_distillation_column` in this change.

#### Scenario: Public supported-build lists remain unchanged for current starts
- **WHEN** current playable modes/starts expose their supported build surfaces
- **THEN** `place_shortcut_distillation_column` is not advertised on those topology-only surfaces
- **AND** existing gameplay exposure remains unchanged by this change pack.

#### Scenario: Direct install attempts still reject with existing start-allowlist contract
- **WHEN** a caller attempts to install `place_shortcut_distillation_column` on a topology-only start
- **THEN** the session layer rejects with `unsupported_on_start`
- **AND** rejection uses existing start-allowlist behavior rather than a new fallback or broadened error translation path.

### Requirement: Dynamic-Column Runtime Exposure Uses Unit-Local Actuation Requests While Controller Scope Is Deferred
This change SHALL stop at dynamic plant behavior, unit-local boundary seam fields, and runtime observability; controller binding/closed-loop proof for distillation SHALL remain deferred to `ModularSimulator-9tr.6`.

#### Scenario: Session/runtime contract separates plant behavior from controller proof
- **WHEN** contributors inspect completion criteria for this change
- **THEN** runtime dynamic-column behavior and observability are required for completion
- **AND** expanded seams (reflux-return routing, liquid-phase holdup-bounded external product withdrawals, condenser/reboiler unit-local duty-request fields) are required as runtime unit behavior
- **AND** closed-loop controller-proof acceptance remains explicitly out-of-scope for this pack.

### Requirement: Runtime Session Interfaces Do Not Promote Ratio Knobs To Live Actuation
Session/runtime contracts SHALL keep `reflux_ratio` and `boilup_ratio` as initialization/reference/derived-observable semantics only.

#### Scenario: Session completeness is not satisfied by ratio-knob wiring
- **WHEN** session-layer runtime contracts are reviewed for dynamic distillation actuation
- **THEN** live runtime actuation is represented by explicit unit-local boundary request fields plus external material-routing seams
- **AND** any exposed ratio values are derived from actual runtime flows
- **AND** exposing or storing ratio values does not count as providing live actuation wiring.

### Requirement: Dynamic Distillation Session Semantics Are Stagewise-Only
Session-level expectations SHALL treat stagewise runtime behavior as the sole distillation behavior path and SHALL NOT depend on a `ShortcutDistillation` compatibility route.

#### Scenario: Dynamic behavior contract is satisfied only by stagewise runtime
- **WHEN** a contributor evaluates whether this change is complete
- **THEN** completion requires stage-by-stage dynamic runtime behavior
- **AND** no `ShortcutDistillation` runtime/shim pathway is part of completion criteria.
