# Simulation Advisor Design (retired approach)

## Goal

This note records the retired standalone advisor approach. The active workflow now merges simulation-realism review into `hybrid-code-reviewer` behind the `simulation-realism-required` task-packet flag.

## Scope

In scope:
- merged realism review guidance inside `hybrid-code-reviewer`
- planner and orchestrator workflow updates for the `simulation-realism-required` flag
- explicit guidance on named equations, empirical correlations, and accepted heuristics

Out of scope:
- adding new simulation models or changing runtime simulation behavior
- introducing a multi-agent thermo/fluids/chemistry panel
- requiring maximum-fidelity plant simulation

## Recommended Approach

Fold realism review into `hybrid-code-reviewer` and gate it with `simulation-realism-required: true` only when the task packet demands it.

This keeps the live review surface compact while preserving the ability to require realism review for simulation-affecting work.

## Review Philosophy

- optimize for transferable engineering truth, not maximum fidelity
- accept simplifications when they preserve first-order balances, constraints, controllability, and optimization incentives
- block materially misleading simplifications before work continues
- allow softer realism debt only when the current result remains educationally honest
- never emit a `Speculative` category; guidance must be `Canonical`, `Accepted heuristic`, or `Unacceptable`

## Reviewer Responsibilities

When the flag is true, the reviewer should:

1. review plans, prompts, specs, and code for physical, thermodynamic, fluid-dynamic, chemistry, controls, and rough-CAPEX realism
2. suggest accepted shortcut models when they preserve the intended educational tradeoffs
3. provide named engineering rules or empirical correlations when they materially improve realism or review quality
4. enforce naming and provenance so the repo refers to real rules by name rather than generic placeholders
5. surface non-blocking realism debt as concrete Beads follow-up suggestions

## Equation And Heuristic Policy

- If a model or estimate uses a known relation, the prompt, spec, code, or tests should name it directly.
- Generic names like `generic_scaling_law` are discouraged when the implementation is really a named rule.
- The advisor should prefer relations future contributors can look up and reason about.
- For each accepted relation, the advisor should identify:
  - the method or correlation name
  - whether it is `Canonical` or `Accepted heuristic`
  - the variables it depends on
  - the key regime or validity assumptions
  - why it is adequate for the repo's educational or gameplay purpose

## Workflow Integration

### Planning

- `hybrid-planner` should encode `simulation-realism-required: true` for plans affecting simulation behavior, unit-operation semantics, thermodynamics, fluids or flow behavior, chemistry, controls, named engineering heuristics/correlations, or rough engineering economics/CAPEX
- `tasks.md` should encode the downstream execution gate that requires the flag and merged realism/code review when the implementation touches simulation semantics or engineering economics

### Implementation Review

- `hybrid-orchestrator` should pass `simulation-realism-required: true|false` to `hybrid-code-reviewer`
- any implementation wave with the flag set true should not close until the reviewer has covered realism, spec compliance, and code quality
- the reviewer should receive the same bounded packet, diff scope, verification evidence, and flag value
- the reviewer may block closure

## Historical Output Notes

This section is retired guidance from the standalone advisor design and does not define the live `hybrid-code-reviewer` contract.

- The live reviewer format is owned by `.opencode/agents/hybrid-code-reviewer.md`.
- Do not treat the list below as authoritative for current output.

Historical output sketch: retired alongside the standalone advisor and intentionally omitted here to avoid defining a second live contract.

## Files To Update

- `.opencode/agents/simulation-advisor.md` - retired standalone path
- `.opencode/agents/hybrid-planner.md` - planning-stage integration and naming guidance
- `.opencode/agents/hybrid-orchestrator.md` - parallel implementation-review integration
- `AGENTS.md` - repo-level workflow guidance and naming convention reminder
