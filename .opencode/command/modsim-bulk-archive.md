---
description: Archive multiple completed modsim changes in one pass.
agent: orchestrator
---

Archive multiple completed changes in a single operation.

This command handles batch archive work, including spec conflicts, linked Beads closure state, and evidence checks.

**Input**: None required by default. Prompt for selection with the `question` tool.

---

## `/modsim-bulk-archive` Flow

1. **Get active changes**
   Run `openspec list --json` to get all active changes.

   If no active changes exist, inform the user and stop.

2. **Prompt for change selection**
   Use the `question` tool with multi-select to let the user choose changes:
   - show each change with its schema and status
   - include an option for `All changes`
   - allow any number of selections

   Do not auto-select.

3. **Batch validation for all selected changes**

   For each selected change, collect:

   a. **Artifact status**
      - Run `openspec status --change "<name>" --json`
      - note which required artifacts are done or incomplete

   b. **Beads closure state**
      - read `beads-identity.md`
      - resolve linked epic and child tasks
      - note whether linked work is closed, open, blocked, or missing

   c. **Verification and review state**
      - note whether verification evidence exists
      - note whether independent review passed
      - note whether realism review was required and passed

   d. **Delta specs**
      - check which capability specs exist
      - identify overlapping capabilities across selected changes

4. **Detect spec conflicts**

   Build a map of `capability -> [changes that touch it]`.

   A conflict exists when 2 or more selected changes have delta specs for the same capability.

5. **Resolve conflicts agentically**

   For each conflict:
   - read the relevant delta specs
   - inspect the codebase for implementation evidence
   - determine whether one or both changes are actually implemented
   - if both are implemented, apply sync in a justified order
   - record the rationale clearly

6. **Show consolidated status table**

   Present a table summarizing all selected changes, including:
   - artifact status
   - Beads closure state
   - review state
   - delta spec status
   - conflict state
   - overall archive readiness

   Show warnings for incomplete or partially verified changes.

7. **Confirm the batch operation**

   Use the `question` tool to ask whether to:
   - archive all selected changes
   - archive only fully ready changes
   - cancel

8. **Execute archive for each confirmed change**

   Process changes in the determined order:

   a. **Sync specs** if needed
   - run the sync flow
   - respect the resolved conflict order

   b. **Perform the archive**
   ```bash
   mkdir -p openspec/changes/archive
   mv openspec/changes/<name> openspec/changes/archive/YYYY-MM-DD-<name>
   ```

   c. **Track outcome**
   - success
   - skipped
   - failed

9. **Display final summary**

   Report:
   - archived changes
   - skipped changes
   - failed changes
   - spec sync summary
   - any conflicts resolved

**Guardrails**

- Always prompt for selection.
- Detect conflicts before archiving.
- Use evidence from code, review, and Beads closure state.
- Do not rely on `tasks.md` checkboxes as the batch archive gate.
- If the archive target already exists for one change, fail that change and continue with the rest.

Finish with the `question` tool and concrete next-step options.
