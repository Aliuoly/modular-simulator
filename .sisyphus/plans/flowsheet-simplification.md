# Flowsheet API Simplification

## TL;DR
> **Summary**: Eliminate ~500 lines of boilerplate from every flowsheet by adding a stream I/O contract to unit processes, auto-wiring them through the existing System→Subsystem→Orchestrator pipeline, integrating real hydraulic elements, and providing a `Flowsheet` builder that automates it all. Breaking changes allowed.
> **Deliverables**: StreamData/StreamPortIO protocol on all 12 units, auto System/Subsystem creation, hydraulic element integration, `Flowsheet` builder class, rewritten demo (~50-80 lines), updated tests
> **Effort**: Large
> **Parallel**: YES - 4 waves
> **Critical Path**: L1 (Stream I/O + Flow Basis) → L2 (Auto-Wiring + Hydraulics) → L3 (Flowsheet Builder) → L4 (Demo + Final Verification)

## Context

### Original Request
The flowsheet demo (`examples/unit_process_flowsheet/flowsheet_demo.py`) is 583 lines but only ~15 lines express actual process engineering intent. The rest is boilerplate: manual inlet application, manual outlet snapshot, custom `_UnitSubsystem` adapter, fake hydraulic solver, fake transport step, helper functions. This same pattern repeats in `two_tank_reaction_comparison.py` (691 lines). The user wants:
- Dramatic boilerplate reduction
- ALL processes using REAL pressure-driven flow through the connection layer
- ALL unit processes capable of having sensors and controllers installed
- Breaking changes are acceptable if they produce cleaner code
- No architectural forks — one path for all processes

### Interview Summary
- **Backward compat**: NOT required — breaking changes allowed for cleaner code
- **Sensors/controllers**: REQUIRED on all unit processes — no-op phases unacceptable
- **Hydraulics**: REAL pressure-driven flow required — no fake bypass
- **Flow basis**: StreamData carries mol/s; units that need volumetric convert internally via PropertyPackage density
- **1→2 port cardinality**: Adapter shimming at compile path, NOT changing ProcessBinding core invariant
- **Connection syntax**: Port inference for SINGLE_IO, explicit `unit.port` for multi-port/multi-outlet

### Metis Review (gaps addressed)
- **ProcessBinding cardinality**: 1→2 units (FlashDrum, ShortcutDistillation) can't compile through existing ProcessBinding. Solution: adapter shimming that presents paired virtual ports to ProcessBinding while internally routing to real ports.
- **Flow basis mismatch**: CSTR/PFR use L/s, Pump/Valve use m³/s, others use mol/s. Solution: StreamData canonical mol/s basis with apply_inlet() converting per unit using PropertyPackage density.
- **ThermoBoundaryPropagationStep boundary feeds**: Skips edges without process bindings on both ends. Feed nodes need explicit handling in builder.
- **Descriptor/topology port matching**: ConnectedPlantOrchestrator.initialize() enforces exact descriptor vs topology port tuple equality. Auto-derived descriptors must match deterministically.
- **Sensor/controller support**: Unit processes must be wrapped in System→Subsystem (not custom lightweight adapter) to get full sensor/controller support.

### Oracle Review (architecture decisions)
- Layer implementation order: L1 (Stream I/O) → L2 (Adapter + Hydraulics) → L3 (Builder) → L4 (Demo)
- `apply_inlet`/`get_outlet_stream` as protocol on unit processes, not on ProcessModel base
- Explicit per-unit port→attribute maps (not naming heuristics)
- Don't relax ProcessBinding globally; adapter-side asymmetric binding
- Units own their HydraulicElement; Flowsheet provides fallback defaults
- Compile/runtime validation: unbound mandatory inlets, ambiguous port inference, recycle convergence

## Work Objectives

### Core Objective
Make unit processes first-class citizens of the existing System→Subsystem→Orchestrator pipeline, with real pressure-driven flow, full sensor/controller support, and a builder API that eliminates all boilerplate.

### Deliverables
1. `StreamData` frozen dataclass (canonical mol/s basis) + `StreamPortIO` protocol
2. `apply_inlet(port, stream)` and `get_outlet_stream(port) -> StreamData` on all 12 unit processes with explicit port→attribute maps
3. Flow basis conversion in `apply_inlet()` for CSTR/PFR (L/s) and Pump/Valve (m³/s)
4. `HydraulicElement` integration: each unit provides its pressure-flow relationship for Newton-Raphson solver
5. Asymmetric port adapter for 1→2 units (FlashDrum, ShortcutDistillation) at compile path
6. `Flowsheet` builder: `add_unit()`, `add_feed()`, `connect()`, `chain()`, `compile()`, `run()`
7. Auto System creation (unit process → System with sensor/controller support)
8. Auto Subsystem/Descriptor creation from unit's `.ports` + publication map
9. Rewritten flowsheet demo (~50-80 lines)
10. Updated/new test suite

### Definition of Done (verifiable conditions with commands)
```bash
# All tests pass
uv run python -m pytest tests/ -q

# Flowsheet demo is 50-80 lines
uv run python -c "p=open('examples/unit_process_flowsheet/flowsheet_demo.py').readlines(); print(len(p)); assert 50<=len(p)<=80"

# Demo runs and produces valid results
uv run python examples/unit_process_flowsheet/flowsheet_demo.py

# All 12 units have StreamPortIO methods
uv run python -c "
from modular_simulation.unit_processes import *
for cls in [Mixer,Splitter,HeaterCooler,Pump,Valve,FlashDrum,ConversionReactor,CSTR,PFR,ShortcutDistillation,HeatExchanger,ComponentSeparator]:
    assert hasattr(cls, 'apply_inlet'), f'{cls.__name__} missing apply_inlet'
    assert hasattr(cls, 'get_outlet_stream'), f'{cls.__name__} missing get_outlet_stream'
print('All 12 units have StreamPortIO')
"

# Type checking passes on new code
uv run basedpyright src/modular_simulation/thermodynamics/ src/modular_simulation/unit_processes/ src/modular_simulation/connection/

# Linting passes on new code
uv run ruff check src/modular_simulation/thermodynamics/ src/modular_simulation/unit_processes/ src/modular_simulation/connection/
```

### Must Have
- `StreamData` with canonical mol/s flow basis
- `apply_inlet`/`get_outlet_stream` on ALL 12 unit processes
- Flow basis conversion (mol/s ↔ L/s, mol/s ↔ m³/s) in apply_inlet for volumetric units
- Real `HydraulicElement` per unit (not fake bypass)
- Asymmetric port adapter for 1→2 units
- `Flowsheet` builder that auto-creates System→Subsystem→Network→Orchestrator
- Full sensor/controller support on all unit processes (via System wrapping)
- Rewritten demo demonstrating the simplified API
- Ability to `connect("flash.vapor_outlet", "column")` (explicit multi-port syntax)
- Ability to `chain("feed", "heater", "cstr")` (SINGLE_IO shorthand)

### Must NOT Have (guardrails)
- NO separate "simple flowsheet" vs "connected plant" code paths — one architecture
- NO fake hydraulic/transport bypass implementations
- NO no-op sensor/calculation/controller phases — all units get real System wrapping
- NO naming-convention-based heuristics for port→attribute mapping — explicit maps only
- NO changes to ProcessBinding equal-port invariant — adapter shimming only
- NO string-based expression evaluation
- NO new unit processes (this plan is about the abstraction layer only)
- NO UI/frontend changes

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- **Test framework**: pytest (existing)
- **Test decision**: Tests-after (each task includes its tests)
- **QA policy**: Every task has agent-executed scenarios
- **Evidence**: `.sisyphus/evidence/task-{N}-{slug}.{ext}`
- **Regression**: Full test suite must pass at every wave gate
- **Key validation**: Demo produces valid mass/energy balances through REAL hydraulic path

## Execution Strategy

### Parallel Execution Waves

**Wave 1 — Stream I/O Contract** (5 tasks, parallel):
- Task 1: StreamData dataclass + StreamPortIO protocol definition [deep]
- Task 2: apply_inlet/get_outlet_stream on SINGLE_IO units (HeaterCooler, Pump, Valve, ConversionReactor, ComponentSeparator) [unspecified-high]
- Task 3: apply_inlet/get_outlet_stream on multi-outlet units (FlashDrum, ShortcutDistillation, HeatExchanger) [deep]
- Task 4: apply_inlet/get_outlet_stream on multi-inlet units (Mixer, Splitter) [unspecified-high]
- Task 5: apply_inlet/get_outlet_stream on dynamic units with flow basis conversion (CSTR, PFR) [deep]

**Wave 2 — Auto-Wiring + Hydraulics** (4 tasks, parallel after Wave 1):
- Task 6: HydraulicElement integration for all unit processes [deep]
- Task 7: Asymmetric port adapter for 1→2 units at network compile path [deep]
- Task 8: Auto System creation + auto Subsystem/Descriptor derivation from unit [deep]
- Task 9: Boundary propagation upgrade — auto-inlet/outlet via StreamPortIO [deep]

**Wave 3 — Flowsheet Builder** (3 tasks, parallel after Wave 2):
- Task 10: Flowsheet builder core (add_unit, add_feed, connect, chain, compile, run) [deep]
- Task 11: Flowsheet compile-time validation (unbound inlets, ambiguous ports, species mismatch) [unspecified-high]
- Task 12: Flowsheet results API (structured output, history access, stream snapshots) [unspecified-high]

**Wave 4 — Demo + Final Verification** (3 tasks, parallel after Wave 3):
- Task 13: Rewrite flowsheet demo using Flowsheet builder (~50-80 lines) [unspecified-high]
- Task 14: Integration test — multi-unit flowsheet with sensors/controllers [deep]
- Task 15: Update/fix any broken existing tests from breaking changes [unspecified-high]

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 (StreamData) | — | 2, 3, 4, 5, 6, 8, 9, 10 |
| 2 (SINGLE_IO units) | 1 | 6, 8, 9, 10 |
| 3 (Multi-outlet units) | 1 | 6, 7, 8, 9, 10 |
| 4 (Multi-inlet units) | 1 | 6, 8, 9, 10 |
| 5 (Dynamic units) | 1 | 6, 8, 9, 10 |
| 6 (Hydraulics) | 1-5 | 10 |
| 7 (Asymmetric adapter) | 3 | 10 |
| 8 (Auto System/Subsystem) | 1-5 | 10 |
| 9 (Boundary propagation) | 1-5 | 10 |
| 10 (Flowsheet builder) | 6, 7, 8, 9 | 13 |
| 11 (Validation) | 10 | 13 |
| 12 (Results API) | 10 | 13 |
| 13 (Demo rewrite) | 10, 11, 12 | F1-F4 |
| 14 (Integration test) | 10 | F1-F4 |
| 15 (Fix broken tests) | 2-5 | F1-F4 |

### Agent Dispatch Summary

| Wave | Tasks | Categories |
|------|-------|------------|
| 1 | 5 | 2× deep, 2× unspecified-high, 1× deep |
| 2 | 4 | 4× deep |
| 3 | 3 | 1× deep, 2× unspecified-high |
| 4 | 3 | 1× deep, 2× unspecified-high |
| Final | 4 | 1× oracle, 2× unspecified-high, 1× deep |

## TODOs

### Wave 1 — Stream I/O Contract

- [x] 1. StreamData Dataclass and StreamPortIO Protocol

  **What to do**:
  Create `src/modular_simulation/thermodynamics/stream.py`:
  - `StreamData` frozen dataclass:
    ```python
    @dataclass(frozen=True)
    class StreamData:
        temperature: float          # K
        pressure: float             # Pa
        mole_fractions: tuple[float, ...]  # canonical order per ActiveSpeciesRegistry
        molar_flow_rate: float      # mol/s (CANONICAL basis)
        species_ids: tuple[str, ...] | None = None  # CAS numbers
        phase: str | None = None    # "vapor", "liquid", "two-phase"
        enthalpy_molar: float | None = None  # J/mol
        entropy_molar: float | None = None   # J/mol/K
    ```
  - `StreamData.from_port_condition(condition: PortCondition) -> StreamData` factory
  - `StreamData.to_port_condition() -> PortCondition` conversion
  - `StreamData.to_material_state() -> MaterialState` conversion
  - `StreamPortIO` Protocol:
    ```python
    class StreamPortIO(Protocol):
        @property
        def ports(self) -> UnitProcessPorts: ...
        def apply_inlet(self, port_name: str, stream: StreamData) -> None: ...
        def get_outlet_stream(self, port_name: str) -> StreamData: ...
    ```
  - `PortAttributeMap` TypedDict or dataclass: `flow: str`, `temperature: str`, `pressure: str`, `composition: str` — maps port name to attribute names on the unit
  - Helper: `default_inlet_map(port_name: str) -> PortAttributeMap` — generates `{port_name}_flow`, `{port_name}_temperature`, etc. For "inlet" port, returns `inlet_flow`, `inlet_temperature`, etc.
  - Helper: `default_outlet_map(port_name: str) -> PortAttributeMap` — same for outlets

  **Must NOT do**: Do NOT auto-convert flow basis here (that's per-unit). Do NOT make StreamData mutable. Do NOT import thermo.

  **Recommended Agent Profile**:
  - Category: `deep` — Core protocol that all units and builder depend on
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2, 3, 4, 5, 6, 8, 9, 10 | Blocked By: —

  **References**:
  - Pattern: `src/modular_simulation/connection/state.py` — MaterialState and PortCondition
  - Pattern: `src/modular_simulation/thermodynamics/algebraic_process_model.py` — UnitProcessPorts
  - Pattern: `src/modular_simulation/connection/material_models.py` — Protocol pattern
  - Pattern: All 12 unit processes in `src/modular_simulation/unit_processes/` — inlet/outlet attribute naming

  **Acceptance Criteria**:
  - [ ] `StreamData(temperature=300, pressure=101325, mole_fractions=(0.5,0.5), molar_flow_rate=1.0)` creates frozen instance
  - [ ] Round-trip: `StreamData.from_port_condition(sd.to_port_condition())` preserves all fields
  - [ ] `default_inlet_map("inlet")` returns `PortAttributeMap(flow="inlet_flow", temperature="inlet_temperature", pressure="inlet_pressure", composition="inlet_composition")`
  - [ ] `default_outlet_map("vapor_outlet")` returns `PortAttributeMap(flow="vapor_outlet_flow", ...)` 
  - [ ] `uv run basedpyright src/modular_simulation/thermodynamics/stream.py` passes
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: StreamData creation and conversion
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.thermodynamics.stream import StreamData
    sd = StreamData(temperature=350.0, pressure=101325.0, mole_fractions=(0.5,0.5), molar_flow_rate=2.0, species_ids=('7732-18-5','64-17-5'))
    pc = sd.to_port_condition()
    sd2 = StreamData.from_port_condition(pc)
    print(f'T={sd2.temperature}, P={sd2.pressure}, flow={sd2.molar_flow_rate}')
    print(f'roundtrip={sd == sd2}')
    "
    Expected: stdout contains roundtrip=True
    Evidence: .sisyphus/evidence/task-1-stream-data.txt

  Scenario: PortAttributeMap generation
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.thermodynamics.stream import default_inlet_map, default_outlet_map
    im = default_inlet_map('hot_inlet')
    om = default_outlet_map('vapor_outlet')
    print(f'inlet: flow={im.flow}, T={im.temperature}')
    print(f'outlet: flow={om.flow}, T={om.temperature}')
    "
    Expected: stdout contains "hot_inlet_flow" and "vapor_outlet_flow"
    Evidence: .sisyphus/evidence/task-1-port-map.txt
  ```

  **Commit**: YES | Message: `feat(stream): add StreamData dataclass and StreamPortIO protocol` | Files: `src/modular_simulation/thermodynamics/stream.py`, `tests/unit_process/test_stream_data.py`

---

- [x] 2. StreamPortIO on SINGLE_IO Units (HeaterCooler, Pump, Valve, ConversionReactor, ComponentSeparator)

  **What to do**:
  Add `apply_inlet()` and `get_outlet_stream()` methods to these 5 units. All use standard SINGLE_IO port naming (inlet → `inlet_*`, outlet → `outlet_*`).

  For each unit:
  - Add `_INLET_MAP` and `_OUTLET_MAP` class-level `dict[str, PortAttributeMap]` mapping port names to attribute names
  - Implement `apply_inlet(port_name, stream)`: validate port_name exists in self.ports.inlets, then set each attribute from StreamData via the map. For Pump and Valve: convert `stream.molar_flow_rate` (mol/s) → m³/s via `molar_flow / density` where density comes from PropertyPackage if available, else raise error.
  - Implement `get_outlet_stream(port_name)`: read attributes via map, return StreamData. For Pump and Valve: convert outlet flow back from m³/s → mol/s.
  - ComponentSeparator has DUAL_OUTLET but standard naming (outlet_1, outlet_2), so include it here with 2 outlet maps

  **Must NOT do**: Do NOT change the internal process logic. Do NOT change constructor signatures. Do NOT change state categories.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Repetitive but requires careful attribute mapping
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6, 8, 9, 10 | Blocked By: 1

  **References**:
  - Pattern: `src/modular_simulation/thermodynamics/stream.py` (Task 1) — StreamData, PortAttributeMap
  - File: `src/modular_simulation/unit_processes/heater_cooler.py` — HeaterCooler states and attributes
  - File: `src/modular_simulation/unit_processes/pump.py` — Pump states (m³/s flow basis)
  - File: `src/modular_simulation/unit_processes/valve.py` — Valve states (m³/s flow basis)
  - File: `src/modular_simulation/unit_processes/conversion_reactor.py` — ConversionReactor states
  - File: `src/modular_simulation/unit_processes/component_separator.py` — ComponentSeparator states (DUAL_OUTLET)

  **Acceptance Criteria**:
  - [ ] `HeaterCooler.apply_inlet("inlet", stream)` sets all inlet attributes from StreamData
  - [ ] `HeaterCooler.get_outlet_stream("outlet")` returns StreamData with correct values
  - [ ] `Pump.apply_inlet("inlet", stream)` converts mol/s → m³/s using property package density
  - [ ] `Valve.apply_inlet("inlet", stream)` converts mol/s → m³/s using property package density
  - [ ] `ComponentSeparator.get_outlet_stream("outlet_1")` and `get_outlet_stream("outlet_2")` both work
  - [ ] Invalid port name raises ValueError with helpful message
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: HeaterCooler round-trip
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.unit_processes.heater_cooler import HeaterCooler
    from modular_simulation.thermodynamics.stream import StreamData
    hc = HeaterCooler(n_species=2, mode='duty', duty_setpoint=10000, pressure_drop=5000)
    # ... attach system, apply inlet, step, get outlet
    print('HeaterCooler StreamPortIO works')
    "
    Expected: stdout contains "works"
    Evidence: .sisyphus/evidence/task-2-single-io.txt

  Scenario: Pump flow basis conversion
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_stream_port_io.py::test_pump_flow_conversion -v
    Expected: Test passes, mol/s correctly converted to m³/s
    Evidence: .sisyphus/evidence/task-2-pump-flow.txt
  ```

  **Commit**: YES | Message: `feat(units): add StreamPortIO to SINGLE_IO unit processes with flow basis conversion` | Files: `src/modular_simulation/unit_processes/heater_cooler.py`, `src/modular_simulation/unit_processes/pump.py`, `src/modular_simulation/unit_processes/valve.py`, `src/modular_simulation/unit_processes/conversion_reactor.py`, `src/modular_simulation/unit_processes/component_separator.py`, `tests/unit_process/test_stream_port_io.py`

---

- [x] 3. StreamPortIO on Multi-Outlet Units (FlashDrum, ShortcutDistillation, HeatExchanger)

  **What to do**:
  Add `apply_inlet()` and `get_outlet_stream()` to units with non-standard outlet naming:

  **FlashDrum**:
  - Inlet map: `{"inlet": PortAttributeMap(flow="inlet_flow", temperature="inlet_temperature", pressure="inlet_pressure", composition="inlet_composition")}`
  - Outlet map: `{"vapor_outlet": PortAttributeMap(flow="vapor_flow", temperature="outlet_temperature", pressure="outlet_pressure", composition="vapor_composition"), "liquid_outlet": PortAttributeMap(flow="liquid_flow", temperature="outlet_temperature", pressure="outlet_pressure", composition="liquid_composition")}`
  - Note: outlet_temperature and outlet_pressure are shared across both outlets

  **ShortcutDistillation**:
  - Inlet map: `{"inlet": ...}` (standard)
  - Outlet map: `{"distillate": PortAttributeMap(flow="distillate_flow", temperature="condenser_temperature", pressure="condenser_pressure", composition="distillate_composition"), "bottoms": PortAttributeMap(flow="bottoms_flow", temperature="reboiler_temperature", pressure="reboiler_pressure", composition="bottoms_composition")}`
  - Note: distillation has different T/P per outlet (condenser vs reboiler conditions)

  **HeatExchanger**:
  - Dual inlet map: `{"hot_inlet": ..., "cold_inlet": ...}` (each prefixed)
  - Dual outlet map: `{"hot_outlet": ..., "cold_outlet": ...}` (each prefixed)
  - Standard naming (hot_inlet_flow, hot_outlet_flow, etc.)

  **Must NOT do**: Do NOT change internal flash/distillation/HX calculation logic. Do NOT add new states.

  **Recommended Agent Profile**:
  - Category: `deep` — Non-standard naming requires careful per-unit mapping
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6, 7, 8, 9, 10 | Blocked By: 1

  **References**:
  - File: `src/modular_simulation/unit_processes/flash_drum.py` — FlashDrum states (vapor_flow, liquid_flow, vapor_composition, liquid_composition)
  - File: `src/modular_simulation/unit_processes/shortcut_distillation.py` — ShortcutDistillation states (distillate_*, bottoms_*)
  - File: `src/modular_simulation/unit_processes/heat_exchanger.py` — HeatExchanger states (hot_*, cold_*)

  **Acceptance Criteria**:
  - [ ] `FlashDrum.get_outlet_stream("vapor_outlet")` returns StreamData with vapor_flow and vapor_composition
  - [ ] `FlashDrum.get_outlet_stream("liquid_outlet")` returns StreamData with liquid_flow and liquid_composition
  - [ ] `ShortcutDistillation.get_outlet_stream("distillate")` returns correct distillate stream
  - [ ] `ShortcutDistillation.get_outlet_stream("bottoms")` returns correct bottoms stream
  - [ ] `HeatExchanger.apply_inlet("hot_inlet", stream)` sets hot-side inlet attributes
  - [ ] `HeatExchanger.get_outlet_stream("cold_outlet")` returns cold-side outlet stream
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: FlashDrum dual outlet streams
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_stream_port_io.py::test_flash_drum_dual_outlet -v
    Expected: Test passes, both vapor and liquid outlets return valid StreamData
    Evidence: .sisyphus/evidence/task-3-flash-outlets.txt

  Scenario: Invalid port name on multi-outlet unit
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.unit_processes.flash_drum import FlashDrum
    fd = FlashDrum(n_species=2, thermal_mode='isothermal')
    try: fd.get_outlet_stream('nonexistent')
    except ValueError as e: print(f'Error: {e}')
    "
    Expected: stdout contains "Error:" with valid port names listed
    Evidence: .sisyphus/evidence/task-3-invalid-port.txt
  ```

  **Commit**: YES | Message: `feat(units): add StreamPortIO to multi-outlet units (FlashDrum, Distillation, HeatExchanger)` | Files: `src/modular_simulation/unit_processes/flash_drum.py`, `src/modular_simulation/unit_processes/shortcut_distillation.py`, `src/modular_simulation/unit_processes/heat_exchanger.py`, `tests/unit_process/test_stream_port_io.py`

---

- [x] 4. StreamPortIO on Multi-Inlet Units (Mixer, Splitter)

  **What to do**:
  Add `apply_inlet()` and `get_outlet_stream()` to Mixer and Splitter:

  **Mixer**:
  - Dynamic inlet count (n_inlets). Inlet ports: `inlet_1`, `inlet_2`, ..., `inlet_N`
  - Inlet map: `{"inlet_i": PortAttributeMap(flow=f"inlet_{i}_flow", temperature=f"inlet_{i}_temperature", ...)}` for each i
  - Single outlet: standard `outlet_*` naming
  - `apply_inlet("inlet_2", stream)` sets `inlet_2_flow`, `inlet_2_temperature`, etc.

  **Splitter**:
  - Single inlet: standard `inlet_*` naming
  - Dynamic outlet count (n_outlets). Outlet ports: `outlet_1`, `outlet_2`, ..., `outlet_N`
  - Outlet map: `{"outlet_i": PortAttributeMap(flow=f"outlet_{i}_flow", ...)}` for each i

  **Must NOT do**: Do NOT change mixing/splitting logic. Do NOT change state declarations.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Dynamic port count but standard naming
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6, 8, 9, 10 | Blocked By: 1

  **References**:
  - File: `src/modular_simulation/unit_processes/mixer.py` — Mixer states with dynamic inlets
  - File: `src/modular_simulation/unit_processes/splitter.py` — Splitter states with dynamic outlets

  **Acceptance Criteria**:
  - [ ] `Mixer(n_inlets=3).apply_inlet("inlet_2", stream)` sets correct attributes
  - [ ] `Mixer(n_inlets=3).get_outlet_stream("outlet")` returns mixed outlet
  - [ ] `Splitter(n_outlets=2).get_outlet_stream("outlet_1")` returns correct split stream
  - [ ] Invalid port index raises clear error
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Mixer multi-inlet apply
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_stream_port_io.py::test_mixer_multi_inlet -v
    Expected: Test passes
    Evidence: .sisyphus/evidence/task-4-mixer-inlets.txt

  Scenario: Splitter multi-outlet get
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_stream_port_io.py::test_splitter_multi_outlet -v
    Expected: Test passes
    Evidence: .sisyphus/evidence/task-4-splitter-outlets.txt
  ```

  **Commit**: YES | Message: `feat(units): add StreamPortIO to Mixer and Splitter with dynamic port mapping` | Files: `src/modular_simulation/unit_processes/mixer.py`, `src/modular_simulation/unit_processes/splitter.py`, `tests/unit_process/test_stream_port_io.py`

---

- [x] 5. StreamPortIO on Dynamic Units with Flow Basis Conversion (CSTR, PFR)

  **What to do**:
  Add `apply_inlet()` and `get_outlet_stream()` to CSTR and PFR. These are special because:
  - Both use L/s (volumetric) flow basis internally, but StreamData uses mol/s
  - Both are ProcessModel subclasses with DIFFERENTIAL states (not AlgebraicProcessModel)
  - Need PropertyPackage or density to convert between mol/s ↔ L/s

  For each unit:
  - `apply_inlet("inlet", stream)`:
    1. Set inlet_temperature, inlet_pressure, inlet_composition from StreamData directly
    2. Convert `stream.molar_flow_rate` (mol/s) → L/s: `volumetric_flow = molar_flow * molecular_weight / density_kg_m3 * 1000` (1000 for m³→L)
    3. Density from PropertyPackage.density(T, P, z, "liquid") if available, else use ideal gas law or raise error
    4. Set `inlet_flow = volumetric_flow_L_s`
  - `get_outlet_stream("outlet")`:
    1. Read outlet_temperature, outlet_pressure, outlet_composition
    2. Convert outlet_flow (L/s) → mol/s: reverse of above
    3. Return StreamData with mol/s

  **Must NOT do**: Do NOT change CSTR/PFR internal calculations. Do NOT change their flow basis internally (they stay L/s). Do NOT hardcode density — use PropertyPackage.

  **Recommended Agent Profile**:
  - Category: `deep` — Flow basis conversion requires thermodynamic calculations
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6, 8, 9, 10 | Blocked By: 1

  **References**:
  - File: `src/modular_simulation/unit_processes/cstr.py` — CSTR states (L/s flow, has set_property_package)
  - File: `src/modular_simulation/unit_processes/pfr.py` — PFR states (L/s flow, has set_property_package)
  - API: `PropertyPackage.density(T, P, z, "liquid")` → kg/m³
  - API: `PropertyPackage.molecular_weight(z)` → g/mol

  **Acceptance Criteria**:
  - [ ] `CSTR.apply_inlet("inlet", stream)` converts mol/s to L/s correctly
  - [ ] `CSTR.get_outlet_stream("outlet")` converts L/s back to mol/s correctly
  - [ ] Round-trip: apply_inlet(stream) then get_outlet_stream should recover approximately same molar flow
  - [ ] PFR same behavior as CSTR
  - [ ] Without PropertyPackage, raises clear error about missing density
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: CSTR flow basis round-trip
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_stream_port_io.py::test_cstr_flow_basis_conversion -v
    Expected: Test passes, molar flow survives round-trip within 1%
    Evidence: .sisyphus/evidence/task-5-cstr-flow.txt

  Scenario: Missing PropertyPackage error
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.unit_processes.cstr import CSTR
    from modular_simulation.thermodynamics.stream import StreamData
    c = CSTR(n_species=2, species_names=('A','B'), volume=10)
    sd = StreamData(temperature=300, pressure=101325, mole_fractions=(0.5,0.5), molar_flow_rate=1.0)
    try: c.apply_inlet('inlet', sd)
    except Exception as e: print(f'Error type: {type(e).__name__}')
    "
    Expected: stdout contains error about missing property package or density
    Evidence: .sisyphus/evidence/task-5-missing-pkg.txt
  ```

  **Commit**: YES | Message: `feat(units): add StreamPortIO to CSTR and PFR with mol/s↔L/s flow basis conversion` | Files: `src/modular_simulation/unit_processes/cstr.py`, `src/modular_simulation/unit_processes/pfr.py`, `tests/unit_process/test_stream_port_io.py`

---

### Wave 2 — Auto-Wiring + Hydraulics

- [x] 6. HydraulicElement Integration for Unit Processes

  **What to do**:
  Add `to_hydraulic_element()` to each unit process so they participate in real Newton-Raphson hydraulic solving:

  **Pump**: Already has `pressure_rise_curve` and `d_dp_d_flow_rate`. Create `PumpHydraulicElement` wrapping these: residual = `downstream_P - upstream_P - dp_curve(flow)`, jacobian = `-d_dp_d_flow`. This is the most natural hydraulic integration — Pump IS a pressure source.

  **Valve**: Already has `valve_cv` and pressure drop calculation. Create `ValveHydraulicElement`: residual = `upstream_P - downstream_P - (flow/Cv)^2`, jacobian from analytical derivative.

  **HeaterCooler**: `PipeHydraulicElement` with default resistance `5.0e3` and `delta=1.0e-6`.

  **Reactors (CSTR, PFR, ConversionReactor)**: `PipeHydraulicElement` with default resistance `1.0e4` and `delta=1.0e-6`.

  **FlashDrum**: `PipeHydraulicElement` with default resistance `5.0e3` and `delta=1.0e-6`.

  **ShortcutDistillation**: `PipeHydraulicElement` with default resistance `2.0e4` and `delta=1.0e-6`.

  **ComponentSeparator**: `PipeHydraulicElement` with default resistance `5.0e3` and `delta=1.0e-6`.

  **HeatExchanger**: `PipeHydraulicElement` with default resistance `5.0e3` and `delta=1.0e-6` per side.

  **Mixer**: `PipeHydraulicElement` with low default resistance `1.0e3` and `delta=1.0e-6`.

  **Splitter**: `PipeHydraulicElement` with low default resistance `1.0e3` and `delta=1.0e-6`.

  Each unit process must implement:
  - `to_hydraulic_element(port_name: str) -> HydraulicElement`
  - For SINGLE_IO units, `port_name` is `"outlet"`
  - For multi-outlet units, `port_name` is one of the real outlet ports (`"vapor_outlet"`, `"liquid_outlet"`, `"distillate"`, `"bottoms"`, etc.)

  **Must NOT do**: Do NOT modify the existing hydraulic solver. Do NOT add flow-dependent resistance models for units that don't need them (keep it simple: fixed resistance or known curves).

  **Recommended Agent Profile**:
  - Category: `deep` — Needs to understand hydraulic element protocol deeply
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10 | Blocked By: 1-5

  **References**:
  - Pattern: `src/modular_simulation/connection/hydraulic_element.py` — HydraulicElement protocol, PipeHydraulicElement, ValveHydraulicElement, PumpHydraulicElement
  - Pattern: `src/modular_simulation/connection/hydraulic_compile.py` — How hydraulic graph is compiled
  - File: `src/modular_simulation/unit_processes/pump.py` — pressure_rise_curve, d_dp_d_flow_rate
  - File: `src/modular_simulation/unit_processes/valve.py` — valve_cv, pressure drop calculation

  **Acceptance Criteria**:
  - [ ] `Pump.to_hydraulic_element()` returns a valid HydraulicElement with correct residual/jacobian
  - [ ] `Valve.to_hydraulic_element()` returns valid HydraulicElement
  - [ ] `HeaterCooler.to_hydraulic_element("outlet")` returns PipeHydraulicElement with resistance `5.0e3`
  - [ ] All elements pass `validate_hydraulic_graph()` when compiled into a network
  - [ ] Newton-Raphson solver converges for a simple 2-unit network using real elements
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Pump hydraulic element convergence
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_hydraulic_elements.py::test_pump_hydraulic -v
    Expected: Test passes, solver converges to physical flow rate
    Evidence: .sisyphus/evidence/task-6-pump-hydraulic.txt

  Scenario: Full network hydraulic solve
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_hydraulic_elements.py::test_network_hydraulic_solve -v
    Expected: Test passes, all flows solved by Newton-Raphson
    Evidence: .sisyphus/evidence/task-6-network-hydraulic.txt
  ```

  **Commit**: YES | Message: `feat(hydraulics): add HydraulicElement integration to all unit processes` | Files: `src/modular_simulation/unit_processes/*.py` (all 12), `src/modular_simulation/thermodynamics/hydraulic_adapters.py`, `tests/unit_process/test_hydraulic_elements.py`

---

- [x] 7. Asymmetric Port Adapter for 1→2 Units

  **What to do**:
  Create an adapter at the network compile path that allows 1-inlet/2-outlet units (FlashDrum, ShortcutDistillation) and 2-inlet/2-outlet units (HeatExchanger) to participate in the connection network:

  - ProcessBinding requires equal inlet/outlet counts. Rather than changing this invariant, create an `AsymmetricPortAdapter` that:
    1. For FlashDrum (1 in, 2 out): Presents to the network as a unit with 1 inlet port and 2 separate outgoing connection lines. The adapter internally manages 2 ProcessBinding-like mappings for the outlets.
    2. For ShortcutDistillation (1 in, 2 out): Same pattern.
    3. For HeatExchanger (2 in, 2 out): ProcessBinding already works (equal counts).
  
  - The adapter should work transparently with the `ThermoBoundaryPropagationStep` and hydraulic solver.

  **Must NOT do**: Do NOT change the ProcessBinding class itself. Do NOT create a separate orchestrator path.

  **Recommended Agent Profile**:
  - Category: `deep` — Complex compile-path integration
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10 | Blocked By: 3

  **References**:
  - Pattern: `src/modular_simulation/connection/process_binding.py` — ProcessBinding, bind_inlets, bind_outlets
  - Pattern: `src/modular_simulation/connection/network.py` — ConnectionNetwork.compile()
  - Pattern: `src/modular_simulation/connection/hydraulic_compile.py` — compile_hydraulic_graph
  - Pattern: `src/modular_simulation/connection/thermo_coupling.py` — ThermoBoundaryPropagationStep

  **Acceptance Criteria**:
  - [ ] FlashDrum with 1 inlet + 2 outlets compiles in ConnectionNetwork without error
  - [ ] ShortcutDistillation with 1 inlet + 2 outlets compiles
  - [ ] Hydraulic solver runs on network containing asymmetric units
  - [ ] Boundary propagation correctly routes to both outlets
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: FlashDrum asymmetric compile
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_asymmetric_ports.py::test_flash_drum_compile -v
    Expected: Test passes, network compiles with FlashDrum's 1→2 ports
    Evidence: .sisyphus/evidence/task-7-flash-compile.txt

  Scenario: Distillation asymmetric compile
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_asymmetric_ports.py::test_distillation_compile -v
    Expected: Test passes
    Evidence: .sisyphus/evidence/task-7-distillation-compile.txt
  ```

  **Commit**: YES | Message: `feat(connection): add asymmetric port adapter for 1→2 unit processes` | Files: `src/modular_simulation/connection/asymmetric_adapter.py`, `src/modular_simulation/connection/network.py` (if compile path modified), `tests/unit_process/test_asymmetric_ports.py`

---

- [x] 8. Auto System Creation + Auto Subsystem/Descriptor Derivation

  **What to do**:
  Create utilities that auto-wrap unit processes in the existing System→Subsystem pipeline:

  **`create_system_for_unit(unit: ProcessModel, dt: float) -> System`**:
  - Creates a `System(dt=dt, process_model=unit, sensors=(), calculations=(), control_elements=())`
  - Relies on normal `System` initialization (do NOT call `model_post_init()` manually)
  - Returns System ready for sensor/controller installation

  **`create_subsystem_for_unit(unit: ProcessModel, unit_id: str, dt: float, runtime_context: SimulationRuntimeContext | None = None) -> Subsystem`**:
  - Calls `create_system_for_unit(unit, dt)` to get System
  - Auto-derives `SubsystemRuntimeDescriptor`:
    - `descriptor_id = unit_id`
    - `process_id = unit_id`
    - `inlet_ports = tuple(Port(port_id=p, direction="inlet") for p in unit.ports.inlets)`
    - `outlet_ports = tuple(Port(port_id=p, direction="outlet") for p in unit.ports.outlets)`
    - `publication_map` = auto-derived from unit's state list (all ALGEBRAIC + DIFFERENTIAL states published with their names as tags)
  - If `runtime_context` provided and unit has `set_property_package()`, auto-inject
  - Returns `Subsystem(descriptor, system)` — the EXISTING Subsystem class, giving full sensor/controller support

  Place in `src/modular_simulation/connection/unit_process_wiring.py`.

  **Must NOT do**: Do NOT create a new Subsystem subclass. Do NOT bypass the existing System/Subsystem infrastructure. Do NOT modify System or Subsystem classes.

  **Recommended Agent Profile**:
  - Category: `deep` — Integration with complex System initialization and publication system
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10 | Blocked By: 1-5

  **References**:
  - Pattern: `src/modular_simulation/framework/system.py` — System constructor and initialization
  - Pattern: `src/modular_simulation/connection/subsystem_descriptor.py` — Subsystem, SubsystemRuntimeDescriptor
  - Pattern: `src/modular_simulation/connection/domain_contracts.py` — Port, UnitProcess
  - Pattern: `src/modular_simulation/thermodynamics/runtime_context.py` — SimulationRuntimeContext

  **Acceptance Criteria**:
  - [ ] `create_subsystem_for_unit(HeaterCooler(...), "heater", dt=0.1)` returns valid Subsystem
  - [ ] Returned Subsystem has correct inlet/outlet ports matching unit's .ports
  - [ ] `subsystem.add_sensor(sensor)` works (sensor/controller support via System)
  - [ ] `subsystem.run_process_phase(0.1)` correctly steps the unit
  - [ ] Auto-derived publication_map includes all ALGEBRAIC states
  - [ ] Auto-injected property_package when runtime_context provided
  - [ ] Works for all 12 unit process types
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Auto-wrap HeaterCooler in Subsystem
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_unit_process_wiring.py::test_auto_wrap_heater -v
    Expected: Test passes, Subsystem created with correct ports and publication map
    Evidence: .sisyphus/evidence/task-8-auto-wrap.txt

  Scenario: Sensor installation on auto-wrapped unit
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_unit_process_wiring.py::test_sensor_on_wrapped_unit -v
    Expected: Test passes, sensor reads unit's algebraic states
    Evidence: .sisyphus/evidence/task-8-sensor.txt
  ```

  **Commit**: YES | Message: `feat(connection): add auto System/Subsystem creation for unit processes` | Files: `src/modular_simulation/connection/unit_process_wiring.py`, `tests/unit_process/test_unit_process_wiring.py`

---

- [x] 9. Boundary Propagation Upgrade via StreamPortIO

  **What to do**:
  Upgrade `ThermoBoundaryPropagationStep` to use the `StreamPortIO` protocol for inlet application and outlet reading, instead of the manual closure-based approach:

  - When propagating from unit A's outlet to unit B's inlet:
    1. Call `unit_A.get_outlet_stream(source_port)` → StreamData
    2. Call `unit_B.apply_inlet(target_port, stream_data)`
  - This replaces the manual attribute-setting closures in the demo
  - Handle feed boundaries: `add_feed()` stores a fixed StreamData that gets applied to the first unit's inlet
  - Handle multi-outlet routing: FlashDrum.vapor_outlet → Column.inlet vs FlashDrum.liquid_outlet → Tank.inlet
  - Respect flow basis conversion (StreamData is mol/s, units convert internally)

  **Must NOT do**: Do NOT change ConnectionRuntimeOrchestrator protocol. Do NOT reintroduce manual inlet/outlet closure plumbing.

  **Recommended Agent Profile**:
  - Category: `deep` — Core coupling logic upgrade
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10 | Blocked By: 1-5

  **References**:
  - Pattern: `src/modular_simulation/connection/thermo_coupling.py` — Current ThermoBoundaryPropagationStep
  - Protocol: `src/modular_simulation/thermodynamics/stream.py` (Task 1) — StreamPortIO, StreamData
  - Pattern: `src/modular_simulation/connection/runtime.py` — RuntimeBoundaryPropagationStep protocol

  **Acceptance Criteria**:
  - [ ] Two connected StreamPortIO units auto-propagate outlet→inlet via StreamData
  - [ ] Feed boundary correctly applied to first unit
  - [ ] Multi-outlet routing works (vapor_outlet → one unit, liquid_outlet → another)
  - [ ] Flow basis conversion happens transparently (mol/s StreamData → L/s for CSTR)
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: StreamPortIO auto-propagation
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_stream_propagation.py::test_auto_propagation -v
    Expected: Test passes, outlet stream automatically applied to downstream inlet
    Evidence: .sisyphus/evidence/task-9-auto-propagation.txt

  Scenario: Multi-outlet routing
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_stream_propagation.py::test_multi_outlet_routing -v
    Expected: Test passes, flash vapor and liquid go to correct downstream units
    Evidence: .sisyphus/evidence/task-9-multi-outlet.txt
  ```

  **Commit**: YES | Message: `feat(coupling): upgrade boundary propagation to use StreamPortIO protocol` | Files: `src/modular_simulation/connection/thermo_coupling.py`, `tests/unit_process/test_stream_propagation.py`

---

### Wave 3 — Flowsheet Builder

- [x] 10. Flowsheet Builder Core

  **What to do**:
  Create `src/modular_simulation/flowsheet/flowsheet.py`:

  **`Flowsheet` class**:
  ```python
  class Flowsheet:
      def __init__(self, context: SimulationRuntimeContext, dt: float = 0.1):
          """Initialize with thermo context and macro timestep."""
  
      def add_unit(self, unit_id: str, unit: ProcessModel) -> None:
          """Register a unit process. Auto-creates System/Subsystem, injects PropertyPackage."""
  
      def add_feed(self, feed_id: str, stream: StreamData) -> None:
          """Register a feed stream boundary condition."""
      
      def add_feed_from_values(self, feed_id: str, *, T: float, P: float, z: tuple[float,...], flow: float) -> None:
          """Convenience: create StreamData from values and register as feed."""
  
      def connect(self, source: str, target: str) -> None:
          """Connect source to target. Format: 'unit_id.port_name' or 'unit_id' (auto-infer for SINGLE_IO).
          Examples:
            connect('heater', 'cstr')                    # SINGLE_IO auto-infer
            connect('flash.vapor_outlet', 'column')      # explicit port
            connect('feed_1', 'heater')                   # feed to unit
          """
      
      def chain(self, *unit_ids: str) -> None:
          """Connect units in sequence. Only works for SINGLE_IO units.
          chain('feed', 'heater', 'cstr', 'flash') is equivalent to:
            connect('feed', 'heater')
            connect('heater', 'cstr')
            connect('cstr', 'flash')
          """
      
      def compile(self) -> ConnectedPlantOrchestrator:
          """Compile the flowsheet into a ConnectedPlantOrchestrator.
          Steps:
          1. Create ConnectionNetwork from registered units and connections
          2. Create Subsystems via create_subsystem_for_unit() for each unit
          3. Assign HydraulicElements from units to connection lines
          4. Handle asymmetric ports (1→2 units)
          5. Compile network (hydraulic graph, transport, etc.)
          6. Create ConnectionRuntimeOrchestrator with context
          7. Return ConnectedPlantOrchestrator
          """
      
      def run(self, steps: int, dt: float | None = None) -> FlowsheetResults:
          """Compile (if needed) and run simulation for N steps.
          Returns structured FlowsheetResults with per-unit stream histories.
          """
      
      def get_unit(self, unit_id: str) -> ProcessModel:
          """Access unit for sensor/controller installation before run()."""
      
      def get_system(self, unit_id: str) -> System:
          """Access System wrapper for advanced sensor/controller configuration."""
  ```

  **Port inference rules**:
  - If unit has exactly 1 outlet and target has exactly 1 inlet: auto-connect
  - If source string contains '.': split into unit_id.port_name
  - If ambiguous (multiple ports): raise error listing available ports

  **Hydraulic element assignment**:
  - For each connection line, call `source_unit.to_hydraulic_element(source_port)` to get the element
  - If a unit is missing `to_hydraulic_element`, `Flowsheet.compile()` must fail with a clear error

  **Must NOT do**: Do NOT create a new orchestrator class. Do NOT bypass ConnectionNetwork. Do NOT implement recycle/tear-stream convergence (future work).

  **Recommended Agent Profile**:
  - Category: `deep` — Core builder integrating all previous layers
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 13 | Blocked By: 6, 7, 8, 9

  **References**:
  - All Wave 1 and Wave 2 outputs
  - Pattern: `src/modular_simulation/connection/network.py` — ConnectionNetwork API
  - Pattern: `src/modular_simulation/connection/connected_plant_orchestrator.py` — ConnectedPlantOrchestrator
  - Pattern: `src/modular_simulation/connection/runtime.py` — ConnectionRuntimeOrchestrator
  - Pattern: `src/modular_simulation/connection/unit_process_wiring.py` (Task 8) — create_subsystem_for_unit

  **Acceptance Criteria**:
  - [ ] `Flowsheet(ctx).add_unit("heater", HeaterCooler(...))` succeeds
  - [ ] `flowsheet.connect("heater", "cstr")` auto-infers SINGLE_IO ports
  - [ ] `flowsheet.connect("flash.vapor_outlet", "column")` explicit port works
  - [ ] `flowsheet.chain("feed", "heater", "cstr")` creates 2 connections
  - [ ] `flowsheet.compile()` returns valid ConnectedPlantOrchestrator
  - [ ] `flowsheet.run(steps=10)` produces results with real hydraulic solving
  - [ ] `flowsheet.get_system("heater")` returns System with sensor support
  - [ ] Port inference error lists available ports
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Simple flowsheet build and run
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_flowsheet_builder.py::test_simple_build_and_run -v
    Expected: Test passes, flowsheet compiles and runs with real hydraulic solving
    Evidence: .sisyphus/evidence/task-10-flowsheet-build.txt

  Scenario: Port inference error
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.flowsheet import Flowsheet
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
    from modular_simulation.unit_processes import FlashDrum
    ctx = SimulationRuntimeContext.create(['water','ethanol'])
    fs = Flowsheet(context=ctx)
    fs.add_unit('flash', FlashDrum(n_species=2, thermal_mode='isothermal'))
    try: fs.connect('flash', 'something')
    except ValueError as e: print(f'Error: {e}')
    "
    Expected: Error message lists vapor_outlet and liquid_outlet as available ports
    Evidence: .sisyphus/evidence/task-10-port-inference.txt
  ```

  **Commit**: YES | Message: `feat(flowsheet): add Flowsheet builder class with auto-wiring and real hydraulic integration` | Files: `src/modular_simulation/flowsheet/__init__.py`, `src/modular_simulation/flowsheet/flowsheet.py`, `tests/unit_process/test_flowsheet_builder.py`

---

- [x] 11. Flowsheet Compile-Time Validation

  **What to do**:
  Add validation to `Flowsheet.compile()` that catches errors early with clear diagnostics:

  - **Unbound mandatory inlets**: Every unit's mandatory inlet must be connected to a feed or upstream unit
  - **Ambiguous port inference**: When `connect("unit_a", "unit_b")` is called but unit_a has multiple outlets, raise error listing ports
  - **Species mismatch**: If upstream unit's outlet species don't cover downstream unit's inlet species
  - **Dangling outlets**: Warn (not error) if outlet is not connected to anything
  - **Topology validation**: Check for disconnected subgraphs, validate DAG structure (warn on cycles — those are recycles)
  - **Hydraulic feasibility**: Check that at least one pressure boundary (feed) exists

  **Must NOT do**: Do NOT implement recycle convergence. Do NOT block cycles entirely (just warn). Do NOT validate thermodynamic feasibility (that's runtime).

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Validation logic, no complex algorithms
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 13 | Blocked By: 10

  **References**:
  - Pattern: `src/modular_simulation/flowsheet/flowsheet.py` (Task 10) — Flowsheet.compile()
  - Pattern: `src/modular_simulation/connection/network.py` — Network validation

  **Acceptance Criteria**:
  - [ ] Unbound inlet raises error listing which unit/port is unconnected
  - [ ] Ambiguous port inference raises error listing available ports
  - [ ] Species mismatch raises error with specific species names
  - [ ] Dangling outlet produces warning (not error)
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Unbound inlet detection
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_flowsheet_validation.py::test_unbound_inlet -v
    Expected: Test passes, clear error for unconnected inlet
    Evidence: .sisyphus/evidence/task-11-unbound-inlet.txt

  Scenario: Ambiguous port error
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_flowsheet_validation.py::test_ambiguous_port -v
    Expected: Test passes, error lists available port names
    Evidence: .sisyphus/evidence/task-11-ambiguous-port.txt
  ```

  **Commit**: YES | Message: `feat(flowsheet): add compile-time validation with clear diagnostics` | Files: `src/modular_simulation/flowsheet/flowsheet.py`, `tests/unit_process/test_flowsheet_validation.py`

---

- [x] 12. Flowsheet Results API

  **What to do**:
  Create structured results from `Flowsheet.run()`:

  **`FlowsheetResults` class**:
  ```python
  class FlowsheetResults:
      time_points: NDArray[float]       # time array
      units: dict[str, UnitResult]      # per-unit results
      streams: dict[str, StreamHistory] # per-connection-line stream history
      
      def get_unit(self, unit_id: str) -> UnitResult
      def get_stream(self, source: str, target: str) -> StreamHistory
      def summary(self) -> str  # text summary of final state
  
  class UnitResult:
      unit_id: str
      outlet_streams: dict[str, StreamData]  # final outlet streams
      state_history: dict[str, NDArray]       # all states over time
      
  class StreamHistory:
      flow_rate: NDArray[float]
      temperature: NDArray[float]
      pressure: NDArray[float]
      composition: NDArray[float, float]  # (n_timesteps, n_species)
  ```

  - Results collected during run loop via Subsystem publication map
  - Final streams via `get_outlet_stream()` on each unit
  - State history from System.history if recording enabled

  **Must NOT do**: Do NOT add plotting. Do NOT add file export. Do NOT store raw solver internals.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Data structure + collection logic
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 13 | Blocked By: 10

  **References**:
  - Pattern: `src/modular_simulation/framework/system.py` — System.history for state recording
  - Pattern: `src/modular_simulation/thermodynamics/stream.py` (Task 1) — StreamData

  **Acceptance Criteria**:
  - [ ] `results.get_unit("heater").outlet_streams["outlet"]` returns final outlet StreamData
  - [ ] `results.units["cstr"].state_history["temperature"]` returns NDArray of T over time
  - [ ] `results.summary()` returns readable text
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Results access
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_flowsheet_results.py::test_results_access -v
    Expected: Test passes, all result accessors work
    Evidence: .sisyphus/evidence/task-12-results.txt
  ```

  **Commit**: YES | Message: `feat(flowsheet): add FlowsheetResults structured output API` | Files: `src/modular_simulation/flowsheet/results.py`, `tests/unit_process/test_flowsheet_results.py`

---

### Wave 4 — Demo + Final Verification

- [x] 13. Rewrite Flowsheet Demo

  **What to do**:
  Rewrite `examples/unit_process_flowsheet/flowsheet_demo.py` using the Flowsheet builder API. Target: 50-80 lines of clean, readable code.

  The demo should:
  1. Create SimulationRuntimeContext
  2. Create Flowsheet with context
  3. Define reactions (user domain logic — stays)
  4. Add units with parameters
  5. Add feed stream
  6. Connect units (chain + explicit for multi-outlet)
  7. Install at least one sensor and one controller to demonstrate capability
  8. Run simulation
  9. Print results using FlowsheetResults API

  Also update the README.md in the same directory.

  **Must NOT do**: Do NOT add plotting code. Do NOT add argparse/CLI. Keep it a simple script.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Rewrite using established API
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: F1-F4 | Blocked By: 10, 11, 12

  **References**:
  - File: `examples/unit_process_flowsheet/flowsheet_demo.py` — Current 583-line demo to replace
  - All Flowsheet builder API from Tasks 10-12

  **Acceptance Criteria**:
  - [ ] Demo file is 50-80 lines
  - [ ] `uv run python examples/unit_process_flowsheet/flowsheet_demo.py` runs without error
  - [ ] Output shows mass/energy balance results
  - [ ] Demo includes sensor installation to prove full System support
  - [ ] All tests pass

  **QA Scenarios**:
  ```
  Scenario: Demo runs successfully
    Tool: Bash
    Steps: uv run python examples/unit_process_flowsheet/flowsheet_demo.py 2>&1 | tail -20
    Expected: Output shows simulation results with no errors
    Evidence: .sisyphus/evidence/task-13-demo-run.txt

  Scenario: Demo line count
    Tool: Bash
    Steps: wc -l examples/unit_process_flowsheet/flowsheet_demo.py
    Expected: Line count between 50 and 80
    Evidence: .sisyphus/evidence/task-13-line-count.txt
  ```

  **Commit**: YES | Message: `refactor(examples): rewrite flowsheet demo using Flowsheet builder API (583→~80 lines)` | Files: `examples/unit_process_flowsheet/flowsheet_demo.py`, `examples/unit_process_flowsheet/README.md`

---

- [x] 14. Integration Test — Multi-Unit Flowsheet with Sensors/Controllers

  **What to do**:
  Create a comprehensive integration test that validates the full pipeline:

  - Build a 4+ unit flowsheet (e.g., Feed → HeaterCooler → CSTR → FlashDrum → with flash vapor and liquid going to separate destinations)
  - Install at least 1 sensor reading a unit's outlet temperature
  - Install at least 1 controller (e.g., PID controlling heater duty based on CSTR temperature)
  - Run for enough steps to see dynamic behavior
  - Validate:
    - Real hydraulic solver ran (not bypass)
    - Mass balance closes across all units
    - Sensor readings match direct state access
    - Controller output affects unit behavior
    - All streams have valid thermodynamic properties

  **Must NOT do**: Do NOT test edge cases (that's Task 11). Focus on happy-path integration.

  **Recommended Agent Profile**:
  - Category: `deep` — Complex integration with multiple subsystems
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: F1-F4 | Blocked By: 10

  **References**:
  - All previous tasks
  - Pattern: `examples/connection_layer/two_tank_reaction_comparison.py` — Existing integration pattern

  **Acceptance Criteria**:
  - [ ] 4+ unit flowsheet compiles and runs for 50+ steps
  - [ ] Mass balance error < 0.1% at each connection
  - [ ] Sensor readings match direct state access within floating point tolerance
  - [ ] Controller output changes unit behavior (heater duty varies)
  - [ ] No fake hydraulic/transport steps used (real compiled hydraulic graph)

  **QA Scenarios**:
  ```
  Scenario: Full integration test
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_flowsheet_integration.py -v
    Expected: All integration tests pass
    Evidence: .sisyphus/evidence/task-14-integration.txt
  ```

  **Commit**: YES | Message: `test(flowsheet): add comprehensive integration test with sensors and controllers` | Files: `tests/unit_process/test_flowsheet_integration.py`

---

- [x] 15. Update/Fix Broken Existing Tests

  **What to do**:
  Since breaking changes are allowed, some existing tests may fail after the Wave 1-3 changes. This task:
  1. Run full test suite: `uv run python -m pytest tests/ -v`
  2. Identify all failures caused by the new changes
  3. Fix tests to work with the new API (update imports, use new methods, etc.)
  4. If a test tested boilerplate patterns that are now unnecessary, remove or replace it
  5. Ensure the existing two_tank and connection layer examples still work (or update them to use new API)

  **Must NOT do**: Do NOT silently delete tests. Document why each change is made. Do NOT change core framework behavior to make tests pass.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Test maintenance
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: F1-F4 | Blocked By: 2, 3, 4, 5

  **References**:
  - Dir: `tests/` — All test files
  - Dir: `examples/` — Example files that may need updating

  **Acceptance Criteria**:
  - [ ] `uv run python -m pytest tests/ -q` all pass
  - [ ] No tests silently deleted without replacement
  - [ ] All examples run without error

  **QA Scenarios**:
  ```
  Scenario: Full regression suite
    Tool: Bash
    Steps: uv run python -m pytest tests/ -q
    Expected: All tests pass
    Evidence: .sisyphus/evidence/task-15-regression.txt
  ```

  **Commit**: YES | Message: `fix(tests): update tests for new StreamPortIO and Flowsheet builder API` | Files: various test files

---

## Final Verification Wave (4 parallel agents, ALL must APPROVE)

- [x] F1. Plan Compliance Audit — oracle
  Verify all plan objectives met: StreamPortIO on 12 units, real hydraulic solving, Flowsheet builder, sensor/controller support, demo rewrite.

- [x] F2. Code Quality Review — unspecified-high
  Type checking, linting, code style consistency, docstrings on public API.

- [x] F3. Real Manual QA — unspecified-high
  Run flowsheet demo end-to-end, verify mass/energy balances, verify sensor/controller functionality, verify hydraulic solver convergence.

- [x] F4. Scope Fidelity Check — deep
  Verify no scope creep (no new unit processes, no UI, no recycle convergence). Verify no fake hydraulic bypass. Verify all units use real System wrapping.

## Commit Strategy
- One commit per task (15 commits + test fixes)
- Each commit should pass full test suite independently
- Final squash into feature branch optional

## Success Criteria
1. All 12 unit processes have `apply_inlet()`/`get_outlet_stream()` methods
2. All unit processes provide `HydraulicElement` for real pressure-driven flow
3. `Flowsheet` builder automates System→Subsystem→Network→Orchestrator pipeline
4. Demo file is 50-80 lines (was 583)
5. Full sensor/controller support on all unit processes
6. No fake hydraulic/transport bypass anywhere
7. All tests pass (existing + new)
8. Mass/energy balances close to < 0.1% in integration test
