## ADDED Requirements

### Requirement: Higher Layers Consume Substrate-Owned Observability Reads
The sandbox session and economics ledger SHALL consume substrate-owned observability snapshot surfaces for physical-state reads rather than reconstructing those reads from low-level runtime internals.

#### Scenario: Economics-facing observability stays separated from policy
- **WHEN** higher-layer code needs runtime observability for educational signals or future economics rollups
- **THEN** those reads come from the substrate-owned snapshot API and not from pricing, tutorial, or ledger logic being pushed down into `PlantBackendSession` or other substrate internals
