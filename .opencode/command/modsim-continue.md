---
description: Create the next ready artifact for an existing modsim change.
agent: planner
---

Continue working on an existing OpenSpec change by creating the next ready artifact.

**Input**: Optionally specify a change name after `/modsim-continue` (for example `/modsim-continue add-auth`). If omitted and multiple active changes exist, ask the user to choose with the `question` tool.

---

## `/modsim-continue` Flow

1. **Resolve the target change**
   - If no change name is provided, run `openspec list --json`.
   - Present the most relevant active changes with schema, completion status, and recency.
   - Do not guess when multiple candidates exist.

2. **Check current status**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the schema, artifact statuses, and completion state.

3. **Act on the next ready artifact**
   - If all artifacts are complete, say so and suggest:
     - `modsim-apply` if execution linkage is ready
     - `modsim-propose` if Beads linkage needs refresh
   - If one or more artifacts are `ready`, take the first ready artifact and fetch its instructions:
     ```bash
     openspec instructions <artifact-id> --change "<name>" --json
     ```
   - Read completed dependency artifacts first.
   - Use the provided template and instruction guidance.
   - Treat `context` and `rules` as constraints only; do not copy them into the artifact.
   - Stop after creating or updating one artifact.

4. **Show updated progress**
   ```bash
   openspec status --change "<name>"
   ```
   Report:
   - artifact created or updated
   - current completion state
   - what is now unlocked
   - next recommended command

**Guardrails**

- Create one artifact per invocation.
- Never skip dependency order.
- Ask only when missing information materially changes the artifact.
- Verify the artifact exists before reporting success.

Use the `question` tool only when change selection is ambiguous or missing information materially changes the artifact.
