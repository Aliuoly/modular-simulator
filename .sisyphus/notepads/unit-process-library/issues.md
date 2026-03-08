# Issues - unit-process-library

[Blockers / Ambiguities] - SpeciesRegistry and ActiveSpeciesRegistry are not implemented yet. All existing code refers to generic boundary/state handling without per-species construct. No tests currently cover multi-species runtime behavior. Plan requires exhaustive mapping; next steps must include creating a species registry module and ensuring compatibility with existing boundary/state propagation logic.

- No unit_processes directory in src; plan 12-22 requires creating 9 unit process modules. Clarify integration example placement and test scaffolding for unit processes.

## Research Risks and Open Questions

---

### SPECIES IDENTIFICATION AND NORMALIZATION

**RISK 1: CAS Number Ambiguity**
- Issue: CAS numbers can have duplicates or retired entries (57 retired CAS for carbon alone)
- Evidence: chemicals.readthedocs.io/tutorial.html
- Mitigation: Always use `CAS_from_any()` for normalization; treat CAS as canonical but not unique
- Question: Should we store primary identifier as CAS only, or maintain multiple IDs?

**RISK 2: Formula Search Unreliability**
- Issue: 23 compounds share aspirin's C9H8O4 formula; formula search gives unpredictable results
- Evidence: chemicals.readthedocs.io/tutorial.html
- Mitigation: Never search by formula alone; always use name/CAS/InChI/InChIKey
- Implementation: Add warning/error if user tries formula-only lookup

**RISK 3: Chemical Data Quality**
- Issue: chemicals is a data collection project, not critically evaluated by experts
- Evidence: chemicals.readthedocs.io/chemical_package_tutorial.html (warning section)
- Mitigation: Document that values should be verified for critical applications
- Implementation: Add config flag for "strict" vs "lenient" mode (default lenient)

---

### PENG-ROBINSON AND FLASH CALCULATIONS

**RISK 4: Flash Convergence Near Critical Points**
- Issue: Flash calculations can fail or converge slowly near critical point or phase boundaries
- Evidence: GitHub issue #35 (adiabatic flash)
- Mitigation: Use phase hints from previous state; implement flash fallback to single-phase if VF≈0 or VF≈1
- Implementation: Add `flash_stability_attempts` parameter and retry logic

**RISK 5: Missing Binary Interaction Parameters (kijs)**
- Issue: Default kijs=0 assumes ideal mixture, which can be highly inaccurate for polar/associating compounds
- Evidence: test_flash_vll.py includes kijs from ChemSep PR database
- Mitigation: Provide mechanism to load custom kijs; warn if non-ideal system uses default zeros
- Implementation: Accept optional kijs matrix in PropertyPackage constructor; log warning if missing for polar components

**RISK 6: Cache Precision vs Performance Trade-off**
- Issue: Rounding T to 0.01 K, P to 1 Pa, z to 6 decimals improves cache hits but loses precision
- Mitigation: Make rounding precision configurable; document trade-offs
- Implementation: Add cache_precision config parameter; default (2, 0, 6) but allow adjustment

**RISK 7: Flash Result Validation**
- Issue: EquilibriumState.phase string uses 'V', 'L', 'LL', 'LLL' etc. - mapping to user-friendly terms needed
- Evidence: thermo.equilibrium.EquilibriumState.phase property
- Question: Should we normalize to 'vapor', 'liquid', 'two-phase' in adapter layer?

---

### FLASH DRUM AND SEPARATION

**RISK 8: Flash Round-Trip Tolerance**
- Issue: Enthalpy round-trip (TP→H→PH) shows temperature drift >0.1 K in some conditions
- Evidence: Documentation suggests 0.1 K tolerance is acceptable
- Mitigation: Use tighter tolerance if possible; document expected drift
- Question: Is 0.1 K acceptable for all use cases (e.g., near-critical, multi-liquid)?

**RISK 9: Single-Phase Flash Handling**
- Issue: FlashVL may return only vapor or only liquid phase; need to handle VF=0 or VF=1 edge cases
- Evidence: FlashVL documentation shows phase count varies
- Mitigation: Check `res.phase_count` and `res.gas is not None` before accessing phase properties
- Implementation: Add safe property getters with None defaults

---

### SHORTCUT DISTILLATION (FUG)

**RISK 10: Constant Relative Volatility Assumption**
- Issue: FUG assumes α constant along column, but actually varies with temperature
- Mitigation: Document this simplification; for accuracy, use rigorous tray-by-tray methods
- Implementation: Add warning in shortcut_distillation about assumptions; suggest rigorous methods for design

**RISK 11: Underwood Equation Multiple Roots**
- Issue: Underwood's first equation can have multiple roots; need to select physically meaningful one
- Evidence: CheGuide mentions need to solve for root θ
- Mitigation: Use scipy.optimize.brentq or robust solver; filter roots to positive real values
- Implementation: Add solver parameter selection; document root selection criteria

**RISK 12: Non-Key Component Distribution**
- Issue: FUG assumes all lighter-than-LK go to distillate, all heavier-than-HK go to bottoms
- Mitigation: Document this limitation; actual columns can have non-keys distributed
- Implementation: Add parameter `nonkey_distribution: str = 'fug' | 'user'` for flexibility

---

### HEAT EXCHANGER (NTU-ε)

**RISK 13: Counter-Flow Iterative Solution**
- Issue: ε_counter requires solving NTU = f(ε) iteratively; no closed-form solution
- Mitigation: Use scipy.optimize.newton with derivative; or pre-computed lookup table
- Implementation: Add NTU_solver_config for method selection; cache results for common (NTU, R) pairs

**RISK 14: Heat Capacity Variation with Temperature**
- Issue: NTU-ε assumes constant Cp, but Cp varies significantly with T
- Mitigation: Iterate: guess outlet T, calculate Cp at average, refine
- Implementation: Add `Cp_correction_iterations: int` parameter (default 0 for no correction, 1-3 for refinement)

**RISK 15: Phase Change Handling**
- Issue: Basic NTU-ε formulas don't account for boiling/condensation (constant-Q region)
- Mitigation: Check for phase change in property package; use segment method if detected
- Implementation: Add `phase_change_handling: bool` flag; raise error if True and not implemented

---

### PERFORMANCE AND CACHING

**RISK 16: Cache Invalidation Strategy**
- Issue: Step-local LRU cache works, but flash results may become invalid if composition changes
- Mitigation: Cache keyed by (species_set, T, P, z); invalidate if species set changes
- Implementation: Use hash of species IDs in cache key; clear on composition changes

**RISK 17: Multiple Flash Calls in Same Step**
- Issue: Flash called separately for enthalpy, entropy, density - repeated calculations
- Mitigation: Cache full EquilibriumState object; extract multiple properties from single flash
- Implementation: Add `cached_state` property to PropertyPackage; reuse if T, P, z match

**RISK 18: Numba Acceleration Compatibility**
- Issue: chemicals.numba can accelerate calculations but requires JIT compilation
- Mitigation: Optional opt-in; provide pure-Python fallback
- Implementation: Add `use_numba: bool` config; wrap functions conditionally

---

### INTEGRATION AND BACKWARD COMPATIBILITY

**RISK 19: PropertyPackage Protocol vs Existing MaterialState**
- Issue: MaterialState has pressure, temperature, mole_fractions but not species_ids
- Mitigation: Extend MaterialState with optional species_ids field (non-breaking)
- Implementation: Use keyword-only arguments; default None for backward compat

**RISK 20: Species Ordering Consistency**
- Issue: Multiple units may have different species order; requires canonical ordering
- Mitigation: ActiveSpeciesRegistry enforces one canonical ordering; projection at boundaries
- Implementation: Add SpeciesProjection class with to_local() and to_global() methods

**RISK 21: RuntimeContext Storage in ProcessModel States**
- Issue: Storing PropertyPackage in ProcessModel.CONSTANT violates "no service objects in states" rule
- Mitigation: Pass RuntimeContext via coupling layer, not store in states
- Implementation: RuntimeContext parameter in coupling steps; accessed via self.runtime_context

---

### TESTING AND VALIDATION

**OPEN QUESTION 1: Test Data Sources**
- Question: Should we embed test data (constants, kijs) or fetch from chemicals each time?
- Trade-off: Embedded = deterministic; Fetching = validates against current chemicals version

**OPEN QUESTION 2: Regression Test Baseline**
- Question: How to handle test result changes when chemicals data updates?
- Mitigation: Pin chemicals version in dev dependencies; document baseline expectations

**OPEN QUESTION 3: Performance Benchmarks**
- Question: What are acceptable flash calculation times for ODE integration?
- Action needed: Profile flash TP, flash PH for 2-10 component systems; set performance targets

---

### DEPENDENCY MANAGEMENT

**RISK 22: Version Compatibility Matrix**
- Issue: thermo and chemicals have tight coupling; version mismatches may cause failures
- Mitigation: Pin both versions together in pyproject.toml; test matrix
- Implementation: Use constraints like `thermo>=0.3.0,<0.5.0` for upper bound

**RISK 23: Optional Dependencies**
- Issue: numba and pint are optional but enhance functionality
- Decision: Exclude from required dependencies; document as "enhanced mode" extras
- Implementation: Add `[project.optional-dependencies]` or extras_require for 'acceleration'

---

### DOCUMENTATION AND USER EXPERIENCE

**OPEN QUESTION 4: Error Message Clarity**
- Question: How to make thermodynamic errors actionable for users?
- Example: "Flash failed at T=350 K, P=1e5 Pa" vs "Convergence failed - try phase hint 'L'"
- Implementation: Add context to all thermo errors; suggest solutions

**OPEN QUESTION 5: PropertyPackage Inspection**
- Question: Should users be able to query package for available methods, supported species?
- Implementation: Add `property_package.info()` method returning capabilities and metadata

---

- 2026-03-03 Task 5: no blockers encountered.
- 2026-03-03 Task 3 verification note: `lsp_diagnostics` unavailable for `.toml` and `.md` in this workspace (no configured LSP server for those extensions), so diagnostics check is N/A for the files changed in this task.
- 2026-03-04 Task 1: no implementation blockers encountered.
- 2026-03-04 Task 1 ambiguity resolved: formula-only identifiers remain accepted by interface but unresolved/ambiguous cases now raise actionable guidance to prefer common-name or CAS identifiers for deterministic behavior.
- 2026-03-04 Task 2: no implementation blockers encountered.
- 2026-03-04 Task 2 edge concern: `phase` remains intentionally permissive (`str | None`) for backward compatibility; downstream thermo adapters should normalize/validate accepted labels (`vapor`, `liquid`, `two-phase`) at integration boundaries.
- 2026-03-04 Task 6 implementation note: `FlashVL` can fail for single-component systems (observed `ZeroDivisionError` during pure-water TP flash); adapter now routes single-component packages through `FlashPureVLS` while keeping Peng-Robinson phase objects (`CEOSGas/CEOSLiquid(PRMIX)`) to preserve PR-only scope.
- 2026-03-04 Task 6 residual risk: cache-key quantization is enforced inside flash methods (rounded T/P/z and normalized composition), but `functools.lru_cache` still keys on method call arguments; repeated calls with numerically equivalent but differently represented tuples may miss cache unless caller inputs are already rounded/normalized.
- 2026-03-04 Task 7 blocker status: no implementation blockers encountered.
- 2026-03-04 Task 7 residual risk: `SimulationRuntimeContext.reaction_sets` is immutable as a mapping (`MappingProxyType`), but contained `ReactionSet` objects remain regular dataclasses and can still be replaced by creating a new context object; downstream tasks should treat contexts as value snapshots and avoid in-place reaction mutation assumptions.

## Task 6 (PropertyPackage Implementation) Research Risks - 2026-03-04

**RISK 24: Chemicals API Breaking Change (version 1.5.1)**
- Issue: Property functions Tc, Pc, omega now require CAS numbers, not names
- Evidence: Local test shows Tc('water') returns None; Tc('7732-18-5') returns 647.096 K
- Mitigation: Always use CAS_from_any() to normalize to CAS before property lookup
- Impact: All existing code using names directly for property retrieval is broken
- Status: HIGH - Requires update to all property lookup code

**RISK 25: Thermo API Breaking Change (version 0.6.0)**
- Issue: ChemicalConstantsPackage.from_IDs() returns tuple, not object
- Evidence: Local test shows type(result) == <class 'tuple'>
- Mitigation: Always unpack as `constants, properties = ChemicalConstantsPackage.from_IDs(species)`
- Impact: Any code expecting direct ChemicalConstantsPackage object will fail
- Status: HIGH - Requires update to all constants loading code

**RISK 26: Pressure Unit Confusion (Pa vs bar)**
- Issue: thermo uses Pascals throughout (Pcs, flasher.P, etc.)
- Evidence: constants.Pcs = [22064000.0, 6268000.0] which is Pa, not bar
- Risk: Passing bar values (e.g., 1e5 bar = 1e10 Pa) would be order-of-magnitude error
- Mitigation: Document clearly that pressure is in Pascals; consider unit conversion helper
- Status: MEDIUM - Documentation and defensive programming needed

**RISK 27: IPDB Missing Parameters for Non-Ideal Systems**
- Issue: Default kijs=0 for missing pairs assumes ideal mixture
- Evidence: IPDB.get_ip_asymmetric_matrix returns 0.0 for missing combinations
- Risk: Polar/associating compounds (alcohols, acids) have large deviations from ideality
- Mitigation: Check IPDB.has_ip_specific() and warn users about missing kijs
- Status: MEDIUM - Depends on use case (ideal vs non-ideal systems)

**RISK 28: Single-Phase Flash Access Errors**
- Issue: res.liquid0 and res.gas can be None when single-phase
- Evidence: FlashVL documentation shows phase count varies; tests check for None
- Risk: Accessing res.liquid0.zs without checking len(res.liquids) > 0 raises AttributeError
- Mitigation: Always check phase existence before accessing properties: `if res.gas is not None: ...`
- Status: MEDIUM - Robust error handling required

**RISK 29: Cache Precision vs Accuracy Trade-off**
- Issue: Rounding for cache stability loses precision near phase boundaries
- Evidence: Cache rounds T to 0.01 K, P to 1 Pa, z to 6 decimals
- Risk: Critical point calculations, phase split determination sensitive to small changes
- Mitigation: Make rounding precision configurable; document trade-offs for users
- Status: LOW-MEDIUM - Depends on use case requirements

**RISK 30: Chemical Metadata Lookup Failures**
- Issue: chemicals.search_chemical raises ValueError for unknown species
- Evidence: Documentation states exception is raised for unidentifiable names
- Risk: Runtime crash when user provides invalid species name
- Mitigation: Catch ValueError, provide helpful error messages with closest matches
- Status: MEDIUM - Requires error handling wrapper

**RISK 31: Flash Convergence Near Critical Points**
- Issue: Flash can fail or converge slowly near Tc, Pc
- Evidence: GitHub discussions mention flash stability issues
- Risk: Unit process simulation may fail with numerical errors
- Mitigation: Use phase hints from previous result; implement fallback to single-phase; increase iterations
- Status: MEDIUM - May affect high-accuracy use cases

**RISK 32: EquilibriumState Phase String Ambiguity**
- Issue: res.phase returns 'L', 'V', 'LL', 'LLL', etc.
- Evidence: thermo.bulk documentation shows phase string varies
- Risk: Users may expect normalized names like 'liquid', 'vapor', 'two-phase'
- Mitigation: Normalize phase strings in adapter layer; document mapping
- Status: LOW - UX consideration, not functional

**RISK 33: Multiple Flash Calls Redundancy**
- Issue: Separate flash calls for enthalpy, entropy, density repeat calculations
- Evidence: Each property method currently triggers separate flash
- Risk: Performance penalty in ODE integration with many property queries
- Mitigation: Cache EquilibriumState object; extract multiple properties from single flash
- Status: MEDIUM - Affects performance-critical applications

---

- 2026-03-04 Task 9 residual risk: boundary auto-propagation currently assumes source/target composition vectors are already aligned to global species ordering; no projection/reconciliation is applied yet (deferred to Task 11).
- 2026-03-04 Task 9 residual risk: pressure for propagated inlet MaterialState currently uses config default (default_pressure_pa) because line/node pressure mapping from hydraulic unknowns is not yet standardized in this layer.

- 2026-03-04 Task 9 retry residual risk update: hydraulic pressure fallback intentionally avoids broad `*pressure*` key scanning to prevent accidental consumption of unrelated pressure diagnostics (for example `node_pressure`); only explicit edge/global pressure keys are treated as propagation signals.
- 2026-03-04 Task 10 residual risk: enthalpy-correct mixer falls back to linear temperature mixing whenever any contributing stream lacks finite `enthalpy_molar` or `flash_ph` raises; this preserves runtime continuity but may underpredict/overpredict outlet temperature under strong latent-heat effects until all upstream streams provide consistent thermo metadata.
- 2026-03-04 Task 11 residual risk: species projection now fails fast when source/target registrations are incompatible or incomplete for a boundary edge (to avoid implicit reordering/dropping); plants that do not register subsystem species consistently will receive explicit `ValueError` during thermo propagation rather than silent fallback.
- 2026-03-04 Task 8 status: no blockers encountered during implementation/testing; residual note: workspace LSP intermittently reports unresolved imports for freshly added modules until package-level import path is stabilized, but `lsp_diagnostics` on changed files is now clean and targeted pytest passes.

- 2026-03-04 Task 12 residual risk: `Mixer.step()` intentionally catches property-package flash failures and keeps the linear flow-weighted temperature from algebraic calculation, so simulations stay numerically stable but can lose enthalpy fidelity when thermo calls fail.
- 2026-03-04 Task 12 residual risk: Mixer/Splitter use flattened vector states for compositions and outlet arrays; downstream integrations should keep strict shape conventions (`(n_inlets*n_species,)`, `(n_outlets*n_species,)`) to avoid length-mismatch validation errors.
- 2026-03-04 Task 13 residual risk: `HeaterCooler` requires `set_property_package(...)` for thermodynamic closure; without a property package, algebraic fallback values persist (pressure/composition remain valid) but outlet enthalpy and mode-specific energy closure are not physically resolved.
- 2026-03-04 Task 13 residual risk: mode is stored as a numeric constant selector (`0.0` duty, `1.0` temperature) for `ProcessModel` array compatibility; string inputs are normalized at validation time, so downstream tools should not assume mode is retained as a string state.
- 2026-03-04 Task 14 residual risk: Pump/Valve currently interpret `inlet_flow` as volumetric flow (`m^3/s`) to satisfy hydraulic-work power and valve ΔP relations; if downstream coupling continues to treat flow as molar (`mol/s`), explicit conversion logic or harmonized units will be required.
- 2026-03-04 Task 14 residual risk: Valve uses a positive pressure floor (`1e-9` Pa) for numerical stability; under extreme throttling this can clip algebraic pressure and slightly break exact hydraulic residual closure relative to unconstrained `ValveHydraulicElement` equations.
- 2026-03-04 Task 15 residual risk: conversion mapping by species name requires either `species_order` in reactor configuration or index-like keys (`0`, `species_1`, ...); ambiguous names without mapping are rejected by design to avoid silent species misalignment.
- 2026-03-04 Task 15 residual risk: when no property package is attached, adiabatic thermal mode cannot perform `flash_ph`; reactor keeps algebraic conversion and pressure/composition closure, but outlet temperature/enthalpy remain fallback values until thermo context is provided.
- 2026-03-04 Task 16 residual risk: `ComponentSeparator` accepts species-name `split_fractions` mappings only when `species_order` is provided (or index-like keys are used); unknown labels fail fast to prevent silent species misrouting.
- 2026-03-04 Task 16 residual risk: when an outlet flow is effectively zero, outlet composition intentionally falls back to inlet composition for numeric stability; downstream consumers should treat zero-flow compositions as placeholders, not physically meaningful assay data.

- 2026-03-04 Task 17 residual risk: `FlashDrum.calculate_algebraic_values()` intentionally provides placeholder algebraic values without thermodynamic closure when no property package is attached; physical flash behavior is applied in `step()` only after `set_property_package(...)`.
- 2026-03-04 Task 17 residual risk: phase tag metadata is implicit via dedicated outlet port names (`vapor_outlet`/`liquid_outlet`) and composition/flow states; no explicit string phase state is emitted on the unit itself, so downstream integrations should infer phase by outlet stream identity and `vapor_fraction`.
- 2026-03-04 Task 18 residual risk: module-level kinetics registry entries are keyed by per-instance `model_instance_id` and are currently not explicitly deregistered on model teardown; this is acceptable for test/runtime scope but may accumulate stale entries in very long-lived model-churn workflows.
- 2026-03-04 Task 18 residual risk: energy closure uses a lumped `volumetric_heat_capacity` and configurable species-wise `reaction_heat_coeffs`; this preserves generic pluggability but requires user calibration for quantitative fidelity when Cp/heat-of-reaction are strongly state-dependent.
- 2026-03-04 Task 19 residual risk: PFR advection currently assumes constant volumetric flow through all cells (`outlet_flow = inlet_flow`) and unit total concentration basis implied by inlet mole fractions, matching existing CSTR conventions but limiting compressibility/expansion fidelity for strongly non-isomolar or gas-density-sensitive cases.
- 2026-03-04 Task 19 residual risk: kinetics registry entries for PFR instances use the same module-level `model_instance_id` pattern as CSTR and are not explicitly removed on teardown; long-running high-churn simulations may accumulate stale registry records unless lifecycle cleanup is added later.
- 2026-03-04 Task 21 residual risk: `HeatExchanger` computes stream `Cp` at inlet states only (constant-Cp NTU-epsilon assumption); strong temperature-dependent `Cp` or near-phase-transition behavior may require iterative Cp updates for higher-fidelity duties/outlet temperatures.
- 2026-03-04 Task 21 residual risk: crossflow effectiveness uses a single algebraic approximation and does not distinguish detailed mixed/unmixed crossflow sub-configurations; users needing exact geometry-specific crossflow correlations should extend the arrangement model.
- 2026-03-04 Task 20 residual risk: shortcut non-key split uses volatility-based interpolation between HK and LK recoveries; this is physically reasonable for preliminary design but can deviate from real tray-by-tray non-key distribution for close-boiling systems.
- 2026-03-04 Task 20 residual risk: condenser/reboiler duties are shortcut enthalpy estimates at feed `T/P` (with reflux latent-load approximation), so they are directionally useful but not a replacement for rigorous energy-profile column design.
