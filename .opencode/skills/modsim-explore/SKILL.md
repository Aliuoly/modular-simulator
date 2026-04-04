---
name: modsim-explore
description: Explore ideas, investigate problems, and clarify requirements in the Modsim OpenSpec plus Beads workflow without implementing code.
license: MIT
compatibility: Requires the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: modsim-contract
---

Explore the user's topic without implementing application code.

**Input**: A vague idea, a specific problem, a change name, a comparison, or no additional input.

**Steps**

1. Run `openspec list --json` to identify active changes and available context.
2. Read repo files, docs, and relevant code before giving recommendations.
3. If the user named a change or a relevant active change exists, read:
   - `proposal.md`
   - `specs/**/*.md`
   - `design.md`
   - `tasks.md`
   - `beads-identity.md` when present
4. Build the analysis with concrete trade-offs, file references, ASCII diagrams, and comparison tables when they help.
5. Surface options, risks, unknowns, and integration points.
6. Offer artifact capture only when the user explicitly wants to record an insight.
7. Suggest `modsim-propose` only when the scope is stable enough for a full change pack or when the user asks to formalize the work.

**Capture Map**

| Insight Type | File |
|--------------|------|
| New requirement | `specs/<capability>/spec.md` |
| Requirement change | `specs/<capability>/spec.md` |
| Design decision | `design.md` |
| Scope change | `proposal.md` |
| New planning work | `tasks.md` |
| Execution linkage clarification | `beads-identity.md` |

**Output**

Provide:
- `Problem:` current understanding
- `Options:` concrete paths or interpretations
- `Risks:` key unknowns and failure points
- `Next action:` one or more valid follow-up moves

**Guardrails**

- Never implement application code in explore mode.
- Never auto-create or auto-update artifacts.
- Ask focused questions only when the answer changes the analysis.
- Use repo evidence first. Use official docs or external evidence when repo evidence is not enough.
