# Simulation Advisor Design

## Goal

Add a repo-local OpenCode specialist that reviews plans and implementation for simulation realism, named engineering heuristics, and educational transfer value, then wire it into the existing hybrid planning and execution workflow.

## Scope

In scope:
- a standalone read-only agent for realism review and named-correlation guidance
- planner and orchestrator workflow updates so the specialist is used in the right review phases
- explicit guidance on named equations, empirical correlations, and accepted heuristics

Out of scope:
- adding new simulation models or changing runtime simulation behavior
- introducing a multi-agent thermo/fluids/chemistry panel
- requiring maximum-fidelity plant simulation

## Recommended Approach

Create a standalone `simulation-advisor` subagent instead of folding realism review into `hybrid-code-reviewer`.

This keeps code-quality review separate from domain-realism review while still letting the orchestrator synthesize both results. It also matches GPT-5.4-led manager/specialist guidance: use compact, bounded specialists with clear output contracts and run them in parallel when the work is independently reviewable.

## Review Philosophy

- optimize for transferable engineering truth, not maximum fidelity
- accept simplifications when they preserve first-order balances, constraints, controllability, and optimization incentives
- block materially misleading simplifications before work continues
- allow softer realism debt only when the current result remains educationally honest
- never emit a `Speculative` category; guidance must be `Canonical`, `Accepted heuristic`, or `Unacceptable`

## Advisor Responsibilities

The agent should:

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

- `hybrid-planner` should be allowed to call `simulation-advisor`
- for plans affecting simulation behavior, unit-operation semantics, thermodynamics, fluids or flow behavior, chemistry, controls, named engineering heuristics/correlations, or rough engineering economics/CAPEX, `hybrid-planner` should invoke `hybrid-plan-reviewer` and `simulation-advisor` in parallel before declaring the pack ready
- both reviewers should receive the same relevant artifact excerpts and review scope
- `tasks.md` should encode the downstream execution gate that requires parallel realism and code review when the implementation touches simulation semantics or engineering economics

### Implementation Review

- `hybrid-orchestrator` should be allowed to call `simulation-advisor`
- any implementation wave affecting simulation behavior, unit-operation semantics, thermodynamics, fluids or flow behavior, chemistry, controls, named engineering heuristics/correlations, or rough engineering economics/CAPEX should be sent to `hybrid-code-reviewer` and `simulation-advisor` in parallel
- both reviewers should receive the same bounded packet, diff scope, and verification evidence
- either review may block closure

## Output Contract

The advisor should return:

1. `VERDICT`
2. `Transfer assessment`
3. `What stays realistic`
4. `Unacceptable issues`
5. `Accepted heuristics and named correlations`
6. `Deferred realism debt`
7. `Beads follow-ups`
8. `Next action`

This keeps the review compact and directly actionable for GPT-5.4 manager-style orchestration.

## Files To Update

- `.opencode/agents/simulation-advisor.md` - new realism-review specialist prompt
- `.opencode/agents/hybrid-planner.md` - planning-stage integration and naming guidance
- `.opencode/agents/hybrid-orchestrator.md` - parallel implementation-review integration
- `AGENTS.md` - repo-level workflow guidance and naming convention reminder
