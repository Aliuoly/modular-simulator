## MODIFIED Requirements

### Requirement: Wrapper Unit APIs Are Removed From Canonical High-Level Support
The repository SHALL no longer expose `Pump`, `Valve`, `Mixer`, or `Splitter` as supported high-level unit-process APIs, and canonical guidance SHALL direct users to junctions and line-installed hydraulic elements instead.

#### Scenario: Canonical regression suites avoid removed wrapper imports outside migration checks
- **WHEN** repository regression tests exercise canonical high-level unit-process, hydraulic-element, or stream-port behavior after wrapper removal
- **THEN** non-migration tests use supported unit-process exports, explicit junction/line APIs, or lower-level hydraulic primitives rather than importing removed wrapper units from canonical package surfaces or internal wrapper modules

#### Scenario: Pump and valve lower-level coverage lives only in dedicated lower-level suites
- **WHEN** the repository preserves lower-level `Pump` or `Valve` behavior checks after wrapper removal
- **THEN** those checks live in dedicated lower-level coverage such as `tests/unit_process/test_layer4_pump_valve.py` or direct hydraulic-element tests rather than in canonical regression files that are expected to exercise only supported exports

#### Scenario: Mixer and splitter wrapper behavior is retired from canonical regression files
- **WHEN** canonical regression files previously covered `Mixer` or `Splitter` wrapper stream-port or hydraulic-default behavior
- **THEN** that coverage is removed from canonical regression files, while any remaining internal behavior coverage stays in dedicated lower-level mixer/splitter tests rather than through canonical imports

#### Scenario: Dedicated migration tests remain the place that asserts wrapper import failure
- **WHEN** the repository verifies migration guidance for removed `Pump`, `Valve`, `Mixer`, or `Splitter` symbols
- **THEN** those assertions live in dedicated wrapper-removal coverage rather than being spread across unrelated regression files that should collect cleanly under the canonical API
