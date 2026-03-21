## MODIFIED Requirements

### Requirement: Wrapper Unit APIs And Live Wrapper Vocabulary Are Fully Removed
The live non-archive repository SHALL no longer ship, reference, or preserve the lower-level unit-process wrapper models for the deleted topology-wrapper and flow-control-wrapper classes. Supported live guidance SHALL describe only explicit junctions, explicit sinks, line-installed `PumpInstall` / `ValveInstall` / `HeatInstall` elements, supported hydraulic primitives, and the remaining supported unit-process families.

#### Scenario: Live package surfaces no longer preserve wrapper symbols or wrapper-specific import guidance
- **WHEN** a user inspects the live non-archive `unit_processes` package surfaces after this change
- **THEN** the repository does not expose lower-level wrapper modules or wrapper-specific import guidance for those deleted unit-process models

#### Scenario: Live source does not keep wrapper-name dispatch tables or runtime defaults
- **WHEN** a user inspects live serializer/load handling, runtime helper tables, and package exports after this change
- **THEN** live source does not carry wrapper-name lookup tables, wrapper-specific migration strings, or default behaviors keyed by the deleted wrapper model names

#### Scenario: Live tests describe only supported surfaces or synthetic fixtures
- **WHEN** repository tests verify hydraulics, runtime coupling, controller harnesses, or supported process-model behavior after this change
- **THEN** those tests use supported unit families, junction-plus-line-install flowsheet APIs, direct hydraulic primitives, or local synthetic fixtures rather than deleted wrapper model classes or wrapper-name assertions

#### Scenario: Live docs avoid the deleted wrapper-model vocabulary
- **WHEN** a user reads non-archive repository docs after this change
- **THEN** the docs describe the supported topology model without mentioning the deleted lower-level wrapper model names

#### Scenario: Archive history remains the only preserved record of wrapper-model names
- **WHEN** repository history or archived OpenSpec changes need to explain the removed wrapper model vocabulary
- **THEN** that historical record lives only under archived artifacts rather than in the live non-archive repository
