---
description: Archive a completed modsim change after evidence, review, Beads closure, and spec sync checks.
agent: orchestrator
---

Archive a completed modsim change after checking artifacts, linked Beads state, verification evidence, sync state, and landing state.

**Input**: Optionally specify a change name after `/modsim-archive` (for example `/modsim-archive add-auth`). If omitted, infer it only when the context is clear. Otherwise use the `question` tool.

---

## `/modsim-archive` Flow

1. **Resolve the target change**
   - If no change name is provided, run `openspec list --json`.
   - Show active changes with schema and status.
   - Do not guess when multiple candidates exist.

2. **Check artifact completion status**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand:
   - `schemaName`
   - required artifacts and their status

   If any required artifacts are not `done`:
   - display a warning listing incomplete artifacts
   - ask whether to continue anyway
   - proceed only if the user confirms

3. **Check linked Beads closure state**
   - Read `beads-identity.md`.
   - Resolve the linked epic and child tasks.
   - Check whether linked execution work is closed, blocked, or still active.

   If linked Beads work is still open:
   - display a warning listing the open items
   - ask whether to continue anyway
   - proceed only if the user confirms

4. **Check verification and review state**
   Confirm:
   - verification evidence exists
   - independent review passed
   - realism review passed when `simulation-realism-required: true` applies

   If evidence or review is missing:
   - display a warning summarizing what is missing
   - ask whether to continue anyway
   - proceed only if the user confirms

5. **Assess delta spec sync state**
   Check for delta specs at `openspec/changes/<name>/specs/`.

   If delta specs exist:
   - compare them with the corresponding main specs
   - determine whether sync is still needed
   - show a combined summary before prompting

   Prompt options:
   - `Sync now (recommended)`
   - `Archive without syncing`
   - `Cancel`

   If the user chooses sync, run the `modsim-sync` flow first, then continue.

6. **Check landing state**
   Confirm the implementation is:
   - already landed, or
   - intentionally staged for landing with a clear explanation

   If landing state is unclear, warn and ask before continuing.

7. **Perform the archive**
   Create the archive directory if it does not exist:
   ```bash
   mkdir -p openspec/changes/archive
   ```

   Generate the target name using the current date: `YYYY-MM-DD-<change-name>`.

   If the target already exists, fail with a clear error and stop.

   Otherwise move the change directory:
   ```bash
   mv openspec/changes/<name> openspec/changes/archive/YYYY-MM-DD-<name>
   ```

8. **Display summary**
   Show:
   - change name
   - schema
   - archive location
   - spec sync state
   - Beads closure state
   - any explicit warnings carried into the archive

**Archive rule**

- Archive is evidence-driven, not checkbox-driven.

**Guardrails**

- Always use schema status for completion checking.
- Do not rely on `tasks.md` checkboxes as the archive gate.
- Preserve `.openspec.yaml` when moving the change directory.
- Show clear warnings before archiving incomplete or partially closed work.
- Use the `question` tool for decision points.

Finish with the `question` tool and concrete next-step options.
