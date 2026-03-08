# Pre-Built Unit Process Library

## TL;DR
> **Summary**: Add a complete thermodynamic property system (via `thermo`/`chemicals` libraries), pluggable kinetics protocol, automatic material/energy balance coupling, and 11 pre-built chainable unit processes to the ModularSimulator. This transforms the simulator from "build everything from scratch" to "compose process flowsheets from a library."
> **Deliverables**: Species registry, thermo adapter, kinetics protocol, auto-coupling runtime, 11 unit process models, comprehensive test suite
> **Effort**: XL
> **Parallel**: YES - 6 waves
> **Critical Path**: Layer 0 (Species/Stream) → Layer 1 (Thermo) → Layer 2 (Kinetics) → Layer 3 (Auto-Coupling) → Layer 4 (Unit Processes) → Final Verification

## Context

### Original Request
Build a library of pre-built unit processes with compatible chemistry that can be exposed as chainable units in a sandbox fashion. Must-haves include distillation columns (shortcut, not rigorous), flash tanks, pumps, heat exchangers, CSTRs, fluidized bed reactors, etc. Key concerns: how to substitute rate laws/kinetics into reactors, and how to implement equation of state for flash calculations.

### Interview Summary
- **Thermo engine**: Caleb Bell's `thermo` + `chemicals` libraries (MIT, pure Python, PR/SRK/NRTL/UNIFAC, flash, 70k+ species)
- **Kinetics**: Callable protocol `rate(concentrations, temperature) -> rates` with pre-built Arrhenius/PowerLaw
- **Distillation**: Shortcut only (Fenske-Underwood-Gilliland algebraic method)
- **Species**: All 70k+ available via `chemicals` lookup by common name/CAS. Runtime-subsetted to only active species per simulation via canonical `ActiveSpeciesRegistry`
- **Scope**: Full MVP — Layers 0-4

### Metis Review (gaps addressed)
- **Static method constraint**: Runtime context (thermo, kinetics) passed via `SimulationRuntimeContext` injected at coupling layer, NOT stored in ProcessModel states. RHS remains numeric/stateless.
- **MaterialState backward compat**: Extended with optional keyword-only fields (species_ids, phase, enthalpy). Existing 3-arg constructor preserved.
- **Species ordering**: ONE canonical ordering per simulation. Per-unit masking via precompiled integer index arrays.
- **Junction species mismatch**: Mapping layer required before mixing (junction.py requires identical vector lengths).
- **Coupling precedence**: manual/auto/hybrid modes with explicit precedence validation.
- **Flash stability**: Step-local LRU cache + phase hints for ODE stability.
- **Layer gates**: Each layer must pass regression before next begins.
- **Thermo data gaps**: Preflight species availability with fail-fast diagnostics.

### Oracle Review (architecture decisions)
- `SimulationRuntimeContext` holds thermo + kinetics + species registry. Passed to coupling layer, NOT to ProcessModel static methods.
- `AlgebraicProcessModel` subclass for flash/splitter/distillation (zero differential states).
- `PropertyPackage` protocol wraps thermo's FlashVL/CEOSGas/CEOSLiquid.
- Step-local LRU cache keyed by `(species_set, T, P, z_rounded)`.
- Enthalpy-correct mixing at junctions using single reference state.

## Work Objectives

### Core Objective
Transform ModularSimulator from a framework where every unit process is hand-coded into one with a library of pre-built, thermodynamically-consistent, chainable unit processes backed by rigorous property calculations.

### Deliverables
1. `Species` class + `ActiveSpeciesRegistry` for species identification and subsetting
2. Enhanced `MaterialState` with species identity, phase, and enthalpy
3. `PropertyPackage` protocol + `PengRobinsonPackage` adapter wrapping `thermo`
4. `RateLaw` protocol + `ArrheniusRateLaw` + `PowerLawRateLaw` implementations
5. `SimulationRuntimeContext` binding thermo + kinetics + species for a simulation
6. `RuntimeBoundaryPropagationStep` + `RuntimeTransportAndMixingStep` implementations for auto-coupling
7. 11 pre-built unit processes: Mixer, Splitter, Heater/Cooler, Pump, Valve, Flash Drum, Conversion Reactor, CSTR, PFR, Shortcut Distillation, Heat Exchanger
8. Comprehensive test suite with analytical/reference validation per unit

### Definition of Done (verifiable conditions with commands)
```bash
# All existing tests still pass (backward compat)
uv run python -m pytest tests/ -q

# Layer 0: Species and stream enhancement
uv run python -m pytest tests/unit_process/test_layer0_species.py -q

# Layer 1: Thermo adapter
uv run python -m pytest tests/unit_process/test_layer1_thermo.py -q

# Layer 2: Kinetics protocol
uv run python -m pytest tests/unit_process/test_layer2_kinetics.py -q

# Layer 3: Auto-coupling
uv run python -m pytest tests/unit_process/test_layer3_coupling.py -q

# Layer 4: All unit processes
uv run python -m pytest tests/unit_process/test_layer4_units.py -q

# Type checking passes
uv run basedpyright src/modular_simulation/

# Linting passes
uv run ruff check src/modular_simulation/
```

### Must Have
- Backward compatibility with ALL existing ProcessModel subclasses and examples
- Species identified by common name or CAS number, resolved via `chemicals` library
- Peng-Robinson EOS as default property package
- Isothermal and adiabatic flash calculations via `thermo`
- Pluggable kinetics via callable protocol (not hardcoded in RHS)
- Automatic outlet→inlet material/energy balance propagation
- Enthalpy-correct mixing at junctions
- 11 unit processes with standard inlet/outlet port definitions
- Each unit validates against analytical solution or literature reference

### Must NOT Have (guardrails)
- NO rigorous distillation column (MESH equations) — shortcut only
- NO VLLE, electrolyte thermodynamics, or solid phase handling
- NO batch reactor, compressor/expander, Gibbs reactor (deferred to Phase 2)
- NO service objects stored in ProcessModel CONSTANT states (serialization/threading risk)
- NO breaking changes to existing `MaterialState` constructor `(pressure, temperature, mole_fractions)`
- NO new solver frameworks — reuse existing `solve_ivp` + Newton-Raphson hydraulic solver
- NO UI/frontend changes — this is pure backend/library
- NO string-based rate law expressions (callable protocol only)
- NO per-unit heterogeneous species sets — ONE canonical ordering per simulation with per-unit masking

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- **Test framework**: pytest (existing)
- **Test decision**: Tests-after (each task includes its tests)
- **QA policy**: Every task has agent-executed scenarios with analytical/reference validation
- **Evidence**: `.sisyphus/evidence/task-{N}-{slug}.{ext}`
- **Layer gates**: Each layer's tests must pass before next layer begins
- **Regression**: Full existing test suite must pass at every layer gate

## Execution Strategy

### Parallel Execution Waves

**Wave 1 — Foundation** (5 tasks, parallel):
- Task 1: Species registry + ActiveSpeciesRegistry [deep]
- Task 2: Enhanced MaterialState [deep]
- Task 3: Add `thermo`+`chemicals` dependencies [quick]
- Task 4: Existing test baseline snapshot [quick]
- Task 5: RateLaw protocol + pre-built implementations [deep]

**Wave 2 — Thermodynamic Engine** (3 tasks, parallel after Wave 1):
- Task 6: PropertyPackage protocol + PR adapter [deep]
- Task 7: SimulationRuntimeContext [deep]
- Task 8: AlgebraicProcessModel base class [deep]

**Wave 3 — Coupling Infrastructure** (3 tasks, parallel after Wave 2):
- Task 9: RuntimeBoundaryPropagationStep implementation [deep]
- Task 10: Enthalpy-correct junction mixing [deep]
- Task 11: Species mapping/projection at stream boundaries [deep]

**Wave 4 — Simple Unit Processes** (5 tasks, parallel after Wave 3):
- Task 12: Mixer + Splitter [unspecified-high]
- Task 13: Heater/Cooler [unspecified-high]
- Task 14: Pump + Valve [unspecified-high]
- Task 15: Conversion Reactor [unspecified-high]
- Task 16: Component Separator [unspecified-high]

**Wave 5 — Complex Unit Processes** (4 tasks, parallel after Wave 4):
- Task 17: Flash Drum [deep]
- Task 18: CSTR with pluggable kinetics [deep]
- Task 19: PFR with pluggable kinetics [deep]
- Task 20: Shortcut Distillation (FUG) [deep]

**Wave 6 — Integration** (2 tasks, parallel after Wave 5):
- Task 21: Heat Exchanger (NTU-ε) [deep]
- Task 22: Integration example — multi-unit flowsheet [unspecified-high]

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 (Species) | — | 2, 6, 7, 11 |
| 2 (MaterialState) | 1 | 6, 7, 9, 10, 11 |
| 3 (Dependencies) | — | 6 |
| 4 (Baseline) | — | all subsequent |
| 5 (Kinetics) | — | 7, 15, 18, 19 |
| 6 (PropertyPackage) | 1, 2, 3 | 7, 8, 17, 20, 21 |
| 7 (RuntimeContext) | 1, 2, 5, 6 | 9, 10, 11, 12-22 |
| 8 (AlgebraicPM) | 6 | 12, 13, 14, 16, 17, 20, 21 |
| 9 (BoundaryPropagation) | 2, 7 | 12-22 |
| 10 (EnthalpyMixing) | 2, 7 | 12-22 |
| 11 (SpeciesMapping) | 1, 2, 7 | 12-22 |
| 12 (Mixer/Splitter) | 8, 9, 10, 11 | 22 |
| 13 (Heater/Cooler) | 8, 9, 10, 11 | 22 |
| 14 (Pump/Valve) | 8, 9, 10, 11 | 22 |
| 15 (ConvReactor) | 5, 8, 9, 10, 11 | 22 |
| 16 (CompSeparator) | 8, 9, 10, 11 | 22 |
| 17 (Flash) | 6, 8, 9, 10, 11 | 22 |
| 18 (CSTR) | 5, 7, 8, 9, 10, 11 | 22 |
| 19 (PFR) | 5, 7, 8, 9, 10, 11 | 22 |
| 20 (Distillation) | 6, 8, 9, 10, 11 | 22 |
| 21 (HeatExchanger) | 6, 8, 9, 10, 11 | 22 |
| 22 (Integration) | 12-21 | F1-F4 |

### Agent Dispatch Summary

| Wave | Tasks | Categories |
|------|-------|------------|
| 1 | 5 | 3× deep, 2× quick |
| 2 | 3 | 3× deep |
| 3 | 3 | 3× deep |
| 4 | 5 | 5× unspecified-high |
| 5 | 4 | 4× deep |
| 6 | 2 | 1× deep, 1× unspecified-high |
| Final | 4 | 1× oracle, 2× unspecified-high, 1× deep |

## TODOs

### Wave 1 — Foundation

- [x] 1. Species Registry and ActiveSpeciesRegistry

  **What to do**:
  Create `src/modular_simulation/thermodynamics/species.py`:
  - `Species` frozen dataclass: `cas: str`, `name: str`, `formula: str`, `mw: float`, `tc: float`, `pc: float`, `omega: float`. Constructor accepts common name or CAS, resolves via `chemicals.search_chemical()` and `chemicals.Tc()`, `chemicals.Pc()`, `chemicals.omega()`, `chemicals.MW()`.
  - `resolve_species(identifier: str) -> Species`: Factory function. Accepts common name, CAS, formula. Caches results (functools.lru_cache).
  - `ActiveSpeciesRegistry` frozen class: `species: tuple[Species, ...]` (canonical ordered tuple for this simulation). Properties: `n_species: int`, `cas_list: tuple[str,...]`, `name_list: tuple[str,...]`, `mw_array: NDArray`. Methods: `index_of(species_or_name: str) -> int`, `contains(name: str) -> bool`, `subset_indices(sub_registry: ActiveSpeciesRegistry) -> NDArray[int]` (maps indices from sub to self), `project_fractions(global_fractions: NDArray, sub_registry: ActiveSpeciesRegistry) -> NDArray`.
  - `SimulationSpeciesContext`: Holds `ActiveSpeciesRegistry` + precompiled index arrays for all registered subsystems. Methods: `register_subsystem(id: str, local_species: list[str])`, `get_projection(subsystem_id: str) -> SpeciesProjection`.
  - `SpeciesProjection`: `global_to_local: NDArray[int]`, `local_to_global: NDArray[int]`, `n_local: int`, `n_global: int`. Methods: `to_local(global_fractions)`, `to_global(local_fractions)`.

  **Must NOT do**: Do NOT create an enum of all 70k species. Do NOT hardcode any species. Do NOT import `thermo` (only `chemicals`).

  **Recommended Agent Profile**:
  - Category: `deep` — Complex data model with indexing logic
  - Skills: [] — No special skills needed
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2, 6, 7, 11 | Blocked By: —

  **References**:
  - Pattern: `src/modular_simulation/connection/state.py` — MaterialState for Pydantic model patterns
  - Pattern: `src/modular_simulation/connection/material_models.py` — Protocol + factory pattern
  - API: `chemicals.search_chemical('ethanol')` → ChemicalMetadata(CAS, MW, formula, name, synonyms)
  - API: `chemicals.CAS_from_any('water')` → '7732-18-5'
  - API: `chemicals.Tc('7732-18-5')`, `chemicals.Pc()`, `chemicals.omega()`, `chemicals.MW()` for pure component properties
  - External: https://chemicals.readthedocs.io/

  **Acceptance Criteria**:
  - [ ] `resolve_species('water')` returns Species(cas='7732-18-5', name='water', mw≈18.015)
  - [ ] `resolve_species('7732-18-5')` returns same Species as `resolve_species('water')`
  - [ ] `ActiveSpeciesRegistry.from_names(['water', 'ethanol', 'methane'])` has n_species==3
  - [ ] `registry.index_of('water')` returns consistent integer index
  - [ ] `SpeciesProjection.to_local()` correctly subsets a global fractions array
  - [ ] `SpeciesProjection.to_global()` correctly expands a local fractions array (zeros for missing species)
  - [ ] Invalid species name raises clear error with suggestions
  - [ ] All existing tests pass: `uv run python -m pytest tests/ -q`

  **QA Scenarios**:
  ```
  Scenario: Species round-trip resolution
    Tool: Bash
    Steps: uv run python -c "from modular_simulation.thermodynamics.species import resolve_species; s=resolve_species('ethanol'); print(s.cas, s.name, round(s.mw,2))"
    Expected: stdout contains "64-17-5" and "ethanol" and "46.07"
    Evidence: .sisyphus/evidence/task-1-species-resolve.txt

  Scenario: Species projection correctness
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.thermodynamics.species import ActiveSpeciesRegistry
    import numpy as np
    global_reg = ActiveSpeciesRegistry.from_names(['water','ethanol','methane'])
    local_reg = ActiveSpeciesRegistry.from_names(['ethanol','methane'])
    proj = global_reg.get_projection_for(local_reg)
    local_z = np.array([0.6, 0.4])
    global_z = proj.to_global(local_z)
    print(list(global_z))
    "
    Expected: stdout is "[0.0, 0.6, 0.4]" (water=0, ethanol=0.6, methane=0.4)
    Evidence: .sisyphus/evidence/task-1-species-projection.txt

  Scenario: Invalid species fails clearly
    Tool: Bash
    Steps: uv run python -c "from modular_simulation.thermodynamics.species import resolve_species; resolve_species('notachemical')" 2>&1 | head -5
    Expected: stderr contains error message (not a silent failure or KeyError)
    Evidence: .sisyphus/evidence/task-1-species-error.txt
  ```

  **Commit**: YES | Message: `feat(thermo): add Species registry and ActiveSpeciesRegistry with projection` | Files: `src/modular_simulation/thermodynamics/__init__.py`, `src/modular_simulation/thermodynamics/species.py`, `tests/unit_process/test_layer0_species.py`

---

- [x] 2. Enhanced MaterialState

  **What to do**:
  Extend `MaterialState` in `src/modular_simulation/connection/state.py`:
  - Add optional keyword-only fields: `species_ids: tuple[str, ...] | None = None` (CAS numbers in same order as mole_fractions), `phase: str | None = None` ("vapor", "liquid", "two-phase", or None), `enthalpy_molar: float | None = None` (J/mol), `entropy_molar: float | None = None` (J/mol/K)
  - Preserve existing `MaterialState(pressure=..., temperature=..., mole_fractions=(...))` constructor
  - Add validator: if `species_ids` provided, `len(species_ids) == len(mole_fractions)`
  - Add `has_thermo_metadata` property: returns True if species_ids is not None
  - Extend `PortCondition` similarly: add optional `species_ids` field
  - Add `MaterialState.with_thermo(species_ids, phase, enthalpy_molar, entropy_molar)` factory that copies existing fields and adds thermo metadata
  - Add backward-compat `from_legacy(pressure, temperature, mole_fractions)` classmethod
  - Update `__eq__` and `__hash__` to include new fields when present
  - Run `lsp_find_references` on MaterialState to identify ALL existing call sites and verify none break

  **Must NOT do**: Do NOT change existing constructor signature. Do NOT make species_ids required. Do NOT import thermo or chemicals. Do NOT change existing serialization format (add new fields as optional in schema).

  **Recommended Agent Profile**:
  - Category: `deep` — Touches core data model with backward compat constraint
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6, 7, 9, 10, 11 | Blocked By: 1 (needs Species for species_ids type)

  **References**:
  - Pattern: `src/modular_simulation/connection/state.py` — Current MaterialState and PortCondition definitions
  - Pattern: `src/modular_simulation/connection/junction.py:46` — mix_junction_state requires identical mole_fraction lengths
  - Pattern: `src/modular_simulation/connection/transport.py` — LagTransportState uses composition tuple
  - Tool: Run `lsp_find_references` on MaterialState at state.py:11 to map all call sites

  **Acceptance Criteria**:
  - [ ] `MaterialState(pressure=101325, temperature=298.15, mole_fractions=(0.5, 0.5))` still works (no species_ids)
  - [ ] `MaterialState(pressure=101325, temperature=298.15, mole_fractions=(0.5, 0.5), species_ids=('7732-18-5', '64-17-5'))` works
  - [ ] species_ids length mismatch with mole_fractions raises ValidationError
  - [ ] `has_thermo_metadata` returns correct bool
  - [ ] All existing tests pass: `uv run python -m pytest tests/ -q`
  - [ ] `uv run basedpyright src/modular_simulation/connection/state.py` passes

  **QA Scenarios**:
  ```
  Scenario: Legacy constructor backward compat
    Tool: Bash
    Steps: uv run python -c "from modular_simulation.connection.state import MaterialState; s=MaterialState(pressure=101325.0, temperature=298.15, mole_fractions=(0.8,0.2)); print(len(s.mole_fractions), round(sum(s.mole_fractions),6), s.species_ids)"
    Expected: stdout is "2 1.0 None"
    Evidence: .sisyphus/evidence/task-2-legacy-compat.txt

  Scenario: Enhanced constructor with thermo metadata
    Tool: Bash
    Steps: uv run python -c "from modular_simulation.connection.state import MaterialState; s=MaterialState(pressure=101325.0, temperature=298.15, mole_fractions=(0.5,0.5), species_ids=('7732-18-5','64-17-5'), phase='liquid', enthalpy_molar=-285830.0); print(s.has_thermo_metadata, s.phase)"
    Expected: stdout is "True liquid"
    Evidence: .sisyphus/evidence/task-2-enhanced-state.txt

  Scenario: Mismatched lengths fail
    Tool: Bash
    Steps: uv run python -c "from modular_simulation.connection.state import MaterialState; MaterialState(pressure=101325, temperature=298.15, mole_fractions=(0.5,0.5), species_ids=('7732-18-5',))" 2>&1 | head -5
    Expected: stderr contains "ValidationError" or "length" or "mismatch"
    Evidence: .sisyphus/evidence/task-2-validation-error.txt
  ```

  **Commit**: YES | Message: `feat(state): extend MaterialState with optional species_ids, phase, enthalpy` | Files: `src/modular_simulation/connection/state.py`, `tests/unit_process/test_layer0_material_state.py`

---

- [x] 3. Add thermo + chemicals Dependencies

  **What to do**:
  - Add `thermo` and `chemicals` to `pyproject.toml` dependencies
  - Pin to compatible versions: `thermo>=0.3.0` and `chemicals>=1.2.0` (verify Python 3.13 compat first)
  - Run `uv sync` to install
  - Run smoke test: `uv run python -c "from thermo import ChemicalConstantsPackage, FlashVL; print('OK')"`
  - Run smoke test: `uv run python -c "from chemicals import search_chemical; print(search_chemical('water').CAS)"`
  - Verify ALL existing tests still pass

  **Must NOT do**: Do NOT add any other dependencies. Do NOT import thermo/chemicals from existing source files yet.

  **Recommended Agent Profile**:
  - Category: `quick` — Simple dependency addition
  - Skills: [] — No special skills
  - Omitted: all

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6 | Blocked By: —

  **References**:
  - File: `pyproject.toml:34` — Current dependencies list
  - External: https://pypi.org/project/thermo/ — Latest version
  - External: https://pypi.org/project/chemicals/ — Latest version

  **Acceptance Criteria**:
  - [ ] `uv run python -c "import thermo; print(thermo.__version__)"` succeeds
  - [ ] `uv run python -c "import chemicals; print(chemicals.__version__)"` succeeds
  - [ ] `uv run python -m pytest tests/ -q` all pass
  - [ ] `uv run basedpyright src/modular_simulation/` passes

  **QA Scenarios**:
  ```
  Scenario: thermo import smoke test
    Tool: Bash
    Steps: uv run python -c "from thermo import ChemicalConstantsPackage, FlashVL, CEOSGas, CEOSLiquid, PRMIX; print('all imports OK')"
    Expected: stdout is "all imports OK"
    Evidence: .sisyphus/evidence/task-3-thermo-import.txt

  Scenario: chemicals species lookup smoke test
    Tool: Bash
    Steps: uv run python -c "from chemicals import search_chemical, CAS_from_any; print(CAS_from_any('water'), search_chemical('ethanol').MW)"
    Expected: stdout contains "7732-18-5" and "46.0"
    Evidence: .sisyphus/evidence/task-3-chemicals-smoke.txt
  ```

  **Commit**: YES | Message: `build: add thermo and chemicals dependencies for thermodynamic calculations` | Files: `pyproject.toml`, `uv.lock`

---

- [x] 4. Existing Test Baseline Snapshot

  **What to do**:
  - Run full test suite: `uv run python -m pytest tests/ -v --tb=short`
  - Record output as baseline in `.sisyphus/evidence/baseline-test-results.txt`
  - Run type checker: `uv run basedpyright src/modular_simulation/`
  - Run linter: `uv run ruff check src/modular_simulation/`
  - Document count of passing tests, any existing failures, any type errors
  - This baseline is the regression gate for all subsequent tasks

  **Must NOT do**: Do NOT fix any existing test failures. Do NOT modify any source files.

  **Recommended Agent Profile**:
  - Category: `quick` — Just run commands and capture output
  - Skills: [] — No special skills
  - Omitted: all

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: all subsequent | Blocked By: —

  **References**:
  - Config: `pyproject.toml` — pytest configuration
  - Dir: `tests/` — Test directory

  **Acceptance Criteria**:
  - [ ] Baseline file exists at `.sisyphus/evidence/baseline-test-results.txt`
  - [ ] Test count and pass/fail status documented

  **QA Scenarios**:
  ```
  Scenario: Capture baseline
    Tool: Bash
    Steps: uv run python -m pytest tests/ -v --tb=short 2>&1 | tee .sisyphus/evidence/baseline-test-results.txt; echo "EXIT_CODE=$?"
    Expected: File created with test results
    Evidence: .sisyphus/evidence/baseline-test-results.txt
  ```

  **Commit**: NO

---

- [x] 5. RateLaw Protocol and Pre-built Implementations

  **What to do**:
  Create `src/modular_simulation/thermodynamics/kinetics.py`:
  - `RateLaw` Protocol:
    ```python
    class RateLaw(Protocol):
        def rate(self, concentrations: dict[str, float], temperature: float) -> dict[str, float]:
            """Return production rates (mol/L/s) for each species. Negative = consumed."""
            ...
    ```
  - `Reaction` dataclass: `name: str`, `stoichiometry: dict[str, float]` (species_name → coefficient, negative=reactant, positive=product), `rate_law: RateLaw`, `basis: Literal['concentration', 'partial_pressure'] = 'concentration'`
  - `ReactionSet`: Ordered collection of `Reaction` objects. Method: `net_rates(concentrations: dict[str, float], temperature: float) -> dict[str, float]` sums rates × stoichiometry across all reactions.
  - `ArrheniusRateLaw`: `pre_exponential: float`, `activation_energy: float` (J/mol), `gas_constant: float = 8.314`. `rate()` returns `{key_species: A * exp(-Ea/RT) * product(C_i^order_i)}` where orders are specified as `orders: dict[str, float]`.
  - `PowerLawRateLaw`: `k_ref: float`, `T_ref: float`, `orders: dict[str, float]`, optional `E_a: float` for temperature correction. `rate()` returns `{key_species: k * product(C_i^n_i)}`.
  - `EquilibriumConstantLaw`: `K_eq: Callable[[float], float]` (T → K_eq), `forward_rate_law: RateLaw`. Computes reverse rate from equilibrium.

  **Must NOT do**: Do NOT import thermo. Do NOT create string-based expression evaluation. Do NOT couple to ProcessModel.

  **Recommended Agent Profile**:
  - Category: `deep` — Protocol design with multiple implementations
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 7, 15, 18, 19 | Blocked By: —

  **References**:
  - Pattern: `src/modular_simulation/connection/material_models.py` — Protocol + implementations + factory pattern
  - Pattern: `src/modular_simulation/connection/hydraulic_element.py` — HydraulicElement Protocol with residuals/jacobian
  - Example: `examples/van_de_vusse_cstr/process_definition.py` — Hardcoded Arrhenius: k1=k10*exp(-E1/T)
  - Example: `examples/simple_irreversible_system/process_definition.py` — First-order: r = k * A * V
  - External: DWSIM IReaction interface pattern (stoichiometry + kinetic type + Arrhenius params)

  **Acceptance Criteria**:
  - [ ] `ArrheniusRateLaw` matches manual Arrhenius calculation to <1e-10 relative error
  - [ ] `PowerLawRateLaw` with known k, orders matches expected rate
  - [ ] `ReactionSet` correctly sums contributions from multiple reactions
  - [ ] `RateLaw` protocol accepts any callable with correct signature
  - [ ] All existing tests pass: `uv run python -m pytest tests/ -q`

  **QA Scenarios**:
  ```
  Scenario: Arrhenius rate law validation
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.thermodynamics.kinetics import ArrheniusRateLaw
    import math
    law = ArrheniusRateLaw(pre_exponential=1e10, activation_energy=80000, orders={'A': 1.0}, key_species='A')
    T = 350.0  # K
    conc = {'A': 1.5, 'B': 0.5}
    result = law.rate(conc, T)
    expected = 1e10 * math.exp(-80000/(8.314*350)) * 1.5
    print(f'rate={result[\"A\"]:.6e}, expected={expected:.6e}, match={abs(result[\"A\"]-expected)/expected < 1e-10}')
    "
    Expected: stdout contains "match=True"
    Evidence: .sisyphus/evidence/task-5-arrhenius.txt

  Scenario: Multi-reaction ReactionSet
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.thermodynamics.kinetics import PowerLawRateLaw, Reaction, ReactionSet
    r1 = Reaction(name='A->B', stoichiometry={'A': -1, 'B': 1}, rate_law=PowerLawRateLaw(k_ref=0.5, orders={'A': 1}, key_species='A'))
    r2 = Reaction(name='B->C', stoichiometry={'B': -1, 'C': 1}, rate_law=PowerLawRateLaw(k_ref=0.3, orders={'B': 1}, key_species='B'))
    rs = ReactionSet(reactions=[r1, r2])
    rates = rs.net_rates({'A': 2.0, 'B': 1.0, 'C': 0.0}, 300.0)
    print(f'A={rates[\"A\"]:.2f}, B={rates[\"B\"]:.2f}, C={rates[\"C\"]:.2f}')
    "
    Expected: stdout is "A=-1.00, B=0.70, C=0.30" (A consumed by r1, B produced by r1 minus consumed by r2, C produced by r2)
    Evidence: .sisyphus/evidence/task-5-reactionset.txt
  ```

  **Commit**: YES | Message: `feat(kinetics): add RateLaw protocol with Arrhenius, PowerLaw, and ReactionSet` | Files: `src/modular_simulation/thermodynamics/kinetics.py`, `tests/unit_process/test_layer2_kinetics.py`

---

### Wave 2 — Thermodynamic Engine

- [x] 6. PropertyPackage Protocol and Peng-Robinson Adapter

  **What to do**:
  Create `src/modular_simulation/thermodynamics/property_package.py`:
  - `FlashResult` dataclass: `temperature: float`, `pressure: float`, `vapor_fraction: float`, `phase: str` ("vapor"/"liquid"/"two-phase"), `liquid_composition: tuple[float,...] | None`, `vapor_composition: tuple[float,...] | None`, `enthalpy_molar: float` (J/mol), `entropy_molar: float` (J/mol/K), `liquid_density: float | None` (kg/m³), `vapor_density: float | None` (kg/m³), `K_values: tuple[float,...] | None`
  - `PropertyPackage` Protocol:
    ```python
    class PropertyPackage(Protocol):
        def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult: ...
        def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult: ...
        def flash_ps(self, P: float, S: float, z: tuple[float, ...]) -> FlashResult: ...
        def enthalpy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...
        def entropy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...
        def density(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...
        def heat_capacity_cp(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...
        def molecular_weight(self, z: tuple[float, ...]) -> float: ...
        @property
        def species_cas(self) -> tuple[str, ...]: ...
    ```
  - `PengRobinsonPackage` implementation:
    - Constructor: `__init__(self, species_ids: tuple[str, ...])` where species_ids are CAS numbers
    - Internally creates: `ChemicalConstantsPackage.from_IDs(species_ids)` → constants/correlations, `IPDB.get_ip_asymmetric_matrix('ChemSep PR', cas_list, 'kij')` → kijs, `CEOSGas(PRMIX, ...)` → gas, `CEOSLiquid(PRMIX, ...)` → liquid, `FlashVL(constants, correlations, gas=gas, liquid=liquid)` → flasher
    - `flash_tp()`: calls `self._flasher.flash(T=T, P=P, zs=list(z))`, wraps result in FlashResult
    - `flash_ph()`: calls `self._flasher.flash(P=P, H=H, zs=list(z))`
    - Other methods delegate to thermo's EquilibriumState properties
    - Step-local LRU cache: `@functools.lru_cache(maxsize=128)` on flash methods with rounded inputs (T to 0.01K, P to 1Pa, z to 6 decimals)
  - `create_property_package(species: ActiveSpeciesRegistry, model: str = 'PR') -> PropertyPackage` factory

  **Must NOT do**: Do NOT implement SRK/NRTL/UNIFAC yet (just PR). Do NOT handle 3-phase. Do NOT call thermo inside ProcessModel static methods.

  **Recommended Agent Profile**:
  - Category: `deep` — Core thermo adapter with caching
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7, 8, 17, 20, 21 | Blocked By: 1, 2, 3

  **References**:
  - API: `thermo.ChemicalConstantsPackage.from_IDs(['water', 'ethanol'])` → constants, correlations
  - API: `thermo.CEOSGas(PRMIX, eos_kwargs={Pcs, Tcs, omegas, kijs}, HeatCapacityGases=...)`
  - API: `thermo.FlashVL(constants, correlations, gas=gas, liquid=liquid).flash(T=..., P=..., zs=...)`
  - API: result.H(), result.S(), result.VF, result.liquid0.rho_mass(), result.gas.rho_mass()
  - Pattern: `src/modular_simulation/connection/material_models.py` — DensityModel Protocol + factory pattern
  - Pattern: `src/modular_simulation/thermodynamics/species.py` (Task 1) — ActiveSpeciesRegistry

  **Acceptance Criteria**:
  - [ ] `PengRobinsonPackage(['7732-18-5', '64-17-5']).flash_tp(T=350, P=101325, z=(0.5,0.5))` returns valid FlashResult
  - [ ] Flash result has physically valid VF ∈ [0,1], enthalpy is finite, density > 0
  - [ ] `flash_ph()` round-trips: flash_tp → get H → flash_ph with same H → same T (within 0.1K)
  - [ ] Cache hit on repeated call with same inputs (verify via cache_info)
  - [ ] Pure component flash: water at 373K, 101325Pa has VF≈1.0 (boiling point)
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Water-ethanol VLE flash
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.thermodynamics.property_package import PengRobinsonPackage
    pkg = PengRobinsonPackage(species_ids=('7732-18-5', '64-17-5'))
    result = pkg.flash_tp(T=350.0, P=101325.0, z=(0.5, 0.5))
    print(f'VF={result.vapor_fraction:.4f}, phase={result.phase}, H={result.enthalpy_molar:.0f}')
    print(f'y={[round(x,4) for x in result.vapor_composition]}')
    print(f'x={[round(x,4) for x in result.liquid_composition]}')
    "
    Expected: stdout contains VF between 0 and 1, finite H, compositions summing to ~1.0
    Evidence: .sisyphus/evidence/task-6-flash-tp.txt

  Scenario: Enthalpy round-trip (flash_tp → flash_ph)
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.thermodynamics.property_package import PengRobinsonPackage
    pkg = PengRobinsonPackage(species_ids=('7732-18-5', '64-17-5'))
    r1 = pkg.flash_tp(T=350.0, P=101325.0, z=(0.5, 0.5))
    r2 = pkg.flash_ph(P=101325.0, H=r1.enthalpy_molar, z=(0.5, 0.5))
    print(f'T1={r1.temperature:.2f}, T2={r2.temperature:.2f}, match={abs(r1.temperature - r2.temperature) < 0.1}')
    "
    Expected: stdout contains "match=True"
    Evidence: .sisyphus/evidence/task-6-enthalpy-roundtrip.txt

  Scenario: Cache effectiveness
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.thermodynamics.property_package import PengRobinsonPackage
    pkg = PengRobinsonPackage(species_ids=('7732-18-5', '64-17-5'))
    for _ in range(5): pkg.flash_tp(T=350.0, P=101325.0, z=(0.5, 0.5))
    info = pkg.flash_tp.cache_info() if hasattr(pkg.flash_tp, 'cache_info') else 'no cache'
    print(f'cache: {info}')
    "
    Expected: stdout shows hits > 0
    Evidence: .sisyphus/evidence/task-6-cache.txt
  ```

  **Commit**: YES | Message: `feat(thermo): add PropertyPackage protocol and PengRobinsonPackage adapter` | Files: `src/modular_simulation/thermodynamics/property_package.py`, `tests/unit_process/test_layer1_thermo.py`

---

- [x] 7. SimulationRuntimeContext

  **What to do**:
  Create `src/modular_simulation/thermodynamics/runtime_context.py`:
  - `SimulationRuntimeContext` dataclass:
    ```python
    @dataclass(frozen=True)
    class SimulationRuntimeContext:
        species_registry: ActiveSpeciesRegistry
        property_package: PropertyPackage
        species_context: SimulationSpeciesContext
        reaction_sets: Mapping[str, ReactionSet] = field(default_factory=dict)  # subsystem_id → reactions
    ```
  - Factory method: `SimulationRuntimeContext.create(species_names: list[str], eos_model: str = 'PR', reactions: dict[str, ReactionSet] | None = None) -> SimulationRuntimeContext`
  - Helper: `get_property_package() -> PropertyPackage`, `get_reactions(subsystem_id: str) -> ReactionSet | None`
  - Integration point: Add optional `runtime_context: SimulationRuntimeContext | None = None` parameter to `ConnectedPlantOrchestrator.__init__()` and `ConnectionRuntimeOrchestrator.__init__()`
  - Store on orchestrator, pass to coupling step implementations (Task 9-11)
  - Do NOT pass to ProcessModel static methods

  **Must NOT do**: Do NOT modify ProcessModel. Do NOT store context in ProcessModel states. Do NOT make context required (default None for backward compat).

  **Recommended Agent Profile**:
  - Category: `deep` — Integration with existing orchestrator
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9, 10, 11, 12-22 | Blocked By: 1, 2, 5, 6

  **References**:
  - Pattern: `src/modular_simulation/connection/connected_plant_orchestrator.py` — ConnectedPlantOrchestrator constructor and step()
  - Pattern: `src/modular_simulation/connection/runtime.py` — ConnectionRuntimeOrchestrator constructor
  - Pattern: `src/modular_simulation/thermodynamics/species.py` (Task 1) — ActiveSpeciesRegistry
  - Pattern: `src/modular_simulation/thermodynamics/property_package.py` (Task 6) — PropertyPackage
  - Pattern: `src/modular_simulation/thermodynamics/kinetics.py` (Task 5) — ReactionSet

  **Acceptance Criteria**:
  - [ ] `SimulationRuntimeContext.create(['water', 'ethanol'])` creates valid context with PR package
  - [ ] `ConnectedPlantOrchestrator(runtime_context=ctx)` accepts context without errors
  - [ ] `ConnectedPlantOrchestrator()` (no context) still works — backward compat
  - [ ] Context is accessible from coupling step implementations
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Create runtime context
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
    ctx = SimulationRuntimeContext.create(species_names=['water', 'ethanol', 'methane'])
    print(f'species={ctx.species_registry.n_species}, pkg_type={type(ctx.property_package).__name__}')
    "
    Expected: stdout is "species=3, pkg_type=PengRobinsonPackage"
    Evidence: .sisyphus/evidence/task-7-context-create.txt

  Scenario: Backward compat with no context
    Tool: Bash
    Steps: uv run python -m pytest tests/connection/ -q --tb=short
    Expected: All existing connection tests pass
    Evidence: .sisyphus/evidence/task-7-backward-compat.txt
  ```

  **Commit**: YES | Message: `feat(thermo): add SimulationRuntimeContext and wire to orchestrators` | Files: `src/modular_simulation/thermodynamics/runtime_context.py`, `src/modular_simulation/connection/connected_plant_orchestrator.py`, `src/modular_simulation/connection/runtime.py`, `tests/unit_process/test_layer1_runtime_context.py`

---

- [x] 8. AlgebraicProcessModel Base Class

  **What to do**:
  Create `src/modular_simulation/thermodynamics/algebraic_process_model.py`:
  - `AlgebraicProcessModel` extends `ProcessModel`:
    - Override `step(dt)` to skip ODE integration entirely — just call `calculate_algebraic_values()` and update algebraic states
    - Has ZERO differential states (enforce via validator)
    - `differential_rhs()` implementation returns empty array
    - Abstract method: `calculate_algebraic_values()` does the real work (flash calculation, energy balance, etc.)
    - All CONTROLLED states represent inlet conditions (set by coupling layer)
    - All ALGEBRAIC states represent outlet conditions (computed by the unit)
  - Standard port naming convention for unit processes:
    - Inlets: `inlet`, `inlet_1`, `inlet_2`, etc.
    - Outlets: `outlet`, `outlet_1`, `outlet_2`, etc.
    - Special: `energy_in`, `energy_out` for heat duty ports
  - `UnitProcessPorts` dataclass: `inlets: tuple[str, ...]`, `outlets: tuple[str, ...]`. Pre-defined constants: `SINGLE_IO = UnitProcessPorts(('inlet',), ('outlet',))`, `DUAL_INLET = UnitProcessPorts(('inlet_1','inlet_2'), ('outlet',))`, etc.

  **Must NOT do**: Do NOT implement any specific unit process here. Do NOT import thermo. Do NOT change ProcessModel base class.

  **Recommended Agent Profile**:
  - Category: `deep` — Framework extension with careful ProcessModel integration
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 12-21 | Blocked By: 6

  **References**:
  - Pattern: `src/modular_simulation/measurables/process_model.py` — ProcessModel base class, step(), attach_system(), StateMetadata, CategorizedStateView
  - Pattern: `src/modular_simulation/measurables/process_model.py:292` — calculate_algebraic_values static method signature
  - Pattern: `src/modular_simulation/measurables/process_model.py:322` — differential_rhs static method signature
  - Pattern: `src/modular_simulation/connection/domain_contracts.py` — UnitProcess with Port(port_id, direction)

  **Acceptance Criteria**:
  - [ ] `AlgebraicProcessModel` subclass with only ALGEBRAIC+CONTROLLED+CONSTANT states works
  - [ ] `step(dt)` computes algebraic values without calling solve_ivp
  - [ ] Validator rejects differential states in AlgebraicProcessModel subclass
  - [ ] UnitProcessPorts constants are importable and correct
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Algebraic model step
    Tool: Bash
    Steps: uv run python -c "
    from modular_simulation.thermodynamics.algebraic_process_model import AlgebraicProcessModel
    # Create a minimal test subclass inline
    print('AlgebraicProcessModel imported OK')
    "
    Expected: stdout contains "imported OK"
    Evidence: .sisyphus/evidence/task-8-algebraic-model.txt
  ```

  **Commit**: YES | Message: `feat(framework): add AlgebraicProcessModel base class and UnitProcessPorts` | Files: `src/modular_simulation/thermodynamics/algebraic_process_model.py`, `tests/unit_process/test_algebraic_process_model.py`

---

### Wave 3 — Coupling Infrastructure

- [x] 9. RuntimeBoundaryPropagationStep Implementation

  **What to do**:
  Create `src/modular_simulation/connection/thermo_coupling.py`:
  - `ThermoBoundaryPropagationStep` implementing `RuntimeBoundaryPropagationStep` protocol:
    - On each macro step: for each connection line, read source unit's outlet state → create `PortCondition` with full thermo metadata (species_ids, phase, enthalpy from PropertyPackage) → set on target unit's inlet
    - Uses `SimulationRuntimeContext.property_package` to compute enthalpy of outlet streams
    - Maps outlet ALGEBRAIC states (T, P, composition, flow) to `MaterialState` with species_ids
    - Sets inlet CONTROLLED states on downstream units from `PortCondition`
  - `ThermoBoundaryPropagationConfig`: `mode: Literal['auto', 'manual', 'hybrid']`, `auto_propagate_species: bool = True`, `auto_propagate_energy: bool = True`
  - Integration: Register as the boundary propagation step in `ConnectionRuntimeOrchestrator` when `SimulationRuntimeContext` is present
  - Fallback: If no runtime context, use existing no-op behavior (backward compat)

  **Must NOT do**: Do NOT modify ProcessModel. Do NOT break existing manual coupling patterns. Do NOT propagate inside ODE integration loops (coupling is macro-step only).

  **Recommended Agent Profile**:
  - Category: `deep` — Core coupling logic with complex state mapping
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 12-22 | Blocked By: 2, 7

  **References**:
  - Pattern: `src/modular_simulation/connection/runtime.py:1224` — Default no-op RuntimeBoundaryPropagationStep
  - Pattern: `src/modular_simulation/connection/runtime.py:1234` — Default no-op RuntimeTransportAndMixingStep
  - Pattern: `examples/connection_layer/two_tank_reaction_comparison.py` — Manual coupling pattern to replicate
  - Pattern: `src/modular_simulation/connection/state.py` — MaterialState, PortCondition
  - Pattern: `src/modular_simulation/connection/process_binding.py` — ProcessBinding.bind_inlets/bind_outlets

  **Acceptance Criteria**:
  - [ ] Two connected units with auto-propagation: outlet T/P/z of unit A correctly appears as inlet of unit B
  - [ ] Manual coupling mode still works when auto disabled
  - [ ] Hybrid mode: auto-propagated values can be overridden by manual hooks
  - [ ] Enthalpy is computed and propagated on MaterialState
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Auto-propagation between two units
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer3_coupling.py::test_auto_propagation_two_units -v
    Expected: Test passes, outlet state of unit A matches inlet state of unit B
    Evidence: .sisyphus/evidence/task-9-auto-propagation.txt

  Scenario: Backward compat (no context)
    Tool: Bash
    Steps: uv run python -m pytest tests/connection/ -q
    Expected: All existing connection tests pass
    Evidence: .sisyphus/evidence/task-9-backward-compat.txt
  ```

  **Commit**: YES | Message: `feat(coupling): add ThermoBoundaryPropagationStep for automatic material/energy propagation` | Files: `src/modular_simulation/connection/thermo_coupling.py`, `tests/unit_process/test_layer3_coupling.py`

---

- [x] 10. Enthalpy-Correct Junction Mixing

  **What to do**:
  Extend junction mixing in `src/modular_simulation/connection/junction.py`:
  - New function `mix_junction_state_with_enthalpy(incoming_states: list[PortCondition], property_package: PropertyPackage) -> JunctionMixingResult`:
    - Flow-weighted composition mixing (same as current)
    - Enthalpy-correct temperature: compute H_mix = Σ(F_i * H_i) / Σ(F_i), then flash_ph(P_mix, H_mix, z_mix) to get outlet T
    - This handles latent heat effects (mixing streams of different phases)
  - Keep existing `mix_junction_state()` unchanged (backward compat)
  - Wire new function into `ThermoBoundaryPropagationStep` when property_package available
  - Fallback to existing linear T mixing when no property_package

  **Must NOT do**: Do NOT modify existing `mix_junction_state()`. Do NOT require PropertyPackage for basic mixing.

  **Recommended Agent Profile**:
  - Category: `deep` — Thermodynamically rigorous mixing
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 12-22 | Blocked By: 2, 7

  **References**:
  - Pattern: `src/modular_simulation/connection/junction.py` — Existing mix_junction_state() with flow-weighted linear mixing
  - API: `PropertyPackage.flash_ph(P, H_mix, z_mix)` — Adiabatic mixing flash
  - Pattern: `src/modular_simulation/connection/state.py` — MaterialState with optional enthalpy_molar

  **Acceptance Criteria**:
  - [ ] Mixing two liquid streams gives correct mixed T via enthalpy balance
  - [ ] Mixing liquid + vapor streams correctly predicts two-phase result or intermediate T
  - [ ] Existing `mix_junction_state()` still works identically (no thermo)
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Enthalpy-correct mixing vs linear mixing
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer3_coupling.py::test_enthalpy_correct_mixing -v
    Expected: Test passes, enthalpy-mixed T differs from linear-mixed T when latent heat involved
    Evidence: .sisyphus/evidence/task-10-enthalpy-mixing.txt
  ```

  **Commit**: YES | Message: `feat(coupling): add enthalpy-correct junction mixing with PropertyPackage` | Files: `src/modular_simulation/connection/junction.py`, `tests/unit_process/test_layer3_coupling.py`

---

- [x] 11. Species Mapping at Stream Boundaries

  **What to do**:
  Add species projection logic to coupling infrastructure:
  - In `ThermoBoundaryPropagationStep`: when propagating from unit A (local species) to unit B (local species), use `SpeciesProjection` to map composition vectors
  - At junction mixing: align all incoming streams to junction's canonical species ordering before mixing
  - Validation: at compile time, verify that every connected pair of ports has compatible species (target species ⊆ source species, or source has zeros for missing target species)
  - Error handling: clear error message if species mismatch detected (e.g., "Unit B expects 'hydrogen' but Unit A's outlet doesn't contain it")

  **Must NOT do**: Do NOT allow implicit species reordering without explicit projection. Do NOT silently drop species.

  **Recommended Agent Profile**:
  - Category: `deep` — Species algebra with validation
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 12-22 | Blocked By: 1, 2, 7

  **References**:
  - Pattern: `src/modular_simulation/thermodynamics/species.py` (Task 1) — SpeciesProjection.to_local/to_global
  - Pattern: `src/modular_simulation/connection/thermo_coupling.py` (Task 9) — ThermoBoundaryPropagationStep
  - Pattern: `src/modular_simulation/connection/junction.py:46` — Current requirement for identical composition lengths

  **Acceptance Criteria**:
  - [ ] Propagation from 5-species unit to 3-species unit correctly projects composition
  - [ ] Missing species in target are dropped with zero check
  - [ ] Species appearing in target but not source raises compile-time error
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Species projection in propagation
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer3_coupling.py::test_species_projection_propagation -v
    Expected: Test passes, composition correctly projected between different species sets
    Evidence: .sisyphus/evidence/task-11-species-projection.txt
  ```

  **Commit**: YES | Message: `feat(coupling): add species mapping and projection at stream boundaries` | Files: `src/modular_simulation/connection/thermo_coupling.py`, `tests/unit_process/test_layer3_coupling.py`

---

### Wave 4 — Simple Unit Processes

- [x] 12. Mixer and Splitter

  **What to do**:
  Create `src/modular_simulation/unit_processes/mixer.py` and `splitter.py`:

  **Mixer** (AlgebraicProcessModel):
  - Ports: N inlets (`inlet_1`, `inlet_2`, ...), 1 outlet (`outlet`)
  - CONTROLLED states: inlet_flow_i, inlet_temperature_i, inlet_composition_i (for each inlet)
  - ALGEBRAIC states: outlet_flow, outlet_temperature, outlet_composition
  - CONSTANT: n_inlets, n_species
  - `calculate_algebraic_values()`: sum inlet flows → outlet_flow, flow-weighted composition → outlet_composition, enthalpy-correct T via PropertyPackage if available (else linear T mixing)
  - Pressure: minimum of inlet pressures (realistic assumption)

  **Splitter** (AlgebraicProcessModel):
  - Ports: 1 inlet (`inlet`), N outlets (`outlet_1`, `outlet_2`, ...)
  - CONTROLLED states: inlet_flow, inlet_temperature, inlet_composition, split_ratios (N-1 ratios, last computed as 1-sum)
  - ALGEBRAIC states: outlet_flow_i, outlet_temperature_i, outlet_composition_i
  - All outlets have SAME T, P, composition as inlet. Only flow differs.

  **Must NOT do**: Do NOT add pressure drop in mixer. Do NOT allow negative split ratios.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Two implementations following established patterns
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 22 | Blocked By: 8, 9, 10, 11

  **References**:
  - Pattern: `src/modular_simulation/thermodynamics/algebraic_process_model.py` (Task 8) — AlgebraicProcessModel base
  - Pattern: `src/modular_simulation/connection/junction.py` — Existing mixing logic
  - Pattern: `examples/simple_irreversible_system/process_definition.py` — ProcessModel state declaration pattern

  **Acceptance Criteria**:
  - [ ] Mixer: 2 streams of pure water at different T → correct mixed T and total flow
  - [ ] Mixer: 2 streams of different composition → correct flow-weighted composition
  - [ ] Splitter: 0.6/0.4 split → outlet flows = 60%/40% of inlet
  - [ ] Splitter: all outlets have same T, P, composition as inlet
  - [ ] Split ratios summing to >1.0 raises error

  **QA Scenarios**:
  ```
  Scenario: Mixer mass balance
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_mixer_splitter.py::test_mixer_mass_balance -v
    Expected: Test passes, total outlet flow equals sum of inlet flows
    Evidence: .sisyphus/evidence/task-12-mixer-balance.txt

  Scenario: Splitter conservation
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_mixer_splitter.py::test_splitter_conservation -v
    Expected: Test passes, sum of outlet flows equals inlet flow, compositions identical
    Evidence: .sisyphus/evidence/task-12-splitter-conservation.txt
  ```

  **Commit**: YES | Message: `feat(units): add Mixer and Splitter unit processes` | Files: `src/modular_simulation/unit_processes/__init__.py`, `src/modular_simulation/unit_processes/mixer.py`, `src/modular_simulation/unit_processes/splitter.py`, `tests/unit_process/test_layer4_mixer_splitter.py`

---

- [x] 13. Heater/Cooler

  **What to do**:
  Create `src/modular_simulation/unit_processes/heater_cooler.py`:
  - `HeaterCooler` (AlgebraicProcessModel):
  - Ports: 1 inlet, 1 outlet
  - Two modes:
    - **Duty mode**: CONTROLLED `duty` (W), compute outlet T via flash_ph(P, H_in + Q/F, z)
    - **Temperature mode**: CONTROLLED `outlet_temperature`, compute duty as Q = F * (H_out - H_in)
  - CONTROLLED states: inlet_flow, inlet_temperature, inlet_composition, pressure_drop (Pa, default 0), plus mode-specific (duty OR outlet_temperature)
  - ALGEBRAIC states: outlet_temperature (or duty), outlet_enthalpy
  - CONSTANT: mode ("duty" or "temperature"), n_species
  - Outlet pressure = inlet pressure - pressure_drop
  - Outlet composition = inlet composition (no reaction)
  - Uses PropertyPackage for enthalpy calculations

  **Must NOT do**: Do NOT add detailed heat transfer correlations. Do NOT handle phase change specially (PropertyPackage handles it via flash).

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Single unit with two modes
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 22 | Blocked By: 8, 9, 10, 11

  **References**:
  - Pattern: `src/modular_simulation/thermodynamics/algebraic_process_model.py` (Task 8)
  - API: `PropertyPackage.flash_tp()` for H_in, `PropertyPackage.flash_ph()` for T_out in duty mode
  - Pattern: `examples/van_de_vusse_cstr/calculation_definition.py` — HeatDutyCalculation pattern

  **Acceptance Criteria**:
  - [ ] Duty mode: 1000W heater on water stream → correct ΔT ≈ Q/(F*Cp)
  - [ ] Temperature mode: set T_out → correct Q computed
  - [ ] Energy balance: Q = F * (H_out - H_in) holds to <0.1% error
  - [ ] Zero duty → outlet = inlet exactly
  - [ ] Pressure drop applied correctly

  **QA Scenarios**:
  ```
  Scenario: Heater duty mode energy balance
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_heater_cooler.py::test_heater_duty_energy_balance -v
    Expected: Test passes, Q = F*(H_out - H_in) within tolerance
    Evidence: .sisyphus/evidence/task-13-heater-energy.txt

  Scenario: Cooler temperature mode
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_heater_cooler.py::test_cooler_temperature_mode -v
    Expected: Test passes, outlet T matches specified T, duty is negative
    Evidence: .sisyphus/evidence/task-13-cooler-temp.txt
  ```

  **Commit**: YES | Message: `feat(units): add HeaterCooler unit process with duty and temperature modes` | Files: `src/modular_simulation/unit_processes/heater_cooler.py`, `tests/unit_process/test_layer4_heater_cooler.py`

---

- [x] 14. Pump and Valve (Process-Level)

  **What to do**:
  Create `src/modular_simulation/unit_processes/pump.py` and `valve.py`:

  **Pump** (AlgebraicProcessModel):
  - Ports: 1 inlet, 1 outlet
  - CONTROLLED: inlet_flow, inlet_temperature, inlet_composition, inlet_pressure
  - ALGEBRAIC: outlet_pressure, outlet_temperature, power_consumed
  - CONSTANT: pressure_rise (Pa), efficiency (0-1, default 0.75), n_species
  - Outlet pressure = inlet pressure + pressure_rise
  - Power = volumetric_flow * pressure_rise / efficiency
  - Temperature rise from compression work: ΔT = Power / (F * Cp) (small for liquids)
  - Integrates with existing `PumpHydraulicElement` for hydraulic network coupling

  **Valve** (AlgebraicProcessModel):
  - Ports: 1 inlet, 1 outlet
  - CONTROLLED: inlet_flow, inlet_temperature, inlet_composition, inlet_pressure, open_fraction (0-1)
  - ALGEBRAIC: outlet_pressure, outlet_temperature
  - CONSTANT: Cv (valve coefficient), n_species
  - Isenthalpic: H_out = H_in, flash_ph to get outlet T (Joule-Thomson effect)
  - Pressure drop: ΔP = f(Cv, open_fraction, flow) per valve equation
  - Integrates with existing `ValveHydraulicElement`

  **Must NOT do**: Do NOT replace existing hydraulic elements. Do NOT model cavitation.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Two implementations building on existing hydraulic elements
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 22 | Blocked By: 8, 9, 10, 11

  **References**:
  - Pattern: `src/modular_simulation/connection/hydraulic_element.py` — PumpHydraulicElement, ValveHydraulicElement
  - Pattern: `examples/connection_layer/pump_causality_demo.py` — Pump hydraulic demo
  - API: PropertyPackage for density (pump power calc) and isenthalpic flash (valve)

  **Acceptance Criteria**:
  - [ ] Pump: outlet_pressure = inlet_pressure + pressure_rise
  - [ ] Pump: power_consumed = flow * ΔP / efficiency (within 1%)
  - [ ] Valve: enthalpy conservation (isenthalpic)
  - [ ] Valve: open_fraction=0 → zero flow (or near-zero)
  - [ ] All existing tests pass

  **QA Scenarios**:
  ```
  Scenario: Pump pressure and power
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_pump_valve.py::test_pump_pressure_power -v
    Expected: Test passes, correct pressure rise and power
    Evidence: .sisyphus/evidence/task-14-pump.txt

  Scenario: Valve isenthalpic
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_pump_valve.py::test_valve_isenthalpic -v
    Expected: Test passes, H_in ≈ H_out
    Evidence: .sisyphus/evidence/task-14-valve.txt
  ```

  **Commit**: YES | Message: `feat(units): add Pump and Valve unit processes` | Files: `src/modular_simulation/unit_processes/pump.py`, `src/modular_simulation/unit_processes/valve.py`, `tests/unit_process/test_layer4_pump_valve.py`

---

- [x] 15. Conversion Reactor

  **What to do**:
  Create `src/modular_simulation/unit_processes/conversion_reactor.py`:
  - `ConversionReactor` (AlgebraicProcessModel):
  - Ports: 1 inlet, 1 outlet
  - CONTROLLED: inlet_flow, inlet_temperature, inlet_composition
  - ALGEBRAIC: outlet_flow, outlet_temperature, outlet_composition
  - CONSTANT: n_species, pressure_drop
  - Configuration: `conversions: dict[str, float]` (species_name → fractional conversion 0-1)
  - `calculate_algebraic_values()`:
    - For each reaction with specified conversion X: moles_consumed = F_in * z_i * X
    - Apply stoichiometry to get all species changes
    - Outlet composition = (inlet_moles + changes) / total_outlet_moles
    - Energy balance: Q = 0 (adiabatic) → compute T_out via flash_ph(P, H_in, z_out) OR isothermal mode
  - Two thermal modes: adiabatic (default), isothermal (set T_out = T_in)

  **Must NOT do**: Do NOT use RateLaw protocol here (conversion reactor is simpler). Do NOT handle reaction equilibrium.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Straightforward stoichiometric reactor
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 22 | Blocked By: 5, 8, 9, 10, 11

  **References**:
  - Pattern: `src/modular_simulation/thermodynamics/kinetics.py` (Task 5) — Stoichiometry dict pattern
  - Pattern: `src/modular_simulation/thermodynamics/algebraic_process_model.py` (Task 8)

  **Acceptance Criteria**:
  - [ ] A→B with X=0.5: outlet has 50% less A, stoichiometric B produced
  - [ ] Mass balance: total moles in = total moles out (for equimolar reactions)
  - [ ] Adiabatic: enthalpy conserved (H_out = H_in)
  - [ ] Isothermal: T_out = T_in exactly
  - [ ] X > 1.0 raises error, X < 0 raises error

  **QA Scenarios**:
  ```
  Scenario: 50% conversion mass balance
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_conversion_reactor.py::test_50pct_conversion_mass_balance -v
    Expected: Test passes, correct outlet composition
    Evidence: .sisyphus/evidence/task-15-conversion-reactor.txt
  ```

  **Commit**: YES | Message: `feat(units): add ConversionReactor unit process` | Files: `src/modular_simulation/unit_processes/conversion_reactor.py`, `tests/unit_process/test_layer4_conversion_reactor.py`

---

- [x] 16. Component Separator

  **What to do**:
  Create `src/modular_simulation/unit_processes/component_separator.py`:
  - `ComponentSeparator` (AlgebraicProcessModel):
  - Ports: 1 inlet, 2 outlets (`outlet_1`, `outlet_2`)
  - CONTROLLED: inlet_flow, inlet_temperature, inlet_composition
  - ALGEBRAIC: outlet_1_flow, outlet_1_composition, outlet_2_flow, outlet_2_composition, outlet_1_temperature, outlet_2_temperature
  - CONSTANT: n_species
  - Configuration: `split_fractions: dict[str, float]` (species_name → fraction going to outlet_1, rest goes to outlet_2)
  - Both outlets at same T, P as inlet (ideal separation)
  - Mass balance: F1_i = F_in * z_i * split_i, F2_i = F_in * z_i * (1 - split_i)

  **Must NOT do**: Do NOT add energy of separation. Do NOT model non-ideal separation.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Simple ideal separator
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: 22 | Blocked By: 8, 9, 10, 11

  **References**:
  - Pattern: `src/modular_simulation/thermodynamics/algebraic_process_model.py` (Task 8)
  - Pattern: DWSIM ComponentSeparator concept

  **Acceptance Criteria**:
  - [ ] Split water/ethanol 90/10 and 10/90 → correct compositions
  - [ ] Total outlet moles = inlet moles (conservation)
  - [ ] Split fraction > 1.0 or < 0.0 raises error

  **QA Scenarios**:
  ```
  Scenario: Component separator mass balance
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_component_separator.py -v
    Expected: All tests pass, mass balance conserved
    Evidence: .sisyphus/evidence/task-16-component-separator.txt
  ```

  **Commit**: YES | Message: `feat(units): add ComponentSeparator unit process` | Files: `src/modular_simulation/unit_processes/component_separator.py`, `tests/unit_process/test_layer4_component_separator.py`

---

### Wave 5 — Complex Unit Processes

- [x] 17. Flash Drum

  **What to do**:
  Create `src/modular_simulation/unit_processes/flash_drum.py`:
  - `FlashDrum` (AlgebraicProcessModel):
  - Ports: 1 inlet, 2 outlets (`vapor_outlet`, `liquid_outlet`)
  - Two modes:
    - **Isothermal flash**: CONTROLLED `temperature` + `pressure`, compute VLE at T,P,z
    - **Adiabatic flash**: CONTROLLED `pressure`, outlet T computed from H_in via flash_ph
  - CONTROLLED states: inlet_flow, inlet_temperature, inlet_composition, flash_pressure, (flash_temperature if isothermal)
  - ALGEBRAIC states: vapor_fraction, vapor_flow, liquid_flow, vapor_composition, liquid_composition, outlet_temperature (if adiabatic)
  - Uses `PropertyPackage.flash_tp()` (isothermal) or `PropertyPackage.flash_ph()` (adiabatic)
  - Wraps FlashResult into outlet streams with correct phase tags
  - Edge cases: subcooled feed (VF=0 → all liquid), superheated feed (VF=1 → all vapor)

  **Must NOT do**: Do NOT implement flash solver from scratch (use thermo). Do NOT handle 3-phase. Do NOT add liquid level dynamics (that's a tank, not a flash drum).

  **Recommended Agent Profile**:
  - Category: `deep` — Core VLE unit with thermo integration
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: 22 | Blocked By: 6, 8, 9, 10, 11

  **References**:
  - API: `PropertyPackage.flash_tp(T, P, z)` → FlashResult with VF, liquid/vapor compositions
  - API: `PropertyPackage.flash_ph(P, H, z)` → FlashResult with T
  - Pattern: `src/modular_simulation/thermodynamics/property_package.py` (Task 6)
  - External: Rachford-Rice equation (handled internally by thermo's FlashVL)

  **Acceptance Criteria**:
  - [ ] Water flash at 373K, 101325Pa → VF≈1.0 (boiling)
  - [ ] Water flash at 300K, 101325Pa → VF≈0.0 (subcooled)
  - [ ] Binary system: liquid + vapor compositions satisfy K-value relationship (y_i = K_i * x_i)
  - [ ] Adiabatic flash: H_in = VF*H_vapor + (1-VF)*H_liquid (energy conservation)
  - [ ] Mass balance: F_in = F_vapor + F_liquid, F_in*z_i = F_vapor*y_i + F_liquid*x_i

  **QA Scenarios**:
  ```
  Scenario: Binary isothermal flash
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_flash_drum.py::test_binary_isothermal_flash -v
    Expected: Test passes, K-value relationship and mass balance satisfied
    Evidence: .sisyphus/evidence/task-17-isothermal-flash.txt

  Scenario: Adiabatic flash energy conservation
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_flash_drum.py::test_adiabatic_flash_energy -v
    Expected: Test passes, inlet enthalpy = weighted outlet enthalpy
    Evidence: .sisyphus/evidence/task-17-adiabatic-flash.txt

  Scenario: Subcooled feed (no vapor)
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_flash_drum.py::test_subcooled_feed -v
    Expected: Test passes, VF=0, all liquid outlet, zero vapor flow
    Evidence: .sisyphus/evidence/task-17-subcooled.txt
  ```

  **Commit**: YES | Message: `feat(units): add FlashDrum unit process with isothermal and adiabatic modes` | Files: `src/modular_simulation/unit_processes/flash_drum.py`, `tests/unit_process/test_layer4_flash_drum.py`

---

- [x] 18. CSTR with Pluggable Kinetics

  **What to do**:
  Create `src/modular_simulation/unit_processes/cstr.py`:
  - `CSTR` (ProcessModel — DYNAMIC, not algebraic):
  - Ports: 1 inlet, 1 outlet
  - DIFFERENTIAL states: species_moles[i] (mol for each species in local registry), temperature (K), volume (L)
  - CONTROLLED: inlet_flow (mol/s), inlet_temperature (K), inlet_composition (tuple), inlet_pressure (Pa)
  - ALGEBRAIC: outlet_composition (from species_moles), outlet_temperature, outlet_flow, concentration[i] (mol/L)
  - CONSTANT: reactor_volume (L, if fixed), pressure (Pa), n_species, heat_transfer_coeff (W/K), jacket_temperature (K), jacket_area (m²)
  - `differential_rhs()`:
    - Get concentrations: C_i = n_i / V
    - Get rates from RateLaw: `reaction_set.net_rates(concentrations_dict, T)` — BUT since RHS is static, pass reaction parameters as CONSTANT arrays (pre-extracted from RateLaw at attach_system time)
    - Actually: Create `_precomputed_kinetics` at `attach_system()` time that extracts numeric arrays from the RateLaw callable. The static RHS uses these arrays.
    - Alternative (simpler, Oracle-recommended): Store RateLaw reference in a module-level registry keyed by model instance ID. Static method looks it up. This avoids modifying the CONSTANT mechanism.
    - dn_i/dt = F_in*z_in_i - F_out*C_i*V_dot + sum(nu_ij * r_j * V)
    - dT/dt = (F_in*Cp*(T_in-T) + sum(r_j*V*(-ΔH_j)) + UA*(T_jacket-T)) / (V*rho*Cp)
    - dV/dt = F_in/rho_in - F_out/rho (if variable volume)
  - Energy balance: adiabatic (UA=0) or with jacket cooling
  - Outlet flow: overflow (F_out = F_in for constant volume) or level-controlled

  **Must NOT do**: Do NOT implement multiphase CSTR. Do NOT hardcode specific reactions. Do NOT bypass RateLaw protocol.

  **Recommended Agent Profile**:
  - Category: `deep` — Most complex unit process, kinetics integration, energy balance
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: 22 | Blocked By: 5, 7, 8, 9, 10, 11

  **References**:
  - Pattern: `examples/van_de_vusse_cstr/process_definition.py` — Existing CSTR with hardcoded Arrhenius
  - Pattern: `examples/simple_irreversible_energy_balance_system/process_definition.py` — CSTR with energy balance
  - Pattern: `src/modular_simulation/thermodynamics/kinetics.py` (Task 5) — RateLaw protocol, ReactionSet
  - Pattern: `src/modular_simulation/measurables/process_model.py` — ProcessModel, StateMetadata, attach_system()

  **Acceptance Criteria**:
  - [ ] CSTR with A→B first-order kinetics matches analytical steady-state: C_A_ss = C_A0 / (1 + k*τ) where τ=V/F
  - [ ] Van de Vusse kinetics reproduces existing example results (regression against examples/van_de_vusse_cstr)
  - [ ] Energy balance: adiabatic CSTR T rises for exothermic reaction
  - [ ] Jacket cooling: steady-state T between T_jacket and T_adiabatic
  - [ ] Plugging in different RateLaw changes behavior correctly

  **QA Scenarios**:
  ```
  Scenario: First-order CSTR steady state
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_cstr.py::test_first_order_steady_state -v
    Expected: Test passes, C_A converges to C_A0/(1+k*tau) within 1%
    Evidence: .sisyphus/evidence/task-18-cstr-steady-state.txt

  Scenario: Pluggable kinetics swap
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_cstr.py::test_kinetics_swap -v
    Expected: Test passes, different rate law gives different steady state
    Evidence: .sisyphus/evidence/task-18-cstr-kinetics-swap.txt

  Scenario: CSTR energy balance
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_cstr.py::test_energy_balance -v
    Expected: Test passes, temperature dynamics physically reasonable
    Evidence: .sisyphus/evidence/task-18-cstr-energy.txt
  ```

  **Commit**: YES | Message: `feat(units): add CSTR unit process with pluggable kinetics and energy balance` | Files: `src/modular_simulation/unit_processes/cstr.py`, `tests/unit_process/test_layer4_cstr.py`

---

- [x] 19. PFR with Pluggable Kinetics

  **What to do**:
  Create `src/modular_simulation/unit_processes/pfr.py`:
  - `PFR` (ProcessModel — DYNAMIC, uses ODE integration along reactor volume):
  - Ports: 1 inlet, 1 outlet
  - Model: ODE along volume coordinate V (0 to V_total), NOT time-dependent
  - Actually for dynamic simulation: discretize into N_cells CSTRs-in-series (finite volume method)
  - Each cell has: species_moles[i], temperature
  - DIFFERENTIAL states: cell_composition[cell][species], cell_temperature[cell] (flattened into 1D array)
  - CONTROLLED: inlet_flow, inlet_temperature, inlet_composition
  - ALGEBRAIC: outlet_composition, outlet_temperature (last cell's values)
  - CONSTANT: total_volume, n_cells (default 20), n_species, diameter, pressure
  - `differential_rhs()`: For each cell, compute rates via kinetics (same mechanism as CSTR), propagate flow from cell to cell
  - Energy balance per cell: same as CSTR but with advection from upstream cell
  - Configuration: `n_cells: int = 20` (more cells → better PFR approximation)

  **Must NOT do**: Do NOT implement steady-state PFR (keep dynamic for consistency). Do NOT add radial dispersion. Do NOT implement axial dispersion (CSTRs-in-series handles some back-mixing naturally).

  **Recommended Agent Profile**:
  - Category: `deep` — Multi-cell discretization, kinetics, energy balance
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: 22 | Blocked By: 5, 7, 8, 9, 10, 11

  **References**:
  - Pattern: `src/modular_simulation/unit_processes/cstr.py` (Task 18) — Same kinetics integration pattern
  - Pattern: `src/modular_simulation/measurables/process_model.py` — NDArray state support (see GasPhaseReactorProcessModel)
  - Pattern: `examples/gas_phase_polymerization/process_definition.py` — NDArray differential states

  **Acceptance Criteria**:
  - [ ] First-order A→B: outlet C_A = C_A0 * exp(-k*τ) (PFR analytical solution), within 5% for 20 cells
  - [ ] Increasing n_cells improves accuracy toward analytical
  - [ ] PFR gives higher conversion than CSTR for same V, F, k (known theoretical result)
  - [ ] Energy balance: adiabatic temperature profile monotonic for exothermic reaction

  **QA Scenarios**:
  ```
  Scenario: PFR first-order analytical comparison
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_pfr.py::test_first_order_analytical -v
    Expected: Test passes, outlet C_A within 5% of exp(-k*tau)*C_A0
    Evidence: .sisyphus/evidence/task-19-pfr-analytical.txt

  Scenario: PFR vs CSTR conversion comparison
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_pfr.py::test_pfr_higher_conversion_than_cstr -v
    Expected: Test passes, PFR conversion > CSTR conversion for same conditions
    Evidence: .sisyphus/evidence/task-19-pfr-vs-cstr.txt
  ```

  **Commit**: YES | Message: `feat(units): add PFR unit process as discretized cells-in-series with pluggable kinetics` | Files: `src/modular_simulation/unit_processes/pfr.py`, `tests/unit_process/test_layer4_pfr.py`

---

- [x] 20. Shortcut Distillation Column (Fenske-Underwood-Gilliland)

  **What to do**:
  Create `src/modular_simulation/unit_processes/shortcut_distillation.py`:
  - `ShortcutDistillation` (AlgebraicProcessModel):
  - Ports: 1 inlet (`feed`), 2 outlets (`distillate`, `bottoms`)
  - CONTROLLED: feed_flow, feed_temperature, feed_composition, feed_pressure
  - ALGEBRAIC: distillate_flow, distillate_composition, bottoms_flow, bottoms_composition, n_min_stages, min_reflux_ratio, actual_stages, condenser_duty, reboiler_duty, distillate_temperature, bottoms_temperature
  - CONSTANT: light_key_species (str → index), heavy_key_species (str → index), light_key_recovery (default 0.99), heavy_key_recovery (default 0.01), reflux_ratio_multiplier (R/R_min, default 1.3), column_pressure (Pa), n_species
  - `calculate_algebraic_values()`:
    1. Get relative volatilities α_i from K-values at feed conditions: `α_i = K_i / K_HK`
    2. **Fenske equation**: N_min = ln[(x_LK_D/x_HK_D) * (x_HK_B/x_LK_B)] / ln(α_LK)
    3. **Underwood equation**: solve Σ(α_i * x_F_i / (α_i - θ)) = 1 - q for θ, then R_min = Σ(α_i * x_D_i / (α_i - θ)) - 1
    4. **Gilliland correlation**: (N - N_min)/(N + 1) = f((R - R_min)/(R + 1)) using Molokanov correlation
    5. Feed quality q from flash at feed conditions (VF → q = 1 - VF)
    6. Condenser duty = distillate_flow * (R + 1) * ΔH_vap
    7. Reboiler duty = condenser_duty + feed_enthalpy - distillate_enthalpy - bottoms_enthalpy
  - Component distribution: use Fenske equation to distribute non-key components

  **Must NOT do**: Do NOT implement stage-by-stage MESH. Do NOT add condenser/reboiler as separate units. Do NOT model column dynamics.

  **Recommended Agent Profile**:
  - Category: `deep` — Complex algebraic calculation with multiple thermodynamic calls
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: 22 | Blocked By: 6, 8, 9, 10, 11

  **References**:
  - API: `PropertyPackage.flash_tp(T, P, z)` → FlashResult with K_values for relative volatilities
  - API: `PropertyPackage.enthalpy()` for duty calculations
  - External: Fenske equation: N_min = ln(D_LK/B_LK * B_HK/D_HK) / ln(α_avg)
  - External: Underwood: iterative solve for θ between α_HK and α_LK
  - External: Gilliland (Molokanov): Y = 1 - exp[(1+54.4X)/(11+117.2X) * (X-1)/sqrt(X)] where X=(R-Rmin)/(R+1)
  - External: https://en.wikipedia.org/wiki/Fenske_equation

  **Acceptance Criteria**:
  - [ ] Benzene-toluene separation: N_min matches textbook value (~7-8 for typical specs)
  - [ ] Light key recovery in distillate ≥ specified value
  - [ ] Heavy key recovery in bottoms ≥ (1 - specified_to_distillate)
  - [ ] Mass balance: F * z_i = D * x_D_i + B * x_B_i for all species
  - [ ] Energy balance: Q_reboiler - Q_condenser = D*H_D + B*H_B - F*H_F
  - [ ] Non-key component distribution physically reasonable (lighter-than-LK mostly in distillate)

  **QA Scenarios**:
  ```
  Scenario: Benzene-toluene textbook separation
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_distillation.py::test_benzene_toluene_fug -v
    Expected: Test passes, N_min ≈ 7-8, mass balance within 0.1%
    Evidence: .sisyphus/evidence/task-20-distillation-bt.txt

  Scenario: Distillation mass balance
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_distillation.py::test_mass_balance -v
    Expected: Test passes, F*z = D*x_D + B*x_B for all species
    Evidence: .sisyphus/evidence/task-20-distillation-balance.txt

  Scenario: Distillation energy balance
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_distillation.py::test_energy_balance -v
    Expected: Test passes, Q_reb - Q_cond = H_products - H_feed
    Evidence: .sisyphus/evidence/task-20-distillation-energy.txt
  ```

  **Commit**: YES | Message: `feat(units): add ShortcutDistillation column (Fenske-Underwood-Gilliland)` | Files: `src/modular_simulation/unit_processes/shortcut_distillation.py`, `tests/unit_process/test_layer4_distillation.py`

---

### Wave 6 — Integration

- [x] 21. Heat Exchanger (NTU-ε Method)

  **What to do**:
  Create `src/modular_simulation/unit_processes/heat_exchanger.py`:
  - `HeatExchanger` (AlgebraicProcessModel):
  - Ports: 2 inlets (`hot_inlet`, `cold_inlet`), 2 outlets (`hot_outlet`, `cold_outlet`)
  - CONTROLLED: hot_inlet_flow, hot_inlet_temperature, hot_inlet_composition, cold_inlet_flow, cold_inlet_temperature, cold_inlet_composition
  - ALGEBRAIC: hot_outlet_temperature, cold_outlet_temperature, duty, effectiveness, LMTD
  - CONSTANT: UA (W/K, overall heat transfer coefficient × area), flow_arrangement (counter/co/cross), n_species_hot, n_species_cold
  - `calculate_algebraic_values()`:
    1. Compute Cp_hot, Cp_cold via PropertyPackage
    2. C_hot = F_hot * Cp_hot, C_cold = F_cold * Cp_cold
    3. C_min = min(C_hot, C_cold), C_max = max(C_hot, C_cold), C_r = C_min/C_max
    4. NTU = UA / C_min
    5. Effectiveness ε from NTU-ε correlation based on flow_arrangement
    6. Q = ε * C_min * (T_hot_in - T_cold_in)
    7. T_hot_out = T_hot_in - Q/C_hot, T_cold_out = T_cold_in + Q/C_cold
  - Outlet compositions = inlet compositions (no reaction)
  - NTU-ε correlations for counter-current: ε = (1-exp(-NTU*(1-C_r)))/(1-C_r*exp(-NTU*(1-C_r)))

  **Must NOT do**: Do NOT implement shell-and-tube geometry. Do NOT add fouling factors. Do NOT model phase change in exchanger (use PropertyPackage flash if needed).

  **Recommended Agent Profile**:
  - Category: `deep` — Two-stream unit with NTU-ε correlation
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: YES | Wave 6 | Blocks: 22 | Blocked By: 6, 8, 9, 10, 11

  **References**:
  - API: `PropertyPackage.heat_capacity_cp(T, P, z, phase)` for Cp calculations
  - External: NTU-ε method: counter-current ε = (1-exp(-NTU*(1-Cr)))/(1-Cr*exp(-NTU*(1-Cr)))
  - External: Co-current: ε = (1-exp(-NTU*(1+Cr)))/(1+Cr)

  **Acceptance Criteria**:
  - [ ] Counter-current HX: Q matches NTU-ε formula to <0.1%
  - [ ] Energy balance: Q_hot = Q_cold (duty symmetry)
  - [ ] High NTU → ε approaches theoretical maximum
  - [ ] T_hot_out > T_cold_in (counter-current physical constraint)
  - [ ] Mass balance: outlet flows = inlet flows, compositions unchanged

  **QA Scenarios**:
  ```
  Scenario: Counter-current HX energy balance
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_heat_exchanger.py::test_counter_current_energy_balance -v
    Expected: Test passes, Q_hot = Q_cold within 0.1%
    Evidence: .sisyphus/evidence/task-21-hx-energy.txt

  Scenario: High NTU effectiveness limit
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_layer4_heat_exchanger.py::test_high_ntu_effectiveness -v
    Expected: Test passes, ε > 0.95 for NTU > 5
    Evidence: .sisyphus/evidence/task-21-hx-effectiveness.txt
  ```

  **Commit**: YES | Message: `feat(units): add HeatExchanger unit process with NTU-ε method` | Files: `src/modular_simulation/unit_processes/heat_exchanger.py`, `tests/unit_process/test_layer4_heat_exchanger.py`

---

- [x] 22. Integration Example — Multi-Unit Flowsheet

  **What to do**:
  Create `examples/unit_process_flowsheet/flowsheet_demo.py`:
  - Build a complete process flowsheet using pre-built unit processes:
    - Feed stream → Heater → CSTR (A→B first-order) → Flash Drum → Distillation Column
    - Demonstrate chainability via ConnectionNetwork + auto-coupling
    - Use SimulationRuntimeContext for thermo
    - Show pluggable kinetics on CSTR
  - Run simulation for sufficient time to reach steady state
  - Print key results: conversion, product purity, duties, flows
  - Add `examples/unit_process_flowsheet/README.md` explaining the flowsheet
  - This serves as the "sandbox" proof-of-concept

  **Must NOT do**: Do NOT add UI. Do NOT create a complex industrial process. Keep it pedagogical.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Integration example combining all layers
  - Skills: [] — No special skills
  - Omitted: [`playwright`] — No UI

  **Parallelization**: Can Parallel: NO | Wave 6 | Blocks: F1-F4 | Blocked By: 12-21

  **References**:
  - Pattern: `examples/connection_layer/two_tank_reaction_comparison.py` — Multi-unit ConnectionNetwork usage
  - Pattern: All unit processes from Tasks 12-21
  - Pattern: `src/modular_simulation/thermodynamics/runtime_context.py` (Task 7)

  **Acceptance Criteria**:
  - [ ] Script runs without errors: `uv run python examples/unit_process_flowsheet/flowsheet_demo.py`
  - [ ] Mass balance closes across entire flowsheet (total in ≈ total out within 0.1%)
  - [ ] Energy balance closes across entire flowsheet
  - [ ] CSTR reaches expected conversion for given kinetics
  - [ ] Flash drum separates vapor/liquid with correct compositions
  - [ ] Distillation produces high-purity product

  **QA Scenarios**:
  ```
  Scenario: Full flowsheet runs to completion
    Tool: Bash
    Steps: uv run python examples/unit_process_flowsheet/flowsheet_demo.py 2>&1 | tail -20
    Expected: No errors, prints steady-state results with physical values
    Evidence: .sisyphus/evidence/task-22-flowsheet-run.txt

  Scenario: Flowsheet overall mass balance
    Tool: Bash
    Steps: uv run python -m pytest tests/unit_process/test_integration_flowsheet.py::test_overall_mass_balance -v
    Expected: Test passes, feed_in ≈ products_out within 0.1%
    Evidence: .sisyphus/evidence/task-22-flowsheet-balance.txt
  ```

  **Commit**: YES | Message: `feat(examples): add multi-unit flowsheet integration example` | Files: `examples/unit_process_flowsheet/flowsheet_demo.py`, `examples/unit_process_flowsheet/README.md`, `tests/unit_process/test_integration_flowsheet.py`

---

## Final Verification Wave (4 parallel agents, ALL must APPROVE)

- [x] F1. Plan Compliance Audit — oracle
  Verify all 22 tasks implemented per plan. Check architectural decisions followed (no service objects in ProcessModel states, backward compat preserved, layer gates respected).

- [x] F2. Code Quality Review — unspecified-high
  Run `uv run ruff check src/modular_simulation/`, `uv run basedpyright src/modular_simulation/`, review for consistent naming, docstrings, type annotations.

- [x] F3. Real Manual QA — unspecified-high
  Run ALL test suites: `uv run python -m pytest tests/ -v --tb=long`. Run integration example. Verify all 11 unit processes work in isolation AND in the flowsheet.

- [x] F4. Scope Fidelity Check — deep
  Verify Must NOT Have list: no rigorous distillation, no VLLE, no batch reactor, no compressor, no UI changes, no string-based kinetics. Verify no scope creep.

## Commit Strategy
- One commit per task (22 feature commits + 0 for baseline)
- Conventional commit format: `feat(scope): description`
- Scopes: `thermo`, `kinetics`, `state`, `coupling`, `units`, `framework`, `examples`, `build`
- Each commit should leave the project in a green state (all tests passing)

## Success Criteria
1. All 11 unit processes importable from `modular_simulation.unit_processes`
2. Full existing test suite still passes (zero regressions)
3. Multi-unit flowsheet example runs and produces physically valid results
4. Mass and energy balances close to <0.1% across all unit processes
5. Plugging a different RateLaw into CSTR/PFR changes behavior correctly
6. Flash calculations return physically valid VLE results
7. Shortcut distillation matches textbook Fenske-Underwood-Gilliland results
8. Species can be specified by common name and auto-resolved via `chemicals`
9. Auto-coupling propagates material state between units without manual scripting
10. Type checking and linting pass with zero errors
