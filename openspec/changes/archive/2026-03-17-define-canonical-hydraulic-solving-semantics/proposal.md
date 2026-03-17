## Why

The repository already has line-oriented hydraulic elements, junction-mixing runtime logic, and a generic nonlinear hydraulic solver, but it does not yet define one canonical statement of how flows are solved across lines, junctions, and unit ports. That gap leaves the pending `canonicalize-hydraulic-junction-api` work without a firm semantics-first contract for flow ownership, junction pressure solving, unit participation, and hydraulic-versus-thermodynamic ordering.

## What Changes

- Define the canonical hydraulic closure for flowsheets as a node-pressure plus mass-balance network solve, with signed line-flow unknowns, hydraulic-node pressure unknowns, line head-balance equations, and explicit pressure-reference or boundary-condition anchoring.
- Specify that junctions are solved as hydraulic nodes with one pressure unknown per junction and mass conservation across all connected lines, including same-node multi-in/multi-out junctions.
- Specify line equations as head-balance relations using line resistance with optional pump, valve, and heat overlays, while keeping hydraulic overlay ownership on the connection network rather than in unit-process wrappers.
- Define line flow ownership explicitly: the connection network is the canonical source of solved line flow rates, and unit-process algebraic models do not implicitly own physical branch allocation.
- Define how unit processes participate in canonical hydraulics through declared ports, hydraulic boundary conditions, pressure/state coupling, and optional constitutive relationships, but not as standalone hidden flow solvers detached from the network closure.
- Distinguish junctions from unit processes architecturally while introducing shared node/port abstractions for common validation and compile behavior; explicitly reject making `UnitProcess` inherit from `JunctionNode` directly.
- Define runtime ordering so hydraulics solve first and thermodynamic mixing/state propagation at junctions happens second using the solved hydraulic flows.
- Identify coordination and required follow-on updates for `canonicalize-hydraulic-junction-api`, `reject-invalid-recycle-loops`, and curated examples so the repository converges on one canonical hydraulic model.

## Capabilities

### New Capabilities
- `hydraulic-network-solving-semantics`: Define the canonical hydraulic closure, junction solving behavior, unit participation model, flow ownership rules, and runtime solve ordering for flowsheet networks.

### Modified Capabilities
- `curated-flowsheet-examples`: Update canonical examples so merge/split topology, recycle pressure boost, and hydraulic control placement follow the canonical network-solving semantics.

## Impact

- Affected code: `src/modular_simulation/flowsheet/flowsheet.py`, `src/modular_simulation/connection/hydraulics/hydraulic_solver.py`, `src/modular_simulation/connection/hydraulics/hydraulic_compile.py`, `src/modular_simulation/connection/topology/network.py`, `src/modular_simulation/connection/topology/topology.py`, `src/modular_simulation/connection/topology/junction.py`, `src/modular_simulation/connection/runtime/thermo_coupling.py`, and connection-domain contracts that currently normalize units versus junctions.
- Affected public API: no standalone end-user API is introduced by this semantics pack, but it becomes the governing contract for the pending high-level junction/line canonicalization work and for removal of `Pump`, `Valve`, `Mixer`, and `Splitter` wrapper models from the canonical surface.
- Affected persistence/contracts: hydraulic unknown naming, topology compilation expectations, runtime coupling assumptions, and any saved examples or guidance that currently imply unit-owned branch flows or wrapper-unit-owned hydraulic behavior.
- Affected tests/examples: hydraulic solver/compile coverage, thermo-coupling and junction-runtime coverage, curated flowsheet examples, recycle-loop examples, and follow-on API migration coverage.
- Coordination impact: this follow-on change must align the pending `canonicalize-hydraulic-junction-api` and `reject-invalid-recycle-loops` proposal packs so they implement line-installed pump semantics, hydraulic-owned branch flows, and hydraulics-first junction evaluation consistently.
