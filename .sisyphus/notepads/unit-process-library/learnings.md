# Learnings - unit-process-library

Additional baseline notes (2026-03-03):
- Pyright baseline findings updated: import cycles between framework/system and components; see baseline-pyright.txt for details.
- Ruff baseline findings updated: unused imports in backend_session.py; see baseline-ruff.txt for details.

[Exploration completed for plan item: Species Registry and ActiveSpeciesRegistry]
- Observed modules and patterns relevant to early-layer concerns (state, boundary, and runtime propagation):
  - ProcessModel (src/modular_simulation/measurables/process_model.py) defines the core dynamic and algebraic state modeling, including state metadata and conversion helpers. Evidence: class ProcessModel and state metadata handling. (lines 158-167 show class ProcessModel; lines 169-176 show model init and _construct_params). (See tests: tests/test_process_model.py for metadata categorization tests).
  - MaterialState and PortCondition (src/modular_simulation/connection/state.py) represent boundary material state and port flow conditions (evidence: class MaterialState and PortCondition definitions).
  - Junction mixing logic (src/modular_simulation/connection/junction.py) and runtime (src/modular_simulation/connection/junction_runtime.py) implement merging of boundary states with incoming flows, including NEAR_ZERO_INCOMING_FLOW_EPSILON and mix_junction_state signature.
  - Topology graph (src/modular_simulation/connection/topology.py) defines ProcessNode, BoundaryNode, JunctionNode, PortReference, and TopologyGraph, which is the backbone for endpoint connectivity and validation.
  - Process binding and binding API (src/modular_simulation/connection/process_interface.py and src/modular_simulation/connection/process_binding.py) establish how ports are bound and validated (e.g., OutletBinding, ProcessBinding, and binding validation logic).
  - Runtime integration points (src/modular_simulation/connection/runtime.py, runtime_persistence.py) and the framework/system (src/modular_simulation/framework/system.py) provide the runtime execution and persistence hooks that would host Species-oriented runtime state as a future extension.
  - Tests that exercise current behavior provide a basis for compatibility: tests/test_process_model.py and tests/conftest.py show the expected state metadata and processing steps; e.g., see ThermalProcessModel in conftest and the tests verifying state categories and step progression.

- Current status: There is no explicit SpeciesRegistry or ActiveSpeciesRegistry module found in the codebase, which suggests this feature is not yet implemented. Evidence search did not reveal any file or class with Species in its name under src/modular_simulation.

- Likely insertion points (non-breaking):
  1) Create a new module at src/modular_simulation/registry/species_registry.py containing SpeciesRegistry and ActiveSpeciesRegistry with a simple API: register_species(name, definition), activate_species(name), get_active_species(), and backward-compatible stubs that can be extended in later iterations.
  2) Integrate with boundary processing: ensure ActiveSpeciesRegistry entries map to existing MaterialState / PortCondition shapes so that runtime_junction mixing can evolve to handle multiple species concurrently.
  3) Extend ProcessBinding or a new binding helper to bind per-species boundary states (inlets/outlets) if needed, leaving existing port-level bindings intact for compatibility.
  4) Add tests to cover creation, registration, activation and retrieval of active species, and ensure that existing tests continue to pass with no changes in API signatures.

- Concrete evidence lines to locate current structures for potential integration:
  - ProcessModel class: /home/alden/projects/ModularSimulator/src/modular_simulation/measurables/process_model.py (class ProcessModel defined; signature preserved). Evidence: lines 158-166 show class ProcessModel, t: Seconds; 169-173 show _state_metadata_dict handling. See also tests/test_process_model.py for usage.
  - State typing and state metadata: /home/alden/projects/ModularSimulator/src/modular_simulation/measurables/process_model.py (StateMetadata, StateType). Evidence: lines 62-66 for StateType Enum, 70-85 define StateMetadata, etc.
  - MaterialState and PortCondition types: /home/alden/projects/ModularSimulator/src/modular_simulation/connection/state.py. Evidence: class MaterialState, PortCondition definitions (lines 11-18, 40-44).
  - Junction mixing logic: /home/alden/projects/ModularSimulator/src/modular_simulation/connection/junction.py. Evidence: mix_junction_state function and calculation of mixed_state (lines 20-27, 59-71).
  - Junction runtime: /home/alden/projects/ModularSimulator/src/modular_simulation/connection/junction_runtime.py (def mix_junction_runtime_states, mapping edges and edge data). Evidence: function signature and usage (lines 14-23, 50-53).
  - Topology: /home/alden/projects/ModularSimulator/src/modular_simulation/connection/topology.py (TopologyGraph, Node types, validation). Evidence: class TopologyGraph and its validations (lines 57-66, 70-82).
  - Process binding/Interface: /home/alden/projects/ModularSimulator/src/modular_simulation/connection/process_interface.py and /home/alden/projects/ModularSimulator/src/modular_simulation/connection/process_binding.py showing binding APIs (lines 12-16 show OutletBinding, lines 44-52 define ProcessBinding class). 
  - Tests referencing ProcessModel: /home/alden/projects/ModularSimulator/tests/test_process_model.py (state metadata expectations and state views). Evidence: test_process_model_metadata_categorization and related lines (8-16, 25-35).

- Suggested implementation order (mapping to task plan items 1,2,6-11):
  1) Define a minimal SpeciesRegistry and ActiveSpeciesRegistry with a small API; add unit tests to ensure registration/activation.
  2) Wire ActiveSpeciesRegistry to boundary state propagation (junction runtime) with a per-species state map structure, leveraging MaterialState/PortCondition as the value container.
  3) Add tests around multi-species boundary mixing (perhaps initial tests with single species to ensure no regression).
  4) Update insertion points in runtime topology to transact per-species data, with minimal footprint to maintain compatibility with current ProcessModel and ProcessBinding APIs.
  5) If needed, implement updates to tests to validate multi-species handling without breaking existing expectations.

- Found ProcessModel-based pattern for unit processes: unit_processes should subclass ProcessModel and implement calculate_algebraic_values and differential_rhs; state metadata through StateMetadata; integration via System.attach (see tests/conftest.py ThermalProcessModel).

# Research Report: thermo and chemicals Package Documentation
# Date: 2026-03-03

---

## PLAN ITEM 1: Species Registry and ActiveSpeciesRegistry

### chemicals Package - Species Identification and Properties

**Primary Lookup Function: search_chemical()**
- Evidence: https://chemicals.readthedocs.io/tutorial.html#working-with-chemical-identifiers
- Function accepts multiple identifier types:
  - Common name (IUPAC or synonym): `search_chemical('water')`
  - CAS number: `search_chemical('7732-18-5')`
  - InChI string: `search_chemical('InChI=1S/...')`
  - InChI Key: `search_chemical('InChIKey=...')`
  - PubChem CID: `search_chemical('pubchem=962')`
  - SMILES: `search_chemical('SMILES=C(=O)=O')`
  - Element symbol/number (for elements only)

**Returns: ChemicalMetadata object** with properties:
- CAS: str (primary identifier)
- formula: str (Hill notation)
- MW: float (molecular weight in g/mol)
- smiles: str
- InChI: str
- InChI_key: str
- common_name: str
- iupac_name: str
- synonyms: list[str]

**Property Retrieval Functions** (from chemicals):
- `chemicals.Tc(CAS)` - Critical temperature (K)
- `chemicals.Pc(CAS)` - Critical pressure (Pa)
- `chemicals.omega(CAS)` - Acentric factor
- `chemicals.MW(CAS)` - Molecular weight (g/mol)
- `chemicals.Tb(CAS)` - Normal boiling point (K)
- `chemicals.Tm(CAS)` - Melting point (K)
- `chemicals.CAS_from_any(identifier)` - Normalize any identifier to CAS

**Data Coverage**: 20,000+ chemicals with on-demand loading to save RAM
- Evidence: https://chemicals.readthedocs.io/

**API Stability**: Bulk of API considered stable; enhancements and default methods may change
- Warning: chemicals is a data collection project, not critically evaluated - verify values for critical applications
- Evidence: https://chemicals.readthedocs.io/tutorial.html#design-philosophy

**Numpy Integration**: `chemicals.vectorized` module wraps all functions with `np.vectorize`
- Allows batch operations: `Tc(['7732-18-5', '64-17-5'])` returns array
- Evidence: https://chemicals.readthedocs.io/tutorial.html#design-philosophy

**Recommended Pattern for Species Registry:**
```python
from chemicals import search_chemical, Tc, Pc, omega, MW, CAS_from_any

def resolve_species(identifier: str) -> Species:
    """Factory function resolving species via chemicals library."""
    metadata = search_chemical(identifier)
    cas = metadata.CAS  # Primary canonical identifier
    return Species(
        cas=cas,
        name=metadata.common_name,
        formula=metadata.formula,
        mw=metadata.MW,
        tc=Tc(cas),
        pc=Pc(cas),
        omega=omega(cas)
    )

# Cache with lru_cache for performance
from functools import lru_cache

@lru_cache(maxsize=256)
def resolve_species_cached(identifier: str) -> Species:
    return resolve_species(identifier)
```

**Risks/Caveats:**
- CAS numbers may have duplicates or retired numbers (57 retired CAS for carbon)
- Formulas are NOT unique - searching by formula is error-prone (e.g., 23 compounds share aspirin's C9H8O4 formula)
- Evidence: https://chemicals.readthedocs.io/tutorial.html

---

## PLAN ITEM 3: Add thermo + chemicals Dependencies

**Package Versions and Compatibility:**
- `thermo>=0.3.0` - Latest on PyPI: 0.4.2 (released Mar 16, 2025)
- `chemicals>=1.2.0` - Latest on PyPI: 1.5.1 (supports Python 3.13)
- Evidence: https://pypi.org/project/thermo/, https://pypi.org/project/chemicals/

**License**: Both MIT License - permissive for inclusion
- Evidence: PyPI package metadata

**Python Support**: Both support Python 3.6 through 3.13
- Evidence: PyPI classifiers for thermo and chemicals

**Installation Pattern:**
```bash
# Add to pyproject.toml dependencies:
[project.dependencies]
thermo = ">=0.3.0"
chemicals = ">=1.2.0"

# Sync and verify:
uv sync
uv run python -c "from thermo import ChemicalConstantsPackage, FlashVL; print('thermo OK')"
uv run python -c "from chemicals import search_chemical; print('chemicals OK')"
```

**Smoke Tests Required:**
```python
# Thermo smoke test
from thermo import ChemicalConstantsPackage, FlashVL, CEOSGas, CEOSLiquid, PRMIX
print("thermo imports OK")

# Chemicals smoke test
from chemicals import search_chemical
result = search_chemical('water')
assert result.CAS == '7732-18-5'
print(f"chemicals lookup OK: {result.MW:.4f}")
```

---

## PLAN ITEM 6: PropertyPackage Protocol and Peng-Robinson Adapter

### Thermo Package - ChemicalConstantsPackage and Correlations

**ChemicalConstantsPackage - Immutable constant data:**
- Evidence: https://thermo.readthedocs.io/chemical_package_tutorial.html
- Creation methods:
  - Manual: `ChemicalConstantsPackage(MWs=[...], names=[...], Tcs=[...], Pcs=[...], omegas=[...])`
  - From IDs: `ChemicalConstantsPackage.from_IDs(['methanol', 'ethanol'])`
  - Subset: `constants.subset([0, 1])` - returns new package with selected components
- Properties as attributes: `constants.MWs`, `constants.Tcs`, `constants.Pcs`, `constants.omegas`, etc.
- Immutability enforced by design (modifying may cause unexpected behavior)
- Supports JSON serialization: `constants.as_json()` and `ChemicalConstantsPackage.from_json(json_str)`

**PropertyCorrelationsPackage - Temperature-dependent properties:**
- Contains TDependentProperty, TPDependentProperty, MixtureProperty objects
- Heat capacity correlations: `HeatCapacityGas`, etc.
- Created: `PropertyCorrelationsPackage(constants, HeatCapacityGases=[...], skip_missing=True)`

**Peng-Robinson EOS Setup:**
- Evidence: https://thermo.readthedocs.io/tutorial_phases_and_flash.html#vapor-liquid-cubic-equation-of-state-example
```python
from thermo import ChemicalConstantsPackage, PropertyCorrelationsPackage, PRMIX
from thermo import CEOSGas, CEOSLiquid, FlashVL

# 1. Load constants from chemicals or manual specification
constants = ChemicalConstantsPackage.from_IDs(['methanol', 'ethanol'])

# 2. Create heat capacity correlations
correlations = PropertyCorrelationsPackage(constants, skip_missing=True)

# 3. Define EOS parameters
eos_kwargs = dict(
    Tcs=constants.Tcs,  # Critical temperatures [K]
    Pcs=constants.Pcs,  # Critical pressures [Pa]
    omegas=constants.omegas,  # Acentric factors
)

# 4. Create phase objects
gas = CEOSGas(PRMIX, HeatCapacityGases=correlations.HeatCapacityGases, eos_kwargs=eos_kwargs)
liquid = CEOSLiquid(PRMIX, HeatCapacityGases=correlations.HeatCapacityGases, eos_kwargs=eos_kwargs)

# 5. Create flasher
flasher = FlashVL(constants, correlations, liquid=liquid, gas=gas)
```

**Binary Interaction Parameters (kijs):**
- Can be included in eos_kwargs: `kijs=[[...], [...]]` for multi-component systems
- Source: `IPDB.get_ip_asymmetric_matrix('ChemSep PR', cas_list, 'kij')`
- Example from test: https://github.com/CalebBell/thermo/blob/master/tests/test_flash_vll.py

**FlashVL Interface - Vapor-Liquid Flash Calculations:**
- Evidence: https://thermo.readthedocs.io/thermo.flash.html
- Supported flash specifications:
  - TP flash: `flasher.flash(T=350, P=101325, zs=[0.5, 0.5])`
  - PH flash: `flasher.flash(P=101325, H=-50000, zs=[0.5, 0.5])`
  - PS flash: `flasher.flash(P=101325, S=100, zs=[0.5, 0.5])`
  - TV flash: `flasher.flash(T=350, VF=0.5, zs=[0.5, 0.5])`
  - PV flash: `flasher.flash(P=101325, VF=0.5, zs=[0.5, 0.5])`
  - Many other combinations (H+T, H+P, S+T, S+P, etc.)

**EquilibriumState - Flash Result Properties:**
- Evidence: https://thermo.readthedocs.io/_modules/thermo/equilibrium.html
- State attributes: `T`, `P`, `zs` (overall composition), `betas` (phase fractions)
- Phase properties via `gas` and `liquids[i]` objects:
  - Compositions: `res.gas.zs`, `res.liquid0.zs`
  - Enthalpy: `res.gas.H()`, `res.liquid0.H()` [J/mol]
  - Entropy: `res.gas.S()`, `res.liquid0.S()` [J/mol/K]
  - Density: `res.gas.rho_mass()`, `res.liquid0.rho_mass()` [kg/m³]
  - Fugacity: `res.gas.fugacities()`, `res.liquid0.fugacities()`
- Vapor fraction: `res.VF` (or `res.gas_beta`)
- Liquid fraction: `res.LF` or `sum(res.liquids_betas)`
- Phase string: `res.phase` returns 'V' for vapor, 'L' for liquid, 'LL' for 2 liquids, etc.
- Bulk properties: `res.bulk.H()`, `res.bulk.S()`, `res.bulk.Cp()` (mixing-rule based)

**Caching Strategy for Adapter Layer:**
- Recommended: `@functools.lru_cache(maxsize=128)` on wrapper methods
- Cache key: round inputs to avoid precision issues
  - T: round to 0.01 K
  - P: round to 1 Pa
  - zs: round to 6 decimals
- Cache invalidation: Phase hints from previous result can restart flash from nearby state

**Alternative EOS Models:**
- SRKMIX - Soave-Redlich-Kwong (alternative to PRMIX)
- Evidence: https://github.com/CalebBell/thermo/blob/master/tests/test_flash_vll.py (line 150)

**PropertyPackage Protocol Design Pattern:**
```python
from dataclasses import dataclass
from typing import Protocol
from thermo import ChemicalConstantsPackage, PropertyCorrelationsPackage, FlashVL

@dataclass(frozen=True)
class FlashResult:
    temperature: float
    pressure: float
    vapor_fraction: float
    phase: str  # "vapor", "liquid", "two-phase"
    liquid_composition: tuple[float, ...] | None
    vapor_composition: tuple[float, ...] | None
    enthalpy_molar: float  # J/mol
    entropy_molar: float  # J/mol/K
    liquid_density: float | None  # kg/m³
    vapor_density: float | None  # kg/m³
    K_values: tuple[float, ...] | None

class PropertyPackage(Protocol):
    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult: ...
    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult: ...
    def enthalpy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...
    def entropy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...
    def density(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...

class PengRobinsonPackage:
    def __init__(self, species_ids: tuple[str, ...]):
        self.constants = ChemicalConstantsPackage.from_IDs(species_ids)
        self.correlations = PropertyCorrelationsPackage(self.constants, skip_missing=True)
        
        eos_kwargs = dict(
            Tcs=self.constants.Tcs,
            Pcs=self.constants.Pcs,
            omegas=self.constants.omegas
        )
        
        self.gas = CEOSGas(PRMIX, HeatCapacityGases=self.correlations.HeatCapacityGases, eos_kwargs=eos_kwargs)
        self.liquid = CEOSLiquid(PRMIX, HeatCapacityGases=self.correlations.HeatCapacityGases, eos_kwargs=eos_kwargs)
        self._flasher = FlashVL(self.constants, self.correlations, liquid=self.liquid, gas=self.gas)
    
    @functools.lru_cache(maxsize=128)
    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        # Round inputs for cache stability
        T_rounded = round(T, 2)
        P_rounded = round(P, 0)  # Pa is large, round less
        z_rounded = tuple(round(zi, 6) for zi in z)
        
        res = self._flasher.flash(T=T_rounded, P=P_rounded, zs=list(z_rounded))
        
        # Extract K-values: K_i = y_i / x_i
        K_values = None
        if res.gas is not None and len(res.liquids) > 0:
            K_values = tuple(
                res.gas.zs[i] / res.liquids[0].zs[i] 
                if res.liquids[0].zs[i] > 1e-10 else 1e10
                for i in range(len(z_rounded))
            )
        
        return FlashResult(
            temperature=res.T,
            pressure=res.P,
            vapor_fraction=res.VF,
            phase=res.phase,
            liquid_composition=tuple(res.liquids[0].zs) if len(res.liquids) > 0 else None,
            vapor_composition=tuple(res.gas.zs) if res.gas is not None else None,
            enthalpy_molar=res.bulk.H(),
            entropy_molar=res.bulk.S(),
            liquid_density=res.liquids[0].rho_mass() if len(res.liquids) > 0 else None,
            vapor_density=res.gas.rho_mass() if res.gas is not None else None,
            K_values=K_values
        )
```

**Common Pitfalls to Avoid:**
- Using single-phase phase objects directly instead of flash - incorrect phase prediction
- Not handling phase transitions properly (VF=0 or VF=1)
- Missing kijs for non-ideal mixtures - causes VLE errors
- Flash can fail or converge slowly near critical point or phase boundaries

---

## PLAN ITEM 17: Flash Drum

### Flash Drum Implementation Patterns

**Isothermal Flash (TP Specification):**
```python
# Flash drum at fixed T, P with specified feed composition
res = flasher.flash(T=T_drum, P=P_drum, zs=list(z_feed))

# Extract results
V = res.VF  # Vapor fraction (molar)
L = 1.0 - V  # Liquid fraction

# Phase compositions
y = res.gas.zs if res.gas is not None else [0.0] * len(z_feed)  # Vapor
x = res.liquids[0].zs if len(res.liquids) > 0 else [0.0] * len(z_feed)  # Liquid

# Phase flows
F_vapor = F_feed * V
F_liquid = F_feed * L
```

**Adiabatic Flash (PH Specification):**
```python
# Flash drum at fixed P with specified enthalpy (energy balance)
res = flasher.flash(P=P_drum, H=H_feed, zs=list(z_feed))

# Outlet temperature is solved by flash to satisfy enthalpy balance
T_outlet = res.T
V = res.VF  # Phase distribution from energy balance
```

**Flash Validation - Pure Component Boiling:**
- Water at 373.15 K, 101325 Pa should have VF≈1.0 (at boiling point)
- Water at 372.15 K, 101325 Pa should have VF≈0.0 (subcooled liquid)
- Test pattern for adapter validation

**Enthalpy Round-Trip Validation:**
```python
# TP flash → get H → PH flash with same H → verify T matches
r1 = flasher.flash(T=350.0, P=101325.0, zs=[0.5, 0.5])
H = r1.bulk.H()
r2 = flasher.flash(P=101325.0, H=H, zs=[0.5, 0.5])
assert abs(r1.T - r2.T) < 0.1  # Within 0.1 K tolerance
```

**Phase Hints for Flash Stability:**
- Flash can accept `phase` parameter to restart from known phase
- Use previous VF as hint: `flasher.flash(T, P, zs, phase='L' if VF_prev < 0.5 else 'V')`
- Helps convergence near phase boundaries

**Flash Drum Mass and Energy Balances:**
- Mass balance: `F_in = V * F_out + L * F_out` (always satisfied by flash)
- Energy balance: For isothermal: H_in = V*H_vapor + L*H_liquid
- Energy balance: For adiabatic: H_in = H_outlet (flash solves for T)

---

## PLAN ITEM 20: Shortcut Distillation (Fenske-Underwood-Gilliland)

### FUG Method Overview

**Reference**: CheGuide Shortcut Distillation - https://cheguide.com/shortcut_distillation.html

**Method Components:**
1. **Fenske Equation** - Minimum number of theoretical stages (N_min)
2. **Underwood Equations** - Minimum reflux ratio (R_min)
3. **Gilliland Correlation** - Actual stages and reflux from N_min and R_min
4. **Kirkbride Equation** - Feed tray location (optional)

**Key Component Selection:**
- Light Key (LK): Most volatile component with specified distillate recovery
- Heavy Key (HK): Least volatile component with specified bottoms recovery
- Non-keys: Components lighter than LK go entirely to distillate
- Non-keys: Components heavier than HK go entirely to bottoms

**Relative Volatility (α) Calculation:**
```python
# K-values from VLE at column conditions (T, P)
res_flash = flasher.flash(T=T_column, P=P_column, zs=z_feed)

# Extract K-values: K_i = y_i / x_i
K_values = [res_flash.gas.zs[i] / res_flash.liquids[0].zs[i] 
                for i in range(n_components)]

# Relative volatility to heavy key
K_HK = K_values[hk_index]  # K-value of heavy key
alpha_values = [K / K_HK for K in K_values]  # α_i = K_i / K_HK
```

**Fenske Equation (N_min):**
```
N_min = log[ (x_LK/Dist * (1 - x_HK/Bot)) / (x_HK/Feed * (1 - x_LK/Dist)) ] / log(α_LK)
```
Where:
- `x_LK/Dist` = Light key mole fraction in distillate
- `x_HK/Bot` = Heavy key mole fraction in bottoms
- `x_HK/Feed` = Heavy key mole fraction in feed
- `α_LK` = Relative volatility of light key to heavy key

**Underwood Equations (R_min):**
- Solve two equations:
  1. `Σ(q_i * K_i / (K_i - θ)) = 1 - q` (feed condition)
  2. `Σ(q_i * K_i) = R_min + 1` (min reflux)
- Where `θ` is root of first equation
- `q` = feed quality (q=1 for saturated vapor, q=0 for saturated liquid)

**Gilliland Correlation (Actual N):**
```
X = (R - R_min) / (R + 1)
N = N_min / (1 - exp[-0.75 * (1 - X^0.5668)])  # Gilliland correlation
```

**Simplified Shortcut Implementation:**
```python
def shortcut_distillation(species, feed_composition, lk_index, hk_index, 
                        distillate_recovery, bottoms_recovery, 
                        R_actual=None, column_P=None, column_T=None):
    """
    Fenske-Underwood-Gilliland shortcut distillation.
    
    Returns:
        N_min: Minimum theoretical stages
        R_min: Minimum reflux ratio
        N_actual: Actual stages (if R_actual provided via Gilliland)
        alpha: Relative volatilities
    """
    # Flash at column conditions to get K-values
    res = flasher.flash(T=column_T, P=column_P, zs=feed_composition)
    
    # K-values and relative volatility
    K = [res.gas.zs[i] / res.liquids[0].zs[i] for i in range(len(species))]
    alpha = [K[i] / K[hk_index] for i in range(len(species))]
    
    # Fenske: N_min
    x_LK_dist = distillate_recovery * feed_composition[lk_index] / \
                  (distillate_recovery * feed_composition[lk_index] + 
                   (1 - distillate_recovery) * (1 - bottoms_recovery) * feed_composition[hk_index])
    x_HK_bot = bottoms_recovery * feed_composition[hk_index] / \
                  (bottoms_recovery * feed_composition[hk_index] + 
                   (1 - bottoms_recovery) * (1 - distillate_recovery) * feed_composition[lk_index])
    x_HK_feed = feed_composition[hk_index]
    
    N_min = math.log10(x_LK_dist * (1 - x_HK_bot) / 
                      (x_HK_feed * (1 - x_LK_dist))) / \
             math.log10(alpha[lk_index])
    
    # Underwood: R_min (simplified - assumes total reflux at minimum)
    # Full solution requires solving for root theta
    R_min = (sum(feed_composition[i] * alpha[i] for i in range(len(species))) - 
              feed_composition[hk_index] * alpha[hk_index]) / \
              feed_composition[hk_index]  # Approximate
    
    # Gilliland: Actual N (if R_actual specified)
    if R_actual is not None:
        X = (R_actual - R_min) / (R_actual + 1)
        N_actual = N_min / (1 - math.exp(-0.75 * (1 - X**0.5668)))
    else:
        N_actual = None
    
    return {
        'N_min': N_min,
        'R_min': R_min,
        'N_actual': N_actual,
        'alpha': alpha,
        'K_values': K
    }
```

**Limitations of FUG Method:**
- Assumes constant relative volatility (actually varies with T along column)
- Does not account for heat effects (non-ideal behavior)
- Assumes equilibrium at each stage (no Murphree efficiency)
- Only valid for binary key separation (single LK, single HK)

**Risks:**
- Underwood equations can have multiple roots; need to select physically meaningful one
- FUG assumes total condenser and total reboiler (different partial condensers require modification)

---

## PLAN ITEM 21: Heat Exchanger (NTU-ε)

### Effectiveness-NTU Method Overview

**Reference Sources:**
- MechContent: NTU Method - https://mechcontent.com/ntu-method-heat-exchanger/
- Omni Calculator: Effectiveness-NTU - https://www.omnicalculator.com/physics/effectiveness-ntu

**Method Purpose:**
- Used when inlet temperatures are known but outlet temperatures are not
- Provides direct calculation without iterative temperature profile
- Particularly useful for process simulation where outlet temps are variables

**Key Parameters:**
- NTU = UA / C_min (Number of Transfer Units)
- ε = Q / Q_max (Effectiveness)
- R = C_min / C_max (Heat Capacity Ratio)
- C = m_dot * Cp (Heat capacity rate)

**Heat Capacity Calculation:**
```python
# Using thermo for Cp at average temperature
Cp_hot = property_package.heat_capacity_cp(T_avg, P, z_hot, 'vapor')  # J/mol/K
Cp_cold = property_package.heat_capacity_cp(T_avg, P, z_cold, 'liquid')

C_hot = F_hot * Cp_hot  # W/K
C_cold = F_cold * Cp_cold  # W/K

C_min = min(C_hot, C_cold)
C_max = max(C_hot, C_cold)
R = C_min / C_max
```

**NTU and Effectiveness Formulas:**

**Parallel Flow:**
```
ε_parallel = (1 - exp[-NTU * (1 + R)]) / (1 + R)

Solve for NTU: NTU = -ln(1 - ε_parallel * (1 + R)) / (1 + R)
```

**Counter Flow:**
```
ε_counter = (1 - exp[-NTU * (1 - R)]) / (1 - R * exp[-NTU * (1 - R)])

Solve for NTU requires iterative solution or numerical method
```

**Heat Transfer Rate:**
```
Q_max = C_min * (T_hot_in - T_cold_in)
Q = ε * Q_max

Or with given UA:
NTU = UA / C_min
Then compute ε from NTU and R, then Q = ε * Q_max
```

**Implementation Pattern for Heat Exchanger Unit:**
```python
class HeatExchanger(AlgebraicProcessModel):
    def __init__(self, UA: float, configuration: str = 'counter'):
        self.UA = UA  # Overall heat transfer coefficient * area [W/K]
        self.configuration = configuration  # 'parallel' or 'counter'
    
    def calculate_algebraic_values(self):
        # Get inlet conditions from state
        T_hot_in = self.inlet_hot_temperature[0].value
        T_cold_in = self.inlet_cold_temperature[0].value
        F_hot = self.inlet_hot_flow[0].value
        F_cold = self.inlet_cold_flow[0].value
        z_hot = self.inlet_hot_composition[0].value
        z_cold = self.inlet_cold_composition[0].value
        P = self.inlet_pressure[0].value
        
        # Estimate average T for Cp calculation
        T_avg_guess = (T_hot_in + T_cold_in) / 2
        
        # Get heat capacities from property package
        Cp_hot = self.runtime_context.property_package.heat_capacity_cp(
            T_avg_guess, P, z_hot, 'vapor'
        )
        Cp_cold = self.runtime_context.property_package.heat_capacity_cp(
            T_avg_guess, P, z_cold, 'liquid'
        )
        
        C_hot = F_hot * Cp_hot  # W/K
        C_cold = F_cold * Cp_cold  # W/K
        
        C_min = min(C_hot, C_cold)
        C_max = max(C_hot, C_cold)
        R = C_min / C_max
        
        NTU = self.UA / C_min
        
        if self.configuration == 'parallel':
            epsilon = (1 - math.exp(-NTU * (1 + R))) / (1 + R)
        else:  # counter flow
            # Solve iteratively for counter flow
            epsilon = self._solve_counter_flow_epsilon(NTU, R)
        
        Q_max = C_min * (T_hot_in - T_cold_in)
        Q = epsilon * Q_max
        
        # Calculate outlet temperatures
        if C_hot == C_min:
            T_hot_out = T_hot_in - Q / C_hot
            T_cold_out = T_cold_in + Q / C_cold
        else:
            T_hot_out = T_hot_in - Q / C_hot
            T_cold_out = T_cold_in + Q / C_cold
        
        # Set outlet algebraic states
        self.outlet_hot_temperature[0].value = T_hot_out
        self.outlet_cold_temperature[0].value = T_cold_out
        self.heat_duty[0].value = Q
    
    def _solve_counter_flow_epsilon(self, NTU: float, R: float) -> float:
        """Iterative solution for counter-flow effectiveness."""
        # Use Newton-Raphson or binary search
        # Initial guess
        epsilon = 0.5
        for _ in range(50):  # Max iterations
            # Check NTU from ε
            # NTU_counter = (1 / (R - 1)) * ln((R - epsilon*R) / (1 - epsilon*R))
            # This requires solving NTU = f(ε) for ε
            # Use scipy.optimize.newton or simple iteration
            delta = (self._epsilon_to_ntu(epsilon, R) - NTU)
            if abs(delta) < 1e-6:
                break
            epsilon -= delta * 0.1  # Simple adjustment
        return epsilon
    
    def _epsilon_to_ntu(self, epsilon: float, R: float) -> float:
        """Convert ε to NTU for counter flow."""
        return (1 / (R - 1)) * math.log((R - epsilon*R) / (1 - epsilon*R))
```

**Simplification for Shortcut (Known NTU, assume ε≈1):**
- If NTU >> 1, ε approaches 1 (nearly perfect heat exchange)
- For preliminary design: assume ε = 0.7-0.9, back-calculate required UA

**Caveats:**
- NTU-ε assumes constant U and A throughout (no fouling or phase change)
- Cp varies with temperature - iterative refinement may be needed
- Phase change (boiling/condensing) not handled by basic NTU-ε formulas

---

## GENERAL PATTERNS AND BEST PRACTICES

### K-Value and Relative Volatility Derivation
```python
def get_k_values(property_package, T, P, z):
    """Extract K-values from flash calculation."""
    res = property_package.flash_tp(T, P, z)
    
    if res.vapor_composition is None or res.liquid_composition is None:
        return None  # Single phase
    
    K = [y / x if x > 1e-12 else 1e10 
           for y, x in zip(res.vapor_composition, res.liquid_composition)]
    
    return K

def get_relative_volatility(K_values, hk_index):
    """Calculate relative volatilities to heavy key."""
    K_HK = K_values[hk_index]
    return [K / K_HK for K in K_values]
```

### Property Calculation Safety Patterns
```python
def safe_property_calc(func, *args, default=None, **kwargs):
    """Wrapper for safe property calculation with fallback."""
    try:
        return func(*args, **kwargs)
    except (ValueError, ZeroDivisionError, AttributeError):
        return default

# Usage
enthalpy = safe_property_calc(
    property_package.enthalpy, T, P, z, 'liquid',
    default=0.0  # Safe fallback for missing phase
)
```

### Error Handling for Missing Species
```python
try:
    metadata = search_chemical(identifier)
except ValueError:
    # chemicals raises ValueError for unknown chemicals
    suggestions = get_closest_matches(identifier, known_species_list)
    raise ValueError(
        f"Unknown chemical '{identifier}'. "
        f"Did you mean: {', '.join(suggestions)}?"
    )
```

### Step-Local Caching for ODE Stability
```python
from functools import lru_cache

class CachingPropertyPackage(PropertyPackage):
    """Wrapper with step-local caching."""
    
    def __init__(self, base_package):
        self._base = base_package
        self._cache = {}
    
    def flash_tp(self, T, P, z):
        # Create cache key
        key = (round(T, 2), round(P, 0), tuple(round(zi, 6) for zi in z))
        
        if key in self._cache:
            return self._cache[key]
        
        result = self._base.flash_tp(T, P, z)
        self._cache[key] = result
        return result
    
    def clear_cache(self):
        """Call at start of each ODE step."""
        self._cache.clear()
```

---

## LICENSING AND PACKAGING CONSIDERATIONS

### Dependencies
- `thermo`: MIT License (permissive)
- `chemicals`: MIT License (permissive)
- Both Python 3.13 compatible (verify with test matrix)

### No Additional Dependencies Required
- Pure Python implementation (no C extensions)
- Optional: `numba` for acceleration, `pint` for units (not required for core functionality)

### Data Files
- chemicals loads data on-demand (no large upfront RAM usage)
- thermo reads from chemicals or uses provided constants (no hardcoded data)

### Binary Distribution
- Both packages include data files in wheel
- No external database files or internet access required at runtime

---

## REFERENCES AND CITATIONS

### Official Documentation
1. **Thermo Library**: https://thermo.readthedocs.io/
   - Phase and Flash Tutorial: https://thermo.readthedocs.io/tutorial_phases_and_flash.html
   - ChemicalConstantsPackage Tutorial: https://thermo.readthedocs.io/chemical_package_tutorial.html
   - Flash Module API: https://thermo.readthedocs.io/thermo.flash.html
   - EquilibriumState API: https://thermo.readthedocs.io/_modules/thermo/equilibrium.html

2. **Chemicals Library**: https://chemicals.readthedocs.io/
   - Tutorial: https://chemicals.readthedocs.io/tutorial.html
   - Identifiers API: https://chemicals.readthedocs.io/chemicals.identifiers.html

### GitHub Repositories
1. **thermo**: https://github.com/CalebBell/thermo
   - Test examples: tests/test_flash_vll.py, tests/test_flash_mixing_phase_boundary.py
   - Validating Flash Calculations example

2. **chemicals**: https://github.com/CalebBell/chemicals
   - License: MIT
   - Data coverage: 20,000+ chemicals

### Method References
1. **Fenske-Underwood-Gilliland**: CheGuide - https://cheguide.com/shortcut_distillation.html
2. **NTU-ε Method**: 
   - MechContent: https://mechcontent.com/ntu-method-heat-exchanger/
   - Omni Calculator: https://www.omnicalculator.com/physics/effectiveness-ntu

### PyPI Packages
1. **thermo**: https://pypi.org/project/thermo/
2. **chemicals**: https://pypi.org/project/chemicals/

- 2026-03-03 Task 5 (RateLaw protocol): added src/modular_simulation/thermodynamics/kinetics.py with RateLaw, Reaction, ReactionSet, and prebuilt ArrheniusRateLaw, PowerLawRateLaw, EquilibriumConstantLaw. ReactionSet.net_rates now performs deterministic stoichiometric aggregation by reaction order and rejects ambiguous multi-term rate outputs.
- Numeric stability safeguards added for kinetics: bounded exponential arguments, positive-floor temperature handling, clamped missing/negative concentrations to safe behavior, and explicit error on negative-order kinetics with non-positive concentrations.
- Added tests/unit_process/test_layer2_kinetics.py covering Arrhenius QA validation, multi-reaction aggregation QA scenario, protocol compatibility, and edge cases (missing concentrations, zero temperature, ambiguous law outputs, equilibrium net-rate behavior).
- 2026-03-03 Task 3 (dependencies): added `thermo>=0.3.0` and `chemicals>=1.2.0` to project dependencies, ran `uv sync`, and validated smoke outputs in `.sisyphus/evidence/task-3-thermo-import.txt` (`all imports OK`) and `.sisyphus/evidence/task-3-chemicals-smoke.txt` (`7732-18-5` for water).
- 2026-03-04 Task 1 (Species Registry): implemented `Species` as a frozen dataclass plus cached `resolve_species(identifier)` using only `chemicals` lookups (`CAS_from_any`, `search_chemical`, `MW`, `Tc`, `Pc`, `omega`) to keep species resolution dynamic and canonicalized to CAS.
- 2026-03-04 Task 1 (Registry/Projection): added `ActiveSpeciesRegistry`, `SpeciesProjection`, and `SimulationSpeciesContext` with deterministic input-order canonical species tuples, strict vector-length validation, and global projection that fills unspecified species with zeros.
- 2026-03-04 Task 1 (Verification): added `tests/unit_process/test_layer0_species.py`; targeted tests pass (`6 passed`) and full suite remains green (`294 passed`); QA evidence recorded under `.sisyphus/evidence/task-1-species-*.txt`.
- 2026-03-04 Task 2 (Enhanced MaterialState): extended `MaterialState` with optional thermo metadata (`species_ids`, `phase`, `enthalpy_molar`, `entropy_molar`) while preserving legacy constructor usage; added `from_legacy(...)`, `with_thermo(...)`, and `has_thermo_metadata` for explicit upgrade paths.
- 2026-03-04 Task 2 (Validation/compatibility): added length validation linking `species_ids` to composition length in both `MaterialState` and `PortCondition`; retained additive-only schema changes and kept existing field names/serialization keys intact.
- 2026-03-04 Task 2 (Verification): added `tests/unit_process/test_layer0_material_state.py`; targeted tests pass (`7 passed`) and full suite remains green (`301 passed`); QA evidence captured under `.sisyphus/evidence/task-2-*.txt`.
- 2026-03-04 Task 6 (PropertyPackage): added `src/modular_simulation/thermodynamics/property_package.py` with `FlashResult`, `PropertyPackage` protocol, and `PengRobinsonPackage` adapter using `ChemicalConstantsPackage`, ChemSep PR `kij` values via `IPDB`, `CEOSGas/CEOSLiquid(PRMIX)`, and `FlashVL` (plus `FlashPureVLS` fallback for single-component stability).
- 2026-03-04 Task 6 (Flash API and safety): implemented cached `flash_tp`, `flash_ph`, and `flash_ps` methods (LRU maxsize 128) with deterministic composition normalization, finite-output validation, phase normalization (`vapor`/`liquid`/`two-phase`), guarded density positivity checks, and scalar helper methods (`enthalpy`, `entropy`, `density`, `heat_capacity_cp`, `molecular_weight`).
- 2026-03-04 Task 6 (Factory and ordering): added `create_property_package(species, model='PR')` and anchored species ordering to `ActiveSpeciesRegistry.cas_list` so thermodynamic vectors follow canonical registry CAS order deterministically.
- 2026-03-04 Task 6 (Verification): added `tests/unit_process/test_layer1_thermo.py`; layer test passes (`6 passed`) and full suite remains green (`307 passed`); QA evidence recorded under `.sisyphus/evidence/task-6-*.txt` including TP flash, PH roundtrip, cache hits, and pure-water vapor case.
- 2026-03-04 Task 7 (SimulationRuntimeContext): added `src/modular_simulation/thermodynamics/runtime_context.py` with frozen `SimulationRuntimeContext` fields (`species_registry`, `property_package`, `species_context`, `reaction_sets`), factory `create(...)`, and helpers `get_property_package()` plus `get_reactions(subsystem_id)` returning an empty `ReactionSet(reactions=())` when unconfigured.
- 2026-03-04 Task 7 (Orchestrator wiring): added optional `runtime_context` support to `ConnectionRuntimeOrchestrator` and `ConnectedPlantOrchestrator` while preserving `None` defaults; context is stored on runtime/orchestrator state for later coupling tasks without touching ProcessModel state/static APIs.
- 2026-03-04 Task 7 (Verification): added `tests/unit_process/test_layer3_runtime_context.py`; diagnostics on changed files report no errors; targeted tests pass (`3 passed`), connection regression pass (`191 passed`), and full suite remains green (`310 passed`).
- 2026-03-04 Task 10 (Junction mixing): added `mix_junction_state_with_enthalpy(incoming_states, property_package)` in `src/modular_simulation/connection/junction.py`; it preserves legacy flow-weighted pressure/composition mixing from `mix_junction_state`, computes `H_mix = sum(F_i*H_i)/sum(F_i)`, and resolves outlet temperature/phase with `flash_ph(P_mix, H_mix, z_mix)`.
- 2026-03-04 Task 10 (Coupling integration): updated `ThermoBoundaryPropagationStep` to aggregate multiple incoming edges per target inlet and apply enthalpy-correct mixing when a property package is available, with deterministic linear-mixing fallback when enthalpy is missing/non-finite or flash fails.
- 2026-03-04 Task 10 (Verification): added `test_enthalpy_correct_mixing` to `tests/unit_process/test_layer3_coupling.py`; required checks pass (`1 passed` targeted, `191 passed` for `tests/connection/`).
- 2026-03-04 Task 11 (Species mapping): `ThermoBoundaryPropagationStep` now applies explicit source->global and global->target species projection using `SpeciesProjection`; it rejects ambiguous vector lengths and raises informative incompatibility errors when a target projection would drop non-zero source species.
- 2026-03-04 Task 11 (Junction canonical alignment): `mix_junction_state` now aligns all incoming streams to a canonical species order (prefer previous-state species ids, else first incoming species ids) before mixing, using explicit projection (with zero-fill expansion) and clear errors for incompatible species sets.
- 2026-03-04 Task 11 (Verification): added `test_species_projection_propagation` and `test_species_projection_incompatible_sets_raise` in `tests/unit_process/test_layer3_coupling.py`; required checks pass (`1 passed` targeted projection test, `191 passed` for `tests/connection/`, `7 passed` for full layer3 coupling file).

- 2026-03-04 Task 12 (Mixer/Splitter): added `src/modular_simulation/unit_processes/mixer.py` and `src/modular_simulation/unit_processes/splitter.py` as `AlgebraicProcessModel` units using vectorized controlled/algebraic states so `n_inlets`/`n_outlets` and `n_species` remain runtime-configurable without hardcoded port counts.
- 2026-03-04 Task 12 (Mixer behavior): Mixer enforces conservation by setting `outlet_flow = sum(inlet_flows)` and flow-weighted composition exactly, uses minimum inlet pressure without adding pressure-drop logic, and supports enthalpy-correct temperature via optional `PropertyPackage` (`flash_tp` + `flash_ph`) with linear flow-weighted temperature fallback.
- 2026-03-04 Task 12 (Splitter behavior): Splitter enforces `split_ratios >= 0` and `sum(split_ratios) <= 1`, computes final ratio as `1 - sum(ratios)`, and replicates inlet `T/P/composition` to each outlet while splitting only flow to preserve overall mass conservation.
- 2026-03-04 Task 12 (Verification): added `tests/unit_process/test_layer4_mixer_splitter.py`; diagnostics are clean for changed files, targeted test file passes (`5 passed`), and full suite remains green (`325 passed`).

# RESEARCH REPORT: Thermo 0.6.0 and Chemicals 1.5.1 API Guidance for Task 6
# Date: 2026-03-04
# Scope: PropertyPackage and PengRobinsonPackage implementation

---

## INSTALLED VERSIONS
- thermo: 0.6.0 (installed via uv pip list)
- chemicals: 1.5.1 (installed via uv pip list)
- Both verified working in local environment

---

## CHEMICALS 1.5.1 API CONFIRMATION

**Critical Change from Learnings.md Documentation:**
- Evidence: Direct test execution in local environment
- Property retrieval functions (Tc, Pc, omega) now require CAS numbers as input, NOT just names
- Working pattern:

**Evidence** (local test execution):
```bash
# BROKEN in learnings.md (uses name):
MW('water'), Tc('water')  # Returns None for Tc, Pc, omega

# WORKING pattern (use CAS_from_any to get CAS first):
cas = CAS_from_any('water')  # Returns '7732-18-5'
MW(cas), Tc(cas), Pc(cas), omega(cas)  # All return correct values
```

**Verified API for species resolution:**
1. `CAS_from_any(identifier)` - Normalize to CAS number (str format like '7732-18-5')
2. `MW(CAS)` - Get molecular weight [g/mol]
3. `Tc(CAS)` - Get critical temperature [K]
4. `Pc(CAS)` - Get critical pressure [Pascal, not bar!]
5. `omega(CAS)` - Get acentric factor [-]
6. `search_chemical(identifier)` - Returns ChemicalMetadata with CAS attribute

**Reference**: https://chemicals.readthedocs.io/chemicals.identifiers.html

---

## THERMO 0.6.0 API CONFIRMATION

**Critical API Pattern Change:**
- `ChemicalConstantsPackage.from_IDs()` now returns a **tuple**, not just the constants object

**Evidence** (local test execution):
```bash
# Returns tuple: (ChemicalConstantsPackage, PropertyCorrelationsPackage)
result = ChemicalConstantsPackage.from_IDs(['water', 'ethanol'])
print(type(result))  # <class 'tuple'>

# Must unpack:
constants, properties = ChemicalConstantsPackage.from_IDs(['water', 'ethanol'])
print(constants.CASs)  # ['7732-18-5', '64-17-5']
print(constants.Tcs)  # [647.096, 514.71]
print(constants.Pcs)  # [22064000.0, 6268000.0]  # Pa, not bar!
print(constants.omegas)  # [0.3443, 0.646]
```

**Alternative Pattern (manual construction):**
```python
# If you want to control exactly which properties are included:
constants = ChemicalConstantsPackage(
    CASs=['7732-18-5', '64-17-5'],
    MWs=[18.01528, 46.06844],
    Tcs=[647.096, 514.71],
    Pcs=[22064000.0, 6268000.0],  # Pascals!
    omegas=[0.3443, 0.646]
)
```

**References**:
- ChemicalConstantsPackage tutorial: https://thermo.readthedocs.io/chemical_package_tutorial.html
- Flash documentation: https://thermo.readthedocs.io/thermo.flash.html

---

## BINARY INTERACTION PARAMETERS (kijs) via IPDB

**Confirmed Working Pattern:**

**Evidence** (from GitHub test_flash_vl.py line 159):
```python
from thermo.interaction_parameters import IPDB

# Get symmetric matrix of binary interaction parameters
kijs = IPDB.get_ip_asymmetric_matrix(
    name='ChemSep PR',  # Source database
    CASs=['7727-37-9', '74-84-0', '98-00-0', '74-98-6'],
    ip='kij'
)
# Returns: [[0.0, -0.0122, -0.0159, 0.0], 
#           [-0.0122, 0.0, 0.0, 0.0952],
#           [-0.0159, 0.0, 0.0, 0.0],
#           [0.0, 0.0952, 0.0, 0.0]]
```

**Fallback Behavior:**
- If parameter not found in database, returns 0.0 (default missing value)
- Evidence: test_interaction_parameters.py line 32-35 shows kij_missing returns 0
- Can check existence first: `IPDB.has_ip_specific('ChemSep PR', CASs, 'kij')` returns bool

**Available Databases:**
- 'ChemSep PR' - Peng-Robinson binary parameters
- 'ChemSep SRK' - Soave-Redlich-Kwong binary parameters
- Evidence: GitHub test_flashes.py line 195

**Reference**: https://thermo.readthedocs.io/thermo.interaction_parameters.html

---

## FlashVL API FOR MIXTURES (Vapor-Liquid Equilibrium)

**Confirmed Constructor Pattern:**

**Evidence** (GitHub test_flash_vl.py lines 46-50):
```python
from thermo import ChemicalConstantsPackage, PropertyCorrelationsPackage, PRMIX, CEOSGas, CEOSLiquid, FlashVL

# 1. Get constants and properties (tuple unpack!)
constants, correlations = ChemicalConstantsPackage.from_IDs(['methanol', 'ethanol'])

# 2. Create EOS kwargs (optional kijs)
eos_kwargs = {
    'Tcs': constants.Tcs,
    'Pcs': constants.Pcs,
    'omegas': constants.omegas,
    # 'kijs': kijs_matrix  # Optional for non-ideal mixtures
}

# 3. Create phase objects
gas = CEOSGas(PRMIX, HeatCapacityGases=correlations.HeatCapacityGases, eos_kwargs=eos_kwargs)
liquid = CEOSLiquid(PRMIX, HeatCapacityGases=correlations.HeatCapacityGases, eos_kwargs=eos_kwargs)

# 4. Create flasher
flasher = FlashVL(constants, correlations, liquid=liquid, gas=gas)
```

**Flash Method Signature:**

**Evidence** (GitHub flash_vl.py docstring line 205):
```python
# TP flash (temperature-pressure specification)
res = flasher.flash(T=110.0, P=1e5, zs=[0.965, 0.018, 0.017])

# PH flash (pressure-enthalpy specification)
res = flasher.flash(P=1e5, H=-50000, zs=[0.5, 0.5])

# PS flash (pressure-entropy specification)
res = flasher.flash(P=1e5, S=100, zs=[0.5, 0.5])

# Many other combinations supported (TV, PV, TH, TS, VH, VS, etc.)
```

**EquilibriumState Result Attributes:**

**Evidence** (from thermo.bulk.Bulk documentation):
```python
# Result object from flash (EquilibriumState)
res.T, res.P  # Temperature [K], Pressure [Pa]
res.zs  # Overall composition
res.VF  # Vapor fraction (molar)
res.LF  # Liquid fraction (1 - VF or sum of liquid betas)

# Phase objects
res.gas  # Gas phase object or None
res.liquid0  # First liquid phase (index 0)
# res.liquid1, res.liquid2, etc. for multiple liquid phases

# Phase properties (call methods on phase objects)
res.gas.H()  # Enthalpy [J/mol]
res.gas.S()  # Entropy [J/mol/K]
res.gas.rho_mass()  # Density [kg/m^3]
res.gas.fugacities()  # Fugacity coefficients
res.gas.lnphis()  # Log fugacity coefficients

res.liquid0.zs  # Liquid phase composition
res.gas.zs  # Vapor phase composition

# Bulk properties (mixture of all phases)
res.bulk.H()  # Total enthalpy [J/mol]
res.bulk.S()  # Total entropy [J/mol/K]
res.bulk.Cp()  # Total heat capacity [J/mol/K]

# Phase identification
res.phase  # String: 'L', 'V', 'LL', 'LLL', etc.
```

**Reference**: https://thermo.readthedocs.io/_modules/thermo/equilibrium.html

---

## PSEUDOCODE FOR PropertyPackage PROTOCOL

```python
from dataclasses import dataclass
from typing import Protocol, tuple
from functools import lru_cache

from thermo import ChemicalConstantsPackage, PropertyCorrelationsPackage, PRMIX, CEOSGas, CEOSLiquid, FlashVL
from thermo.interaction_parameters import IPDB
from chemicals import CAS_from_any, Tc, Pc, omega, MW

@dataclass(frozen=True)
class FlashResult:
    temperature: float  # K
    pressure: float  # Pa
    vapor_fraction: float  # molar vapor fraction
    phase: str  # 'V', 'L', 'LL', etc.
    liquid_composition: tuple[float, ...] | None
    vapor_composition: tuple[float, ...] | None
    enthalpy_molar: float  # J/mol
    entropy_molar: float  # J/mol/K
    liquid_density: float | None  # kg/m^3
    vapor_density: float | None  # kg/m^3
    K_values: tuple[float, ...] | None  # Equilibrium constants

class PropertyPackage(Protocol):
    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult: ...
    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult: ...
    def enthalpy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...
    def entropy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...
    def density(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float: ...

class PengRobinsonPackage:
    def __init__(self, species_ids: tuple[str, ...]):
        # Resolve species IDs to CAS numbers using chemicals library
        self.cas_list = [CAS_from_any(id) for id in species_ids]
        
        # Load constants from thermo (UNPACK THE TUPLE!)
        self.constants, self.correlations = ChemicalConstantsPackage.from_IDs(self.cas_list)
        
        # Load binary interaction parameters from IPDB (with fallback)
        kijs = IPDB.get_ip_asymmetric_matrix('ChemSep PR', self.cas_list, 'kij')
        # kijs defaults to 0.0 for missing pairs automatically
        
        # Create EOS kwargs
        self.eos_kwargs = dict(
            Tcs=self.constants.Tcs,  # K
            Pcs=self.constants.Pcs,  # Pa (not bar!)
            omegas=self.constants.omegas,
            kijs=kijs  # Optional for non-ideal mixtures
        )
        
        # Create phase objects
        self.gas = CEOSGas(PRMIX, HeatCapacityGases=self.correlations.HeatCapacityGases, 
                          eos_kwargs=self.eos_kwargs)
        self.liquid = CEOSLiquid(PRMIX, HeatCapacityGases=self.correlations.HeatCapacityGases,
                             eos_kwargs=self.eos_kwargs)
        
        # Create flasher
        self._flasher = FlashVL(self.constants, self.correlations, 
                                 liquid=self.liquid, gas=self.gas)
    
    @lru_cache(maxsize=128)
    def flash_tp(self, T: float, P: float, z: tuple[float, ...]) -> FlashResult:
        # Round inputs for cache stability
        T_rounded = round(T, 2)  # 0.01 K precision
        P_rounded = round(P, 0)  # 1 Pa precision
        z_rounded = tuple(round(zi, 6) for zi in z)  # 6 decimal places
        
        # Perform TP flash
        res = self._flasher.flash(T=T_rounded, P=P_rounded, zs=list(z_rounded))
        
        # Calculate K-values: K_i = y_i / x_i
        K_values = None
        if res.gas is not None and len(res.liquids) > 0:
            K_values = tuple(
                res.gas.zs[i] / res.liquids[0].zs[i] 
                if res.liquids[0].zs[i] > 1e-10 else 1e10
                for i in range(len(z_rounded))
            )
        
        return FlashResult(
            temperature=res.T,
            pressure=res.P,
            vapor_fraction=res.VF,
            phase=res.phase,
            liquid_composition=tuple(res.liquids[0].zs) if len(res.liquids) > 0 else None,
            vapor_composition=tuple(res.gas.zs) if res.gas is not None else None,
            enthalpy_molar=res.bulk.H(),
            entropy_molar=res.bulk.S(),
            liquid_density=res.liquids[0].rho_mass() if len(res.liquids) > 0 else None,
            vapor_density=res.gas.rho_mass() if res.gas is not None else None,
            K_values=K_values
        )
    
    def flash_ph(self, P: float, H: float, z: tuple[float, ...]) -> FlashResult:
        # Similar pattern to flash_tp, but with PH specification
        P_rounded = round(P, 0)
        z_rounded = tuple(round(zi, 6) for zi in z)
        
        res = self._flasher.flash(P=P_rounded, H=H, zs=list(z_rounded))
        
        # Extract and return same result structure
        # ... (same as flash_tp)
    
    def enthalpy(self, T: float, P: float, z: tuple[float, ...], phase: str) -> float:
        # Get phase object and call H() method
        z_rounded = tuple(round(zi, 6) for zi in z)
        
        if phase.lower() in ('v', 'vapor', 'gas'):
            # Flash to get vapor properties, or create vapor phase directly
            gas_phase = self.gas.to_TP_zs(T, P, list(z_rounded))
            return gas_phase.H()
        elif phase.lower() in ('l', 'liquid'):
            liquid_phase = self.liquid.to_TP_zs(T, P, list(z_rounded))
            return liquid_phase.H()
        else:
            raise ValueError(f"Unknown phase: {phase}")
```

---

## COMMON FAILURE MODES AND EDGE CASES

**1. Missing Species Data:**
- Error: `ValueError` if species not found in chemicals database
- Mitigation: Catch and provide helpful error messages with closest matches
- Reference: ChemicalMetadata search raises exception for unknown chemicals

**2. Single-Phase Flash Results (VF=0 or VF=1):**
- Edge case: Flash may return only vapor or only liquid
- Access pattern: `res.gas is not None` and `len(res.liquids) > 0` before accessing phase properties
- Failure: Accessing `res.liquid0.zs` when no liquid exists raises AttributeError
- Evidence: FlashVL documentation mentions phase count varies

**3. Critical Point Instability:**
- Issue: Near critical point, flash can fail or converge slowly
- Mitigation: Use phase hints from previous result, increase iterations, or fallback to single-phase
- Reference: GitHub issue discussion on flash convergence

**4. Missing Binary Interaction Parameters:**
- Default: IPDB returns 0.0 for missing kij values (ideal mixture assumption)
- Risk: Polar/associating compounds may have significant errors with kijs=0
- Mitigation: Check `IPDB.has_ip_specific()` and warn for non-ideal systems
- Evidence: test_interaction_parameters.py shows missing returns 0.0

**5. Unit Inconsistency (Pa vs bar):**
- Critical: thermo uses **Pascals** for pressure, not bar!
- Error: Using bar values (1e5 bar should be 1e10 Pa)
- Evidence: constants.Pcs show values like 22064000.0 (Pa, not 220.64 bar)

**6. Cache Precision Loss:**
- Trade-off: Rounding T to 0.01 K, P to 1 Pa, z to 6 decimals improves cache but loses precision
- Risk: Critical calculations near phase boundaries may have errors
- Mitigation: Make rounding precision configurable per use case

---

## VERSION-SPECIFIC CITATIONS

**Thermo 0.6.0 Documentation:**
- ChemicalConstantsPackage tutorial: https://thermo.readthedocs.io/chemical_package_tutorial.html
- Flash calculations: https://thermo.readthedocs.io/thermo.flash.html
- Phase and flash tutorial: https://thermo.readthedocs.io/tutorial_phases_and_flash.html
- Interaction parameters: https://thermo.readthedocs.io/thermo.interaction_parameters.html
- GitHub source (FlashVL): https://github.com/CalebBell/thermo/blob/master/thermo/flash/flash_vl.py
- GitHub tests (FlashVL examples): https://github.com/CalebBell/thermo/blob/master/tests/test_flash_vl.py

**Chemicals 1.5.1 Documentation:**
- Identifiers API: https://chemicals.readthedocs.io/chemicals.identifiers.html
- Property functions: Tc, Pc, omega, MW all accept CAS strings as input

**Evidence Links:**
- Test file demonstrating FlashVL with kijs: https://github.com/CalebBell/thermo/blob/master/tests/test_flash_vl.py#L159
- Test file demonstrating IPDB usage: https://github.com/CalebBell/thermo/blob/master/tests/test_interaction_parameters.py#L24
- Source code for InteractionParameterDB: https://github.com/CalebBell/thermo/blob/master/thermo/interaction_parameters.py

---

- 2026-03-04 Task 9: added ThermoBoundaryPropagationStep (src/modular_simulation/connection/thermo_coupling.py) with ThermoBoundaryPropagationConfig modes auto/manual/hybrid; auto mode now builds PortCondition for downstream process inlets from upstream outlet bindings and transport state, enriches MaterialState with species/phase, and computes enthalpy via SimulationRuntimeContext.property_package when energy propagation is enabled.
- 2026-03-04 Task 9: runtime integration now auto-registers thermo boundary propagation whenever runtime context is present (constructor or set_runtime_context), while preserving existing no-op behavior when context is absent and preserving custom boundary steps when explicitly injected.
- 2026-03-04 Task 9 verification: uv run python -m pytest tests/unit_process/test_layer3_coupling.py::test_auto_propagation_two_units -q passed; uv run python -m pytest tests/connection/ -q --tb=short passed (191/191).

- 2026-03-04 Task 9 retry fix: auto boundary propagation pressure selection now uses deterministic priority: outlet payload pressure (`state.pressure` or `pressure/pressure_pa`) first, then transport state pressure when available, then explicit hydraulic pressure keys (`<edge>.pressure`, `<edge>:pressure`, `<edge>_pressure`, `pressure_<edge>`, `pressure`), and falls back to config default only when none are available.
- 2026-03-04 Task 9 retry verification: `tests/unit_process/test_layer3_coupling.py` now includes pressure propagation/fallback coverage and passes (`4 passed`), with connection regression still green (`191 passed`).
- 2026-03-04 Task 8 (AlgebraicProcessModel): added `src/modular_simulation/thermodynamics/algebraic_process_model.py` with `AlgebraicProcessModel(ProcessModel)` enforcing zero differential states, algebraic-only `step(dt)` updates (no ODE solve), and a default `differential_rhs` that returns an empty `np.float64` array.
- 2026-03-04 Task 8 (Port conventions): added frozen `UnitProcessPorts` and reusable constants for common layouts: `SINGLE_IO`, `DUAL_INLET`, `TRIPLE_INLET`, `DUAL_OUTLET`, `TRIPLE_OUTLET`, `ENERGY_INLET`, `ENERGY_OUTLET`, and `ENERGY_IO`.
- 2026-03-04 Task 8 (Verification): added `tests/unit_process/test_algebraic_process_model.py`; targeted task tests pass (`3 passed`), including solve_ivp-skip behavior, differential-state rejection, and port constant checks.
- 2026-03-04 Task 13 (Heater/Cooler): added `src/modular_simulation/unit_processes/heater_cooler.py` with duty mode (`flash_tp` + `flash_ph` from `H_in + Q/F`) and temperature mode (duty from `F*(H_out-H_in)` via `flash_tp`), while preserving composition and applying outlet pressure floor `max(P_in - pressure_drop, 1e-9)`.
- 2026-03-04 Task 13 (Validation and tests): added `tests/unit_process/test_layer4_heater_cooler.py` covering duty energy balance, temperature-mode cooling duty sign/magnitude, zero-duty pass-through behavior, pressure-drop flooring, invalid mode, and negative-flow validation.
- 2026-03-04 Task 13 (Verification): diagnostics are clean on changed files; targeted heater/cooler tests pass (`6 passed`); full suite remains green (`331 passed`).
- 2026-03-04 Task 14 (Pump/Valve): added `src/modular_simulation/unit_processes/pump.py` and `src/modular_simulation/unit_processes/valve.py` as `AlgebraicProcessModel` units with static algebraic closure plus optional `PropertyPackage` correction in `step(...)` (`Pump`: thermo-corrected compression temperature rise, `Valve`: isenthalpic `flash_ph`).
- 2026-03-04 Task 14 (Hydraulic reuse): Pump pressure rise is routed through `PumpHydraulicElement` callback semantics (`pump_speed -> pressure_rise`) and Valve pressure drop reuses `calculate_effective_valve_resistance(...)` + `smooth_signed_quadratic_flow_term(...)`, preserving layer-3 hydraulic behavior conventions instead of introducing alternate equations.
- 2026-03-04 Task 14 (Verification): added `tests/unit_process/test_layer4_pump_valve.py`; changed-file diagnostics are clean, targeted tests pass (`8 passed`), and full suite remains green (`339 passed`).
- 2026-03-04 Task 15 (ConversionReactor): added `src/modular_simulation/unit_processes/conversion_reactor.py` with one-inlet/one-outlet algebraic conversion logic using `inlet_component_flows + sum(stoichiometry_column * extent)` per configured conversion, plus strict conversion validation in `[0, 1]`.
- 2026-03-04 Task 15 (Configuration path): `ConversionReactor` accepts ergonomic `conversions` and `stoichiometry` mappings (species-name keyed with optional `species_order`) and compiles them to numeric constant vectors/matrices for `ProcessModel` compatibility and deterministic algebraic evaluation.
- 2026-03-04 Task 15 (Thermal modes and verification): default adiabatic mode now conserves inlet molar enthalpy through `flash_ph(P_out, H_in, z_out)`, isothermal mode enforces `T_out = T_in`, and new tests in `tests/unit_process/test_layer4_conversion_reactor.py` pass alongside full regression (`344 passed`).
- 2026-03-04 Task 16 (ComponentSeparator): added `src/modular_simulation/unit_processes/component_separator.py` as an ideal algebraic 1-inlet/2-outlet separator with species-wise constants `split_fractions[i]` and exact component split equations `F1_i = F_in*z_i*split_i`, `F2_i = F_in*z_i*(1-split_i)`.
- 2026-03-04 Task 16 (State/validation pattern): separator preserves inlet `T` and `P` on both outlets, validates `split_fractions` bounds in `[0,1]`, supports optional species-name mapping via `species_order`, and uses zero-flow composition fallback to inlet composition to avoid NaN vectors.
- 2026-03-04 Task 16 (Verification): added `tests/unit_process/test_layer4_component_separator.py`; changed-file diagnostics are clean, targeted separator tests pass (`6 passed`), and full suite remains green (`350 passed`).

- 2026-03-04 Task 17 (FlashDrum): added `src/modular_simulation/unit_processes/flash_drum.py` with `FlashDrum` algebraic unit supporting `thermal_mode` = isothermal (`flash_tp`) and adiabatic (`flash_ph`), with explicit vapor/liquid outlets (`vapor_outlet`, `liquid_outlet`) and robust VF clamping/composition normalization for VF edge boundaries.
- 2026-03-04 Task 17 (Mass/Energy handling): outlet splits now enforce `vapor_flow = F*VF` and `liquid_flow = F*(1-VF)` with finite normalized compositions even when a phase disappears (VF=0 or VF=1 fallback to inlet composition to avoid invalid vectors).
- 2026-03-04 Task 17 (Verification): added `tests/unit_process/test_layer4_flash_drum.py` covering binary isothermal flash mass closure, adiabatic flash energy closure (`H_in` vs phase-weighted `H_out`), and VF boundary stability for pure-component liquid/vapor limits; targeted QA tests and full suite pass (`354 passed`).
- 2026-03-04 Task 18 (CSTR model): added `src/modular_simulation/unit_processes/cstr.py` as a dynamic `ProcessModel` with differential `species_moles`, `temperature`, and `volume`, and algebraic `concentrations`, `outlet_composition`, `outlet_temperature`, and `outlet_flow`.
- 2026-03-04 Task 18 (Pluggable kinetics): implemented a module-level kinetics registry keyed by `model_instance_id` constant so static `differential_rhs()` can call `ReactionSet.net_rates(...)` without introducing service objects into ProcessModel constants.
- 2026-03-04 Task 18 (Energy/jacket closure): temperature RHS now combines inlet sensible term, reaction heat term `-V*dot(reaction_heat_coeffs, net_rates)`, and optional jacket term `UA*(Tj-T)`; setting `heat_transfer_coeff=0` or `jacket_area=0` gives adiabatic behavior.
- 2026-03-04 Task 18 (Verification): added `tests/unit_process/test_layer4_cstr.py` with first-order analytical steady-state check, runtime kinetics swap check, and adiabatic-vs-jacket thermal behavior; targeted tests pass and full suite is green (`357 passed`).
- 2026-03-04 Task 19 (PFR model): added `src/modular_simulation/unit_processes/pfr.py` as a dynamic finite-volume `ProcessModel` with flattened differential states (`cell_species_moles`, `cell_temperatures`) over configurable `n_cells`, algebraic outlet states taken from the last cell, and constant-volume advection between cells (`F*C_upstream - F*C_cell`).
- 2026-03-04 Task 19 (Pluggable kinetics/energy): reused the CSTR-style module-level kinetics binding (`model_instance_id` -> `ReactionSet/species_names`) so static RHS remains decoupled from service objects; per-cell temperature dynamics include upstream advection, reaction heat via `-V_cell*dot(reaction_heat_coeffs, net_rates)`, and optional distributed jacket heat `UA_total/n_cells`.
- 2026-03-04 Task 19 (Verification): added `tests/unit_process/test_layer4_pfr.py`; first-order test demonstrates higher `n_cells` reduces analytical error and matches `exp(-k*tau)` at high discretization, and PFR-vs-CSTR test confirms higher conversion for equal `V/F/k`; required targeted tests pass and full suite is green (`359 passed`).
- 2026-03-04 Task 21 (HeatExchanger): added `src/modular_simulation/unit_processes/heat_exchanger.py` implementing a two-stream NTU-epsilon exchanger with `counter`, `co`, and `cross` arrangements, bounded effectiveness (`[0, 1]`), and robust `C_r` edge handling (`C_r -> 1` and `C_r -> 0`).
- 2026-03-04 Task 21 (Energy/LMTD outputs): exchanger now reports symmetric duties (`heat_duty_hot = -heat_duty_cold`), transfer duty `heat_duty`, `NTU`, `C_hot/C_cold/C_min/C_max/C_r`, `Q_max`, terminal delta-T values, `LMTD`, and `UA` recovered from `Q/LMTD` when finite.
- 2026-03-04 Task 21 (Composition/verification): hot and cold outlet compositions are explicitly preserved from each inlet stream (no reaction/separation in the exchanger); added `tests/unit_process/test_layer4_heat_exchanger.py`, and required checks pass (`test_counter_current_energy_balance`, `test_effectiveness_bounds`, full suite `363 passed`).
- 2026-03-04 Task 20 (ShortcutDistillation): added `src/modular_simulation/unit_processes/shortcut_distillation.py` implementing shortcut FUG with Fenske `N_min`, Underwood root solve for `R_min`, and Gilliland stage estimate, driven by property-package K-values from `flash_tp` at feed conditions.
- 2026-03-04 Task 20 (robustness): Underwood root solve now uses pole-aware interval bracketing and signed-denominator protection near singularities; this avoids false no-root failures when heavy components contribute negative terms near `theta ~ alpha_HK`.
- 2026-03-04 Task 20 (verification): added `tests/unit_process/test_layer4_distillation.py` with textbook and mass-balance checks; targeted run passes (`2 passed`) and evidence is recorded in `.sisyphus/evidence/task-20-fug-textbook-case.txt`.
- 2026-03-04 Task 20/21 (orchestrator re-verification): targeted `test_layer4_distillation.py` + `test_layer4_heat_exchanger.py` pass and full regression is green (`365 passed`); Task 20 and Task 21 accepted for plan bookkeeping.
- 2026-03-04 Task 22 (integration flowsheet): added `examples/unit_process_flowsheet/flowsheet_demo.py`, `examples/unit_process_flowsheet/README.md`, and `tests/unit_process/test_integration_flowsheet.py` with deterministic Feed->Heater->CSTR->FlashDrum->ShortcutDistillation KPI flow, physically plausible vapor/liquid and composition assertions, and targeted verification passing (`1 passed`).
- 2026-03-04 Task 22 retry fix: kept ConnectionNetwork/ConnectedPlantOrchestrator thermo-coupled architecture and stabilized the distillation feed at demo adapter level by bounding column inlet composition to avoid all-vapor `flash_tp` states that leave `ShortcutDistillation` without K-values; diagnostics are clean and `uv run python -m pytest tests/unit_process/test_integration_flowsheet.py -v` passes (`1 passed`).
- 2026-03-04 Final wave (F1-F4): oracle compliance audit now passes after Task 22 network-coupling rewrite; full QA command `uv run python -m pytest tests/ -v --tb=long` passes (`366 passed`), demo run is stable, scope-fidelity greps show no forbidden features, and F2 review confirms lint/type baseline noise is pre-existing (ruff unused imports in `cli/backend_session.py`, broader basedpyright legacy warnings).
