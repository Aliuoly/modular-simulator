---
description: Explore ideas, investigate problems, and clarify requirements without implementing.
---

Investigate the user's topic without implementing application code.

**IMPORTANT:** Explore mode is analysis only. Read files, search code, inspect OpenSpec changes, and research external sources when needed. Do not implement features or write application code. If the user wants implementation, tell them to leave explore mode and use `modsim-propose` or `modsim-apply`.

**Input**: The argument after `/modsim-explore` can be a vague idea, a specific problem, a change name, a comparison, or nothing.

---

## Core Behavior

- Read repo evidence before making claims.
- Use ASCII diagrams, comparison tables, and concrete trade-offs when they clarify the answer.
- Ask focused questions only when the answer materially changes the analysis.
- Surface more than one path when the problem has real options.
- Keep the discussion grounded in actual files, specs, and research.

---

## Exploration Actions

Depending on the topic, do one or more of these:

**Problem exploration**
- identify the real decision
- challenge assumptions
- reframe the problem
- compare alternative goals or scopes

**Codebase investigation**
- map relevant architecture
- find integration points
- identify existing patterns
- trace hidden complexity or coupling

**Option comparison**
- compare approaches
- build trade-off tables
- identify risks and unknowns
- recommend a path when the user asks for one

**Visualization**
```text
┌─────────────────────────────────────────┐
│     Use ASCII diagrams when useful      │
├─────────────────────────────────────────┤
│                                         │
│   ┌────────┐         ┌────────┐        │
│   │ State  │────────▶│ State  │        │
│   │   A    │         │   B    │        │
│   └────────┘         └────────┘        │
│                                         │
│   System diagrams, state machines,      │
│   data flows, architecture sketches,    │
│   dependency graphs, comparison tables  │
│                                         │
└─────────────────────────────────────────┘
```

---

## OpenSpec And Beads Context

1. Start with:
   ```bash
   openspec list --json
   ```
2. If the user named a change, or an active change is clearly relevant, read its artifacts:
   - `openspec/changes/<name>/proposal.md`
   - `openspec/changes/<name>/specs/**/*.md`
   - `openspec/changes/<name>/design.md`
   - `openspec/changes/<name>/tasks.md`
   - `openspec/changes/<name>/beads-identity.md` when present
3. Treat `tasks.md` as planning context.
4. Treat `beads-identity.md` as the execution-linkage record.
5. Offer artifact updates only after the user confirms they want the insight captured.
6. If exploration settles governing equations, closures, correlations, or state definitions that materially define behavior, keep them visible in the analysis and recommend capture into the changepack instead of letting them disappear into prose.

### Capture Map

| Insight Type | Where To Capture |
|--------------|------------------|
| New requirement discovered | `specs/<capability>/spec.md` |
| Requirement changed | `specs/<capability>/spec.md` |
| Governing equations or model closure | `specs/<capability>/spec.md` and `design.md` |
| Design decision made | `design.md` |
| Scope changed | `proposal.md` |
| New implementation work identified | `tasks.md` |
| Execution linkage clarified | `beads-identity.md` |
| Assumption invalidated | relevant artifact |

Example offers:
- `That's a design decision. Capture it in design.md?`
- `This is a new requirement. Add it to specs?`
- `This changes scope. Update the proposal?`
- `This changes the execution mapping. Update beads-identity.md?`

---

## When To Suggest The Next Phase

- Suggest `modsim-propose` only when the scope is stable enough for a full change pack.
- Suggest artifact updates only when the user wants to record a decision.
- Stay in exploration if the problem is still moving or the user is still comparing options.

---

## Output

When useful, summarize with:

```text
## What We Figured Out

**Problem:** [current understanding]

**Options:** [concrete paths]

**Risks:** [key unknowns or failure points]

**Next steps:**
- keep exploring
- create a change pack with modsim-propose
- update an existing artifact
```

Use the `question` tool only when a focused answer materially changes the analysis.

---

## Guardrails

- Never implement application code in explore mode.
- Do not fake understanding.
- Do not route to `modsim-propose` until the user asks or the scope is clearly stable.
- Do not auto-capture insights into artifacts.
- Use repo evidence first. Use official docs and external evidence when needed.
