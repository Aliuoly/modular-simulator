# Recycle Loop Validation

## Purpose

This capability defines how the high-level `Flowsheet` compiler detects and rejects physically invalid directed recycle loops before simulation proceeds. A recycle loop is considered physically invalid if it contains no supported line-installed pump with a strictly positive configured initial boost value. The goal is to surface non-viable configurations at compile time with an actionable diagnostic rather than allowing them to produce silent zero-flow behavior at runtime.

## Requirements

### Requirement: Invalid Recycle Loops Are Rejected At Compile Time
The high-level `Flowsheet` compiler SHALL inspect all compile-time-detectable directed recycle loops and SHALL reject any loop that lacks supported line-installed pump-based pressure boost with a strictly positive configured initial boost value.

#### Scenario: Recycle loop has no pressure boost
- **WHEN** a flowsheet compile detects a directed cycle and none of the cycle's edges include supported line-installed pump boost metadata with a strictly positive configured initial boost value
- **THEN** compilation fails with a validation error instead of only emitting a warning

#### Scenario: Recycle loop has zero configured pump boost
- **WHEN** a directed recycle loop includes pump metadata but every pump on that loop has a zero configured initial boost value at compile time
- **THEN** the loop is rejected as physically invalid

#### Scenario: Diagnostic identifies invalid loop and remediation
- **WHEN** the compiler rejects an invalid recycle loop
- **THEN** the diagnostic identifies the ordered offending loop path, states that no supported positive line-installed pressure boost was found on that loop, and provides remediation guidance to add a pump or pressure-boosting stage on the recycle path

#### Scenario: Any invalid loop causes compile failure
- **WHEN** a flowsheet contains multiple directed recycle loops and at least one of them lacks supported positive pressure boost
- **THEN** compilation fails even if other loops are valid

### Requirement: Pressure-Boosted Recycle Loops Remain Allowed
The high-level `Flowsheet` compiler SHALL allow a directed recycle loop to proceed when every detected loop satisfies the supported positive line-installed pump-boost rule and all other existing validations pass.

#### Scenario: Recycle loop includes supported boost element
- **WHEN** a detected directed cycle includes at least one supported line-installed pump boost with a strictly positive configured initial boost value
- **THEN** recycle-loop validation passes for that loop and compilation continues normally if no other validation rule fails

#### Scenario: Mixed valid and invalid loops are reported deterministically
- **WHEN** a flowsheet contains one recycle loop with supported positive line-installed pump boost and another recycle loop without it
- **THEN** compilation fails because of the invalid loop and reports the offending loop path(s) deterministically

#### Scenario: Non-cyclic topologies remain unchanged
- **WHEN** a flowsheet topology contains no directed recycle loop
- **THEN** recycle-loop validation does not introduce new compile failures
