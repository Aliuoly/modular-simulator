---
name: writing-tests-for-simulations
description: Use when writing tests for dynamic simulation, scientific computing, numerical solvers, or stateful process models, especially when exact transient sample assertions are not the right first specification. Do not use as the primary testing guide for ordinary CRUD, API, UI, serialization, or other non-simulation code, or for simple exact input/output behavior with no meaningful dynamics. Write tests using contracts, invariants, and step-response expectations before implementation, then add validation and regression only when appropriate.
license: MIT
compatibility: Best for repos with dynamic simulation, scientific computing, numerical solvers, or stateful process models.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: testing
---

Write tests for simulation code by specifying structure, physical rules, and expected causal behavior before implementation. Prefer tests that describe what must exist, what must remain physically admissible, and how the model should respond to perturbations.

**Core idea**

For simulation work, write tests in layers:

1. `Contract tests` define what surfaces must exist.
2. `Invariant tests` define what must always remain true.
3. `Step-response tests` define what should respond to what, in what direction, and on what time scale.
4. `Validation tests` compare against an external reference when one exists.
5. `Regression tests` preserve accepted behavior after implementation stabilizes.

Start with the first three layers for red-wave TDD.

## 1. Contract Tests

Use contract tests to freeze required simulation-facing interfaces before implementation.

**Do**:
- assert required state variables exist
- assert required boundary inputs and outputs exist
- assert required callbacks, hooks, or observability fields exist
- assert state shape and indexing semantics are explicit
- assert failure behavior is explicit when inputs are invalid or unsupported

**Do not**:
- hide contract expectations inside large numerical tests
- mix interface existence checks with long transient runs unless the runtime path itself is the contract

**How to write them**:
- instantiate the model with a minimal valid configuration
- assert the expected fields, ports, and methods are present
- assert array sizes and state names are correct
- assert unsupported configurations fail loudly and specifically

**Conceptual example**:

```python
def test_column_exposes_required_boundary_inputs():
    model = DistillationColumn(n_species=3, n_trays=8)
    assert hasattr(model, "reflux_request")
    assert hasattr(model, "reboiler_duty_request")
    assert hasattr(model, "apply_inlet")
```

## 2. Invariant Tests

Use invariant tests to define physical and numerical rules that must hold throughout the simulation.

**Do**:
- test non-negativity for conserved inventories that cannot go negative
- test conservation or balance identities that are structural to the model
- test composition normalization when composition is meant to remain normalized
- test finiteness of temperatures, pressures, holdups, and flows inside the supported operating envelope
- test realizability guards when the model can be over-requested by the runtime
- test bounded acceptance rules for fallback or near-empty behavior

**Do not**:
- require exact trajectories when the real requirement is physical admissibility
- check only the final state when the invariant should hold over the entire transient

**How to write them**:
- run one or more steps under representative operating conditions
- inspect the full relevant state, not only one output stream
- make the invariant explicit in the assertion message
- if the invariant is step-local, check after each step in a short rollout

**Conceptual example**:

```python
def test_inventory_never_steps_negative_under_requested_withdrawal():
    model = HoldingTank(...)
    for _ in range(10):
        model.apply_requested_outlet_through_flow_demand("outlet", 5.0)
        model.step(0.1)
        assert np.all(model.holdup_component_moles >= 0.0)
```

## 3. Step-Response Tests

Use step-response tests to specify expected causal behavior before the implementation details are fixed.

These tests answer:
- which states should respond to a boundary or parameter change
- which states should not materially respond
- whether the response should be positive, negative, delayed, immediate, monotone, oscillatory, saturating, or multi-timescale
- whether the response remains physically admissible while it evolves

**Do**:
- define the perturbed input clearly
- define the observation window and sampling rate clearly
- define which states or outputs must respond
- define the expected sign or ordering of responses where known
- define acceptable lag or dead-time expectations where known
- check that the response remains finite and physically admissible
- repeat the same test at a finer `dt` or denser sampling if shape interpretation depends on resolution

**Do not**:
- over-specify exact sample values when only qualitative behavior is known
- confuse a coarse sampled trace with the real underlying response shape
- observe only one output when the coupling expectation is about several states

**How to write them**:
- prepare a steady or controlled initial condition
- record a pre-step baseline for the states of interest
- apply one perturbation
- advance for a fixed horizon
- assert influence, sign, timing, and admissibility
- if needed, rerun with smaller `dt` to distinguish physics from resolution artifacts

**Conceptual example**:

```python
def test_reboiler_duty_step_increases_bottom_vapor_generation():
    model = Column(...)
    baseline = measure_boilup(model)

    model.reboiler_duty_request = model.reboiler_duty_request + 5000.0
    trace = []
    for _ in range(20):
        model.step(0.1)
        trace.append(measure_boilup(model))

    assert max(trace) > baseline
    assert np.all(np.isfinite(trace))
```

**Common step-response checks**:
- `influence`: response exists in the expected states
- `isolation`: unaffected states stay materially unchanged
- `sign`: response direction is correct
- `timing`: immediate response vs delayed response is correct
- `ordering`: one state responds before another when the model implies that order
- `smoothness`: the trace shape is reasonable at the chosen resolution
- `physical admissibility`: no negative inventory, invalid composition, or non-finite state during the response

## 4. Validation Tests

Use validation tests when a trusted external reference exists.

References may include:
- analytical solutions
- benchmark problems
- accepted literature examples
- higher-fidelity offline models
- plant or experiment data

**Do**:
- compare using tolerances or error metrics that match the purpose of the model
- check terminal error, RMSE, max error, trend agreement, or event timing as appropriate
- keep the reference source explicit in the test or fixture setup

**Do not**:
- require a validation reference for every new simulation feature before writing any tests
- use validation as a replacement for contract, invariant, or step-response tests

**How to write them**:
- make the simulation and reference share the same initial conditions and forcing
- compare only the quantities that the current model is supposed to represent
- use tolerances that reflect model intent, not machine precision by default

## 5. Regression Tests

Use regression tests after the implementation produces accepted behavior you want to preserve.

**Do**:
- snapshot accepted traces, summary metrics, or event timings
- keep tolerances explicit
- store only the amount of reference data needed to detect meaningful drift

**Do not**:
- use regression snapshots as the first and only specification for a new model
- let regression traces replace physical invariants

**How to write them**:
- capture a compact accepted signature such as final values, peak values, settling time, or selected trace samples
- compare with explicit tolerances
- pair regression with at least one invariant or admissibility check

## Choosing The Test Type

Use this rule of thumb:

- if the question is `what must exist?` write a contract test
- if the question is `what must never be violated?` write an invariant test
- if the question is `what should respond to what?` write a step-response test
- if the question is `does this match a trusted reference?` write a validation test
- if the question is `did accepted behavior drift?` write a regression test

## Workflow

When writing tests for a new simulation feature:

1. List the required state, boundary, and observability surfaces.
2. List the physical and numerical invariants.
3. List the expected causal step responses.
4. Write red tests for contracts, invariants, and step response first.
5. Implement the model.
6. Add validation tests when a trusted reference exists.
7. Add regression tests once the behavior is accepted.

## Practical Do / Don't Summary

**Do**:
- describe causal expectations clearly
- test invariants over a rollout, not only at the end
- use tolerances and error metrics that match the model purpose
- inspect multiple states when the physics couples them
- make time horizon and `dt` part of the test specification
- tighten resolution before drawing conclusions from rough trace shapes

**Do not**:
- start with exact transient sample assertions when the model behavior is not yet frozen
- let one outlet signal stand in for the whole physical state
- use only final-state assertions for dynamic behavior
- combine interface checks, invariants, and validation into one giant test
- assume a jagged trace is physical without checking resolution and admissibility

## Output Expectations For Agents Using This Skill

When this skill is used, the agent should:
- identify which test layer is appropriate for each requested behavior
- write red tests for contracts, invariants, and step response first when doing simulation TDD
- add validation or regression only when the task or evidence makes them appropriate
- explain the chosen test type briefly in terms of behavior, admissibility, and causality
