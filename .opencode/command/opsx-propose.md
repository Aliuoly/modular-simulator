---
description: Create OpenSpec artifacts for stable, implementation-ready work
agent: hybrid-planner
---

Use this command when the request is already clear enough to define a stable contract.

If the request is still fuzzy, do not guess. Say:
> "This sounds early-stage. Let's use `/opsx-goal` first to capture the overall goal and do discovery in Beads before creating OpenSpec artifacts."

**Input**

The argument after `/opsx-propose` can be:
- A change name (`kebab-case`), or
- A clear problem statement with stable scope.

**Routing rule (required)**

Before creating artifacts, classify the request:

- **Stable**: scope, intent, and near-term outcomes are clear enough to write proposal/spec/design/tasks now.
  - Continue with `/opsx-propose` flow below.
- **Fuzzy**: open questions, unresolved tradeoffs, unclear boundaries, or missing success criteria.
  - Redirect to `/opsx-goal` or ask permission to run that flow now.

Never treat `/opsx-propose` as default intake for vague work.

---

## `/opsx-propose` flow (stable requests only)

1. **Resolve target change name**
   - If a valid change name is provided, use it.
   - If input is descriptive but clear, derive a concise kebab-case name.
   - If a change with that name already exists, ask whether to continue it or create a new name.

2. **Create or reuse the OpenSpec change container**
   ```bash
   openspec new change "<name>"
   ```
   If it already exists and the user chose reuse, continue in that directory.

3. **Get schema status and apply requirements**
   ```bash
   openspec status --change "<name>" --json
   ```
   Use the JSON output to determine artifact dependencies and apply-ready requirements.

4. **Generate artifacts in dependency order until apply-ready**
   For each artifact with dependencies satisfied:
   ```bash
   openspec instructions <artifact-id> --change "<name>" --json
   ```
   - Read completed dependency artifacts first.
   - Use `template` for structure.
   - Follow `instruction` guidance.
   - Treat `context` and `rules` as constraints only; never copy them into artifact content.
   - Re-check status after each artifact and stop once all `applyRequires` artifacts are done.

5. **Show completion state**
   ```bash
   openspec status --change "<name>"
   ```
   Report what was created and confirm implementation readiness.

**Output**

- Change name and path
- Artifacts created
- Readiness statement: "Ready for implementation with `/opsx-apply`"

**Guardrails**

- Keep scope tight to the stable contract; do not expand scope during artifact creation.
- Ask clarifying questions only when needed to resolve blocking ambiguity.
- If new uncertainty appears that changes scope materially, pause and offer `/opsx-goal`.
