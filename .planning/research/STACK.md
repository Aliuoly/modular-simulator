# Stack Research

**Domain:** Backend simulation kernel stability for complex flowsheets
**Researched:** 2026-03-29
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.13.x | Keep the existing simulation/runtime substrate | The repo already targets Python 3.13, and the right move for this milestone is kernel stabilization inside the current backend, not a language/runtime migration. |
| SciPy integrate (`solve_ivp` with `BDF` and `Radau`) | 1.17.x | Primary stiff ODE stepping for unit models and early global-kernel prototypes | Current code already steps process models through `solve_ivp` (`src/modular_simulation/measurables/process_model.py`). SciPy documents `BDF` and `Radau` as the stiff methods and supports explicit Jacobians plus sparse Jacobian handling, which is the lowest-migration path from the current `LSODA` default. |
| SciPy sparse + sparse linear algebra (`scipy.sparse`, `scipy.sparse.linalg`) | 1.17.x | Sparse Jacobian assembly and Newton linear solves for hydraulics / coupled flowsheet residuals | The current hydraulic solver already assembles a sparse triplet but immediately densifies and calls `np.linalg.solve` (`src/modular_simulation/connection/hydraulics/hydraulic_solver.py`). Keeping the sparse structure and solving with `spsolve`/`splu` is the clearest stack upgrade for larger flowsheets. |
| SciPy optimize (`least_squares`, `Bounds`) | 1.17.x | Bounded nonlinear residual solve, consistent initialization, and fallback correction passes | `least_squares(method="trf")` supports bounds, sparse Jacobians, and large problems. That matters for non-physical states like negative inventories or invalid port states during coupled solves. Use it for algebraic/coupling residual solves before reaching for a new solver ecosystem. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Numba | 0.64.x | JIT residual/Jacobian hot paths after profiling | Numba 0.64 supports Python <3.15. Use it only for pure numeric kernels such as residual assembly, transport kernels, and analytic Jacobian fills after the coupled kernel shape is stable. |
| `pytest-benchmark` | 5.1.x | Realtime-budget regression tracking | Add this when comparing split micro/macro stepping vs flowsheet-wide coupled stepping. Tie benchmarks to representative flowsheets and per-tick budgets, not just raw solver iteration counts. |
| `sundials4py` | 7.6.0 beta | Optional research spike for true DAE / IDA evaluation | Use only behind an adapter if whole-flowsheet coupled solving proves to be a genuine DAE problem that SciPy ODE + algebraic correction cannot handle robustly. It is worth investigating because it is the official SUNDIALS Python binding, but the binding is still beta, so it should not be the first migration target. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Solver telemetry in existing runtime | Record `nfev`, `njev`, `nlu`, residual norms, damping counts, Picard/Newton iterations | Expose these through the current runtime/orchestrator boundary instead of adding a separate observability stack first. This is the fastest way to compare candidate kernels without disturbing `PlantBackendSession` or gameplay APIs. |
| Deterministic benchmark harnesses | Compare stability and tick cost across canonical flowsheets | Replace the current placeholder macro benchmark with real benchmark fixtures covering recycles, pressure coupling, inventory constraints, and controller interaction. |

## Installation

```bash
# Core numerical stack (pin, do not leave floating)
pip install "scipy>=1.17,<1.18"

# Supporting
pip install "numba>=0.64,<0.65"

# Dev dependencies
pip install -D "pytest-benchmark>=5.1,<6"

# Optional research spike only
pip install "sundials4py==7.6.0"
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| SciPy `BDF`/`Radau` as the first coupled-kernel investigation path | Stay on `LSODA` everywhere | Keep `LSODA` for legacy/simple unit stepping, but not as the main research path for complex flowsheets. The current default in `src/modular_simulation/framework/system.py` is fine for today’s unit stepping, but it does not address the main milestone need: explicit control over stiff coupling, Jacobians, and sparsity. |
| `scipy.optimize.least_squares(method="trf")` for bounded coupled residual solves | `scipy.optimize.root` | Use `root` only for small, unconstrained square solves with good initial guesses. For this milestone, bounds and sparse structure matter more than pure root-finding convenience. |
| SciPy sparse direct solves (`spsolve`/`splu`) | Dense `np.linalg.solve` | Keep dense solves only for tiny systems or debugging. Once the global residual spans many units and ports, dense factorization becomes the unnecessary bottleneck. |
| `sundials4py` research spike | `scikits-odes` | Prefer `scikits-odes` only if the team already has it running in CI on Python 3.13. PyPI currently shows `scikits-odes` 3.1.1 as source-only and only classifies Python support through 3.11, so it is a riskier adoption path for this repo. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Keeping the hydraulic/coupled Newton path dense | The repo already has sparse Jacobian structure, but densifies it before solving. That throws away the exact scaling advantage needed for larger flowsheets. | Keep Jacobians sparse end-to-end with `csr`/`csc` matrices and `spsolve`/`splu`. |
| Making `sundials4py` the immediate production kernel | The official binding is promising, but SUNDIALS documents it as beta. Jumping straight to it adds native dependency and adapter complexity before proving that SciPy-based coupling is insufficient. | First build a SciPy-based global residual/Jacobian path; only escalate to IDA/CVODE if the problem is clearly DAE-dominated. |
| Adopting `scikits-odes` as the default DAE stack | Current PyPI metadata is weaker for Python 3.13-era adoption in this repo: source distribution only and Python classifiers stop at 3.11. | If a DAE solver is required, prefer an isolated `sundials4py` feasibility branch or stay in SciPy for the first migration wave. |
| Rewriting the kernel around JAX/Diffrax/CasADi first | That would force a much larger data-model and runtime rewrite than this milestone needs, especially given the existing object-oriented process models, connection runtime, and session/gameplay facades. | Keep the Python/SciPy architecture and introduce residual assembly, sparse Jacobians, and profiling-guided JIT only where needed. |

## Stack Patterns by Variant

**If the project keeps split micro/macro stepping for the next phase:**
- Keep `ProcessModel.step()` on SciPy, but switch research cases from default `LSODA` toward `BDF`/`Radau` and add Jacobian/Jacobian-sparsity support.
- Upgrade `MacroCoupler` stabilization (`src/modular_simulation/connection/runtime/connection_layer.py`) from Picard-only gating into a monitored Picard/Newton-style correction pass with bounded residual solves for port conditions and inventories.
- Replace dense hydraulic Newton linear solves with sparse solves in `src/modular_simulation/connection/hydraulics/hydraulic_solver.py`.
- Because this path minimizes migration cost while directly attacking stale-coupling failures.

**If the project moves toward a flowsheet-wide coupled solve:**
- Introduce a global state vector plus residual/Jacobian assembler spanning differential states, hydraulic unknowns, and algebraic coupling variables.
- Use SciPy `least_squares` for bounded consistent-initialization / algebraic correction and SciPy `BDF` or `Radau` for time advancement around that assembled system.
- Keep `PlantBackendSession`, gameplay services, and HTTP API stable by swapping only the simulation kernel behind the current runtime facade.
- Because this gives the strongest path to physical consistency without immediately paying the cost of a native-solver rewrite.

**If research proves the problem is truly DAE-first rather than stiff-ODE-plus-correction:**
- Prototype an adapter around `sundials4py` IDA on a narrow benchmark set only.
- Require proof that it materially improves both stability and realtime tick cost on representative complex flowsheets before wider adoption.
- Because a DAE solver should be an evidence-backed escalation, not the default first move.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.13.x | Numba 0.64.x | Numba docs list Python support for versions `<3.15`, making it viable for this repo’s current Python target. |
| SciPy 1.17.x `solve_ivp` | Sparse Jacobians for `BDF`/`Radau` | SciPy docs explicitly support callable/sparse Jacobians and `jac_sparsity`, which is the key integration hook for a coupled kernel. |
| SciPy 1.17.x `least_squares` | Sparse Jacobians + bounds | `least_squares(method="trf")` supports sparse Jacobians and `Bounds`, useful for coupled residual correction and feasibility enforcement. |
| `sundials4py` 7.6.0 | SUNDIALS 7.6.x beta Python API | Treat as adapter-isolated experimental infrastructure, not baseline production dependency. |
| `scikits-odes` 3.1.1 | Python 3.11-classified / source-only distribution | This is the compatibility warning that argues against making it the default path for a Python 3.13 backend. |

## Sources

- `/websites/scipy_doc_scipy` — verified `solve_ivp`, `BDF`, `LSODA`, `least_squares`, `Bounds`, and sparse linear algebra behavior (HIGH)
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html — stiff ODE method guidance and Jacobian support (HIGH)
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.BDF.html — sparse Jacobian support for BDF (HIGH)
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.LSODA.html — current LSODA behavior and limitations versus explicit stiff-method selection (HIGH)
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html — bounded sparse nonlinear solve support (HIGH)
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.Bounds.html — feasibility bounds for correction solves (HIGH)
- https://docs.scipy.org/doc/scipy/reference/sparse.linalg.html — sparse direct/iterative linear solver options (HIGH)
- https://numba.readthedocs.io/en/stable/user/installing.html — Python 3.13 compatibility for Numba 0.64.x (HIGH)
- https://sundials.readthedocs.io/en/latest/ida/Introduction_link.html — IDA capabilities for DAE systems and solver structure (HIGH)
- https://sundials.readthedocs.io/en/latest/Python/index.html — official `sundials4py` Python bindings are available but beta (HIGH)
- https://pypi.org/project/scikits-odes/ — `scikits-odes` 3.1.1 packaging/status details used for adoption-risk assessment (MEDIUM)
- Repo integration points: `src/modular_simulation/measurables/process_model.py`, `src/modular_simulation/framework/system.py`, `src/modular_simulation/connection/hydraulics/hydraulic_solver.py`, `src/modular_simulation/connection/runtime/connection_layer.py`, `src/modular_simulation/cli/backend_session.py` (HIGH)

---
*Stack research for: backend simulation kernel stability for complex flowsheets*
*Researched: 2026-03-29*
