---
description: Continue working on a change by creating the next artifact
agent: hybrid-planner
---

Continue working on an existing OpenSpec change by creating the next ready artifact.

**Input**: Optionally specify a change name after `/opsx-continue` (for example `/opsx-continue add-auth`). If omitted and multiple active changes exist, ask the user to choose.

**Steps**

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
   - If all artifacts are complete, say so and suggest `/opsx-apply` to begin implementation.
   - If one or more artifacts are `ready`, take the first ready artifact and fetch its instructions:
     ```bash
     openspec instructions <artifact-id> --change "<name>" --json
     ```
   - Read completed dependency artifacts first.
   - Use the provided template and instruction guidance.
   - Treat `context` and `rules` as constraints only; do not copy them into the artifact.
   - Stop after creating one artifact.

4. **Show updated progress**
   ```bash
   openspec status --change "<name>"
   ```
   Report:
   - artifact created
   - current completion state
   - what is now unlocked
   - next recommended command

**Guardrails**

- Create one artifact per invocation.
- Never skip dependency order.
- Ask only when missing information materially changes the artifact.
- Verify the artifact exists before reporting success.
