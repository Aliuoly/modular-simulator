# Solver Stack Alternatives to SciPy

**Project:** ModularSimulator v1.0 Kernel stability  
**Researched:** 2026-03-29  
**Scope:** Runtime / solver-substrate alternatives for a Python 3.13 brownfield backend  
**Overall confidence:** MEDIUM-HIGH

## Recommendation Summary

If SciPy is no longer good enough as the **primary** kernel substrate, the first serious alternative to explore is **official SUNDIALS via `sundials4py`**. It is the closest brownfield move: Python-native, purpose-built for stiff ODE/DAE and nonlinear algebraic systems, officially maintained, now pip-installable, and much better aligned with whole-flowsheet / hybrid-coupled directions than staying inside `solve_ivp` alone.

The second serious escalation path is **PETSc + petsc4py**. It is the strongest option when the kernel becomes a true sparse nonlinear system platform with custom preconditioning, matrix-free Jacobians, solver composition, and heavy telemetry requirements. It is also the heaviest operational jump.

**Do not make JAX/Diffrax the next move.** It has real performance upside for pure array/JIT workloads, but it is a poor brownfield fit for this repo’s current object-heavy Python runtime, callback-oriented gameplay/session facades, and DAE-heavy direction. Likewise, **Julia interop is a later-stage bet, not the first post-SciPy move**: major upside, major ops/runtime boundary cost.

**Assimulo and scikits-odes are no longer the recommended way forward.** They matter mainly as legacy/reference wrappers; both are now weaker adoption targets than official `sundials4py` for Python 3.13-era work.

## Explicit Recommendation: What to Explore Before and After SciPy

### Before replacing SciPy

1. **Prove the current bottlenecks precisely**
   - Add kernel telemetry: residual norms, Jacobian assembly time, factorization time, nonlinear iterations, rejected steps, warm-start hit rate.
   - The repo already exposes stable session/runtime facades (`PlantBackendSession`, runtime step orchestration); use those as measurement boundaries.
2. **Exploit the obvious brownfield wins inside today’s kernel shape**
   - Stop densifying hydraulic Jacobians before solve; the current hydraulic path assembles sparse structure but then calls dense `np.linalg.solve`.
   - Stop defaulting blindly to `LSODA`; the current system config still defaults to `{"method": "LSODA"}`.
3. **Define the adapter seam now**
   - Standardize a solver-kernel interface around: state vector, residual/Jacobian callbacks, bounds, initialization, warm start state, and telemetry.

### First post-SciPy exploration

1. **`sundials4py` adapter spike**
   - CVODE for stiff ODE stepping
   - IDA for semi-explicit / implicit DAE cases
   - KINSOL for nonlinear initialization / residual correction / steady solves

### If `sundials4py` still is not enough

2. **petsc4py TS/SNES/KSP path**
   - Only justified once you need solver composition, custom preconditioners, matrix-free operators, variable bounds / VI-style solves, or very large sparse coupled systems.

### Later / specialized explorations

3. **CasADi** when symbolic Jacobians, consistent initialization, and warm-started nonlinear solves dominate.
4. **Julia interop (`juliacall` + `diffeqpy` / direct SciML)** only if Python-native paths lose decisively on representative flowsheets.
5. **JAX/Diffrax** only for isolated, array-pure hot kernels or differentiable surrogate subproblems, not as the primary backend substrate.

## Comparison Table

| Option | Brownfield migration fit | Performance upside | Main downside | Packaging/runtime risk | Recommendation |
|---|---|---|---|---|---|
| **SUNDIALS via `sundials4py`** | **High** | High for stiff ODE/DAE + nonlinear solve workloads | New official API is still young/beta in docs | **Medium** | **Best first post-SciPy target** |
| **PETSc + petsc4py (TS/SNES/KSP)** | Medium | Very high for large sparse coupled solves | Large complexity jump; MPI/PETSc mental model | **High** | **Second-stage escalation** |
| **CasADi** | Medium-low | High where symbolic sparsity/Jacobians dominate | Requires reauthoring model logic into CasADi graphs | Medium | **Specialized path, not default** |
| **Julia interop (`juliacall`, `diffeqpy`, direct SciML)** | Medium-low | Very high in best case | Cross-runtime ops/debug/deploy burden | **High** | **Research spike only after Python-native options** |
| **JAX + Diffrax / Optimistix / Lineax** | Low | High only after major refactor to array/JIT style | Weak brownfield fit; DAE story not first-class in retrieved docs | Medium-high | **Not next move** |
| **Assimulo** | Low | Moderate | Conda-first, PyPI outdated, old SUNDIALS basis | **High** | **Do not adopt for new core work** |
| **scikits-odes** | Medium-low | Moderate | Source-only distribution; Python classifiers stop at 3.11 | **Medium-high** | **Only if already proven in CI; otherwise skip** |

## Brownfield Migration Fit

### 1. `sundials4py` — best fit

Why it fits:
- Still Python.
- Still callback/residual oriented.
- Covers the exact problem families this milestone is converging toward: stiff ODEs, DAEs, nonlinear algebraic solves.
- Lets the existing session/runtime facades stay in place while only the kernel adapter changes.

Why it matters here:
- `ProcessModel.step()` currently goes straight through `solve_ivp`.
- Whole-flowsheet or hybrid-coupled solving likely needs **IDA/KINSOL-style** capabilities, not just another `solve_ivp` method choice.
- Official LLNL release notes now say `pip install sundials4py`, with official Python interfaces and zero-copy exchange for DLPack-capable arrays.

Migration shape:
- Keep `PlantBackendSession` and runtime orchestration stable.
- Introduce a `KernelSolver` adapter layer.
- First use case: nonlinear initialization/correction around current coupling.
- Second use case: IDA-backed flowsheet solve.

### 2. petsc4py — powerful but heavy

Why it fits:
- PETSc TS gives time stepping; SNES gives nonlinear solves; KSP/PC give linear solve/preconditioner control.
- Strong telemetry and monitoring surface.
- Good long-term answer if ModularSimulator becomes a genuine sparse equation platform.

Why it does not fit as the first move:
- The complexity tax is real.
- PETSc’s power comes with PETSc’s model: Vec/Mat/KSP/SNES/TS, options databases, solver configuration depth, often MPI assumptions.
- This is more infrastructure than the repo likely wants before proving SUNDIALS is insufficient.

### 3. JAX/Diffrax — poor primary-substrate fit

Why people reach for it:
- JIT, GPU, autodiff, vectorization.

Why it is the wrong next move here:
- Brownfield Python object models and mutable runtime graphs fight JAX’s tracing model.
- Diffrax docs emphasize ODE/SDE/CDE and JAX-native pytrees; the retrieved docs did **not** show first-class DAE positioning comparable to IDA/CVODE/KINSOL.
- Warm-started, bounded, sparse nonlinear solve workflows would require stitching JAX ecosystem tools together and rewriting kernels into array-pure form.

Verdict:
- Excellent for future isolated kernels or differentiable subsystems.
- Not credible as the next primary flowsheet solver substrate.

### 4. Julia interop — real upside, high disruption

Why it is tempting:
- SciML/DifferentialEquations.jl is broad, fast, and mature across stiff ODE/DAE classes.
- `diffeqpy` and `juliacall` make Python entry possible.

Why it is still not the next move:
- You are adding a second language runtime to a game-backend service.
- `juliacall` may auto-download Julia and manage Julia environments; convenient for experimentation, risky for product deployment if left uncontrolled.
- `diffeqpy` explicitly notes limitations: autodiff does not work on Python functions, DAE `de.jit()` is not supported, and best performance often requires defining functions on the Julia side.

Verdict:
- Great benchmarking/control arm.
- Bad first production migration target.

### 5. CasADi — best when symbolic structure becomes the product

Why it is interesting:
- Sparse symbolic graphs, automatic differentiation, rootfinders, DAE/integrator tooling, generated C code.
- Warm starts and initialization workflows can be excellent.

Why it is not the default answer:
- CasADi is explicit that it is **not** a drop-in AD wrapper over existing user code; models must be expressed in CasADi form.
- That means a modeling rewrite, not just a solver swap.

Verdict:
- Worth it if the kernel becomes a residual/Jacobian-centric algebraic platform.
- Too invasive as the first replacement for SciPy.

### 6. Assimulo / scikits-odes — legacy/reference only

**Assimulo**
- README says the recommended install path is conda, PyPI releases are outdated, and compliance targets SUNDIALS 2.7.0.
- That is too far behind to be the new core substrate.

**scikits-odes**
- Still alive and released in 2025.
- But PyPI shows source-only distribution and Python classifiers only through 3.11.
- That makes it a risky Python 3.13 production choice compared with official `sundials4py`.

## Performance Upside / Downside by Family

### `sundials4py`
**Upside:**
- Native stiff ODE/DAE and nonlinear system solvers.
- Strong match for sparse Jacobians, consistent initialization, warm starts, and hybrid-coupled solves.
- Lower rewrite cost than JAX/CasADi/Julia rewrite paths.

**Downside:**
- Newer Python binding surface; fewer battle-tested Python examples than old SciPy paths.
- You still need good residual/Jacobian engineering; SUNDIALS is not magic.

### petsc4py
**Upside:**
- Best ceiling for large sparse nonlinear systems, custom preconditioning, matrix-free formulations, solver composition, and monitors.

**Downside:**
- High setup and expertise burden.
- Easy to overshoot milestone needs.

### JAX/Diffrax
**Upside:**
- Huge wins possible on pure array kernels, batched solves, differentiable simulation.

**Downside:**
- First-call compile latency, tracing constraints, and major data-model rewrite pressure.
- Likely conflicts with realtime interactive backend patterns unless heavily curated.

### Julia interop
**Upside:**
- Very high algorithmic ceiling.
- Broad solver menu and proven stiff/DAE ecosystem.

**Downside:**
- Runtime boundary, packaging, debugging, deployment, and ops complexity become product concerns.

### CasADi
**Upside:**
- Excellent symbolic sparsity and derivative machinery.
- Strong for initialization and nonlinear residual solve pipelines.

**Downside:**
- Model rewrite cost is high.
- More compelling for optimization/control-centric kernels than direct drop-in simulation backend replacement.

## Packaging / Runtime Risk

| Option | Risk | Why |
|---|---|---|
| `sundials4py` | Medium | New official package, but PyPI wheels exist and require Python >=3.12; docs still mark bindings beta. |
| petsc4py | High | PETSc dependency stack, optional MPI complexity, bigger dev/prod surface. |
| JAX/Diffrax | Medium-high | `jax` install is easy on CPU, but runtime semantics/JIT/debug behavior are a major system-level change. |
| Julia interop | High | Second runtime, environment bootstrapping, signal/threading caveats, deployment control needed. |
| CasADi | Medium | Good wheel story for cp313, but large binary dependency and model rewrite cost. |
| Assimulo | High | Conda-first, outdated PyPI, old SUNDIALS target. |
| scikits-odes | Medium-high | Source-only and weaker Python 3.13 support posture. |

## When Each Option Becomes Justified

### Choose `sundials4py` when
- SciPy cannot give stable whole-flowsheet / hybrid-coupled behavior.
- You need real DAE support.
- You need nonlinear initialization and residual correction beyond SciPy’s comfort zone.
- You want to preserve Python and existing facades.

### Choose petsc4py when
- The flowsheet kernel becomes a large sparse nonlinear platform.
- Preconditioners and matrix-free methods decide performance.
- You need solver composition and deep monitoring more than easy adoption.

### Choose CasADi when
- Analytic/symbolic Jacobians are central.
- Consistent initialization and rootfinding become core workload.
- You are willing to represent the model as symbolic residual graphs.

### Choose Julia interop when
- Python-native options lose clearly on representative workloads.
- You can afford a runtime boundary and deployment discipline.
- Benchmark evidence, not taste, justifies the extra language/runtime.

### Choose JAX/Diffrax when
- You are intentionally redesigning around array-pure kernels.
- GPU batch solve throughput or differentiability is the main value.
- DAE-heavy whole-flowsheet solving is not the core requirement.

## Bottom-Line Recommendation

For this milestone, the realistic stack sequence is:

1. **Instrument and de-risk the kernel seam while still on SciPy**
2. **Prototype `sundials4py` as the first real alternative primary substrate**
3. **Escalate to petsc4py only if sparse coupled solves clearly demand PETSc-level machinery**
4. **Use CasADi or Julia only for specialized or evidence-backed follow-on directions**
5. **Do not bet milestone v1.0 on JAX/Diffrax, Assimulo, or scikits-odes**

If the question is "what replaces SciPy first?" the answer is **official SUNDIALS (`sundials4py`)**.

If the question is "what is the highest-ceiling long-term substrate?" the answer is **PETSc**, but only once the project proves it needs PETSc-sized complexity.

## Repo Context Used

- `src/modular_simulation/measurables/process_model.py` — `ProcessModel.step()` currently uses `scipy.integrate.solve_ivp`
- `src/modular_simulation/framework/system.py` — default solver config still falls back to `{"method": "LSODA"}`
- `src/modular_simulation/connection/hydraulics/hydraulic_solver.py` — sparse Jacobian structure is assembled but densified before `np.linalg.solve`
- `src/modular_simulation/cli/backend_session.py` — stable session facade worth preserving through kernel migration

## Sources

- SciPy docs: `solve_ivp`, `BDF`, `Radau`, `least_squares`, sparse Jacobian support (HIGH)  
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html
- Official SUNDIALS Python docs (`sundials4py` beta, official bindings) (HIGH)  
  https://sundials.readthedocs.io/en/latest/Python/index.html
- LLNL SUNDIALS release page (`pip install sundials4py`, official Python interfaces, Jan 2026) (HIGH)  
  https://computing.llnl.gov/projects/sundials/sundials-software
- PyPI `sundials4py` 7.6.0 (Python >=3.12, wheel availability) (HIGH)  
  https://pypi.org/project/sundials4py/
- PETSc TS docs (ODE/DAE, SNES integration, monitors) (HIGH)  
  https://petsc.org/manualpages/TS/
- PETSc SNES docs (Newton/quasi-Newton/VI/monitoring options) (HIGH)  
  https://petsc.org/manualpages/SNES/
- petsc4py docs + install docs (HIGH)  
  https://petsc.org/release/petsc4py/  
  https://petsc.org/release/petsc4py/install.html
- JAX installation docs (platform/runtime constraints) (HIGH)  
  https://docs.jax.dev/en/latest/installation.html
- Diffrax docs / README / PyPI (JAX ODE/SDE/CDE focus, package status) (MEDIUM-HIGH)  
  https://docs.kidger.site/diffrax/  
  https://pypi.org/project/diffrax/
- JuliaCall docs (auto-download Julia, threading/signal caveats) (HIGH)  
  https://juliapy.github.io/PythonCall.jl/dev/juliacall/
- DifferentialEquations.jl docs + diffeqpy README/PyPI (Python interop, capabilities, limitations) (MEDIUM-HIGH)  
  https://docs.sciml.ai/DiffEqDocs/stable/  
  https://github.com/SciML/diffeqpy  
  https://pypi.org/project/diffeqpy/
- CasADi docs + PyPI (symbolic rewrite implications, rootfinder/integrator tooling, cp313 wheels) (HIGH)  
  https://web.casadi.org/docs/  
  https://pypi.org/project/casadi/
- Assimulo README (conda recommended, PyPI outdated, old SUNDIALS target) (MEDIUM-HIGH)  
  https://github.com/modelon-community/Assimulo
- scikits-odes PyPI (source-only, Python classifiers through 3.11) (MEDIUM-HIGH)  
  https://pypi.org/project/scikits-odes/
