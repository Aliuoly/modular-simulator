---
description: Execute linked Beads work from an approved modsim OpenSpec change.
agent: orchestrator
---

Implement work from a `modsim-contract` change.

**Precondition**: Execution requires an approved OpenSpec change with a complete planning pack and valid Beads linkage. If either is missing, stop and route through `modsim-propose` or `modsim-continue`.

**Input**: Optionally specify a change name after `/modsim-apply` (for example `/modsim-apply add-auth`). If omitted, infer from conversation context when safe; if ambiguous, prompt with the `question` tool.

---

## `/modsim-apply` Flow

1. **Select the change**
   - If a name is provided, use it.
   - Otherwise infer from conversation context, auto-select only if there is one clear active candidate, or use `openspec list --json` and ask the user to choose.
   - Always announce which change is being used and how to override it.

2. **Check status to understand the schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand the schema, artifact state, and apply requirements.

3. **Get apply instructions**
   ```bash
   openspec instructions apply --change "<name>" --json
   ```
   Handle returned states:
   - `blocked`: explain what is missing and suggest `modsim-continue` or `modsim-propose`
   - `all_done`: report completion and suggest `modsim-verify` or `modsim-archive`
   - otherwise: proceed

4. **Read context files**
   - Read every file listed in `contextFiles`.
   - Follow the schema reported by the CLI output rather than assuming filenames.
   - Treat `tasks.md` as the planning breakdown and `beads-identity.md` as the execution-linkage record.

5. **Resolve linked Beads work**
   - Read `beads-identity.md`.
   - Resolve the linked Beads epic and child tasks.
   - Check current task status before claiming work.
   - If linkage is stale, missing, or contradictory, stop and route back to `modsim-propose`.

6. **Show current execution context**
   Report:
   - schema name
   - Beads epic and active child task
   - relevant planning wave(s) from `tasks.md`
   - current blocker state if any
   - dynamic instruction from the CLI output

7. **Implement linked work until done or blocked**
   - Select the next ready linked Beads task and claim it before implementation.
   - When a worktree is needed, use `bd worktree`, not raw `git worktree`, so Beads keeps working inside the worktree.
   - Keep changes focused on the claimed task packet.
   - Pass the claimed Beads task ID into every delegated executor or reviewer packet.
   - Require each delegated executor or reviewer to append packet-level notes to that Beads task before returning.
   - Update Beads notes and status as the live progress log.
   - Run required verification commands after each implementation wave.
   - Send completed work through independent review before claiming the wave is complete.
   - If implementation reveals a design contradiction, spec defect, or missing decision, stop and route back through planning.
   - The orchestrator keeps ownership of final `closed` and top-level `blocked` status transitions.

8. **Continue until the change is complete or blocked**
   - After each completed task, select the next ready linked Beads task and continue.
   - Stop only when the full change is complete, a real blocker stops progress, or replanning is required.

9. **Show completion or pause state**
   Report:
   - Beads tasks completed or advanced this session
   - verification evidence gathered
   - review result or next review action
   - overall completion state
   - clear blocker summary if paused

**Guardrails**

- Always read context files before implementation.
- Do not use `tasks.md` checkboxes as the live execution source of truth.
- Do not guess through ambiguous tasks.
- Do not proceed if Beads linkage is stale or ambiguous.
- Keep code changes minimal and task-scoped.

Use the `question` tool only when a missing decision blocks execution.
