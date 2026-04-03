---
description: Implement tasks from an OpenSpec change (Experimental)
agent: build
---

Implement tasks from an OpenSpec change.

**Precondition**: Execution requires both a claimed Beads execution task (run `bd --json` from the project root to confirm) and an approved OpenSpec change with a complete `tasks.md`. If either is missing, stop and route through planning or intake before proceeding.

**Input**: Optionally specify a change name (e.g., `/opsx-apply add-auth`). If omitted, check whether it can be inferred from conversation context. If vague or ambiguous, prompt for available changes.

**Steps**

1. **Select the change**
   - If a name is provided, use it.
   - Otherwise infer from conversation context, auto-select if only one active change exists, or use `openspec list --json` and ask the user to choose.
   - Always announce: `Using change: <name>` and how to override.

2. **Check status to understand the schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand the workflow schema and which artifact contains tasks.

3. **Get apply instructions**
   ```bash
   openspec instructions apply --change "<name>" --json
   ```
   Handle returned states:
   - `blocked`: explain what is missing and suggest `/opsx-continue`
   - `all_done`: report completion and suggest archive
   - otherwise: proceed

4. **Read context files**
   - Read the files listed in `contextFiles`.
   - Follow the schema reported by the CLI output rather than assuming filenames.

5. **Show current progress**
   - Schema
   - `N/M` tasks complete
   - Remaining task overview
   - Dynamic instruction from CLI output

6. **Implement tasks until done or blocked**
   - Work each pending task in order.
   - Keep changes focused.
   - Mark the task complete in `tasks.md` immediately after verified completion.
   - Pause if the task is ambiguous, reveals a design contradiction, or hits a blocker.

7. **Show completion or pause state**
   - Tasks completed this session
   - Overall progress
   - Archive recommendation if all done
   - Clear blocker summary if paused

**Guardrails**

- Always read context files before implementation.
- Do not guess through ambiguous tasks.
- If implementation reveals artifact defects, stop and route back through planning.
- Keep code changes minimal and task-scoped.
