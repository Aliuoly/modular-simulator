## MODIFIED Requirements

### Requirement: Higher Layers Consume Substrate-Owned Observability Reads
The sandbox session and economics ledger SHALL consume substrate-owned observability snapshot surfaces for physical-state reads, including tank/process holdup reads, rather than reconstructing those reads from low-level runtime internals or gameplay-owned inventory mirrors.

#### Scenario: Tank state reads use observability rather than gameplay custody
- **WHEN** higher-layer code needs holding-tank holdup, composition, or outlet-flow information
- **THEN** those reads come from the substrate-owned observability snapshot
- **AND** gameplay/session code does not maintain a mirrored tank inventory record with conserved amount or mixed thermodynamic state.

### Requirement: Gameplay Tank Metadata Remains Non-Physical And Non-Public
Phase-1 gameplay SHALL NOT maintain a session-owned mirror of simulation-owned holding-tank conserved inventory or mixed thermodynamic state. Any future gameplay-owned tank metadata introduced above the substrate MAY track only non-physical route or UI intent keyed by tank `process_id`, and SHALL remain non-public.

#### Scenario: Physical tank state is not mirrored in gameplay
- **WHEN** contributors inspect gameplay/session code after `ej7.1`
- **THEN** gameplay does not store per-tank conserved amount, mixed composition, or aggregate thermodynamic state outside the substrate runtime
- **AND** stale helpers such as gameplay-owned `tank_custody.py` are not the authoritative source of tank physical state.

#### Scenario: Public session contracts stay unchanged in ej7.1
- **WHEN** contributors inspect simulation-session methods and snapshots
- **THEN** no new public tank methods, tank snapshot fields, or build/start widenings are introduced by this pack
- **AND** higher-layer tank reads remain observability-driven until a later change explicitly widens gameplay contracts.
