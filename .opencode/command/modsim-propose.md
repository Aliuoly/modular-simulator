---
description: Create a modsim OpenSpec pack and sync linked Beads execution items.
agent: planner
---

Use this command when the request is clear enough to define a stable contract and linked execution packets.

If the request is still fuzzy, do not guess. Say:
> "This sounds early-stage. Let's use `/modsim-explore` first to shape the problem before creating the OpenSpec pack and Beads linkage."

**Input**

The argument after `/modsim-propose` can be:
- a change name in kebab-case, or
- a clear problem statement with stable scope

**Routing rule (required)**

Before creating artifacts, classify the request:

- **Stable**: scope, intent, and near-term outcomes are clear enough to write the full `modsim-contract` pack now
  - continue with the flow below
- **Fuzzy**: open questions, unresolved trade-offs, unclear boundaries, or missing success criteria
  - redirect to `modsim-explore`

Never treat `/modsim-propose` as default intake for vague work.

---

## `/modsim-propose` Flow

1. **Resolve target change name**
   - If a valid change name is provided, use it.
   - If input is descriptive but clear, derive a concise kebab-case name.
   - If a change with that name already exists, ask whether to continue it or create a new name.

2. **Create or reuse the OpenSpec change container**
   ```bash
   openspec new change "<name>" --schema modsim-contract
   ```
   If it already exists and the user chose reuse, continue in that directory.

3. **Get schema status and apply requirements**
   ```bash
   openspec status --change "<name>" --json
   ```
   Use the JSON output to determine artifact dependencies, artifact status, and apply-ready requirements.

4. **Generate artifacts in dependency order until apply-ready**
   For each artifact with dependencies satisfied:
   ```bash
   openspec instructions <artifact-id> --change "<name>" --json
   ```
   - Read completed dependency artifacts first.
   - Use the provided template for structure.
   - Follow the instruction guidance.
   - Treat `context` and `rules` as constraints only. Do not copy them into artifact content.
   - Reuse the repo's local style from nearby high-quality changes.
   - Re-check status after each artifact and stop only when all `applyRequires` artifacts are done.

5. **Run planner self-review before Beads sync**
   Treat this as a defect-finding pass, not a formatting pass. Check the pack for:
   - missing or broadened behavior
   - contradictions between proposal, specs, design, tasks, and `beads-identity.md`
   - interface, naming, file-path, or data-shape drift across artifacts
   - hidden dependencies, bad wave ordering, or execution dead-ends
   - missing edge cases, error paths, migration/backfill needs, or integration seams that would likely produce wrong implementation
   - verification commands or evidence that are too weak to catch regressions
   - missing `simulation-realism-required: true` when simulation or engineering realism is touched
   Fix issues inline before continuing. If a real decision is still missing, stop and report the blocker.

6. **Create or refresh the linked Beads execution items**
   - Create or refresh one Beads epic for the change.
   - Create or refresh child Beads tasks from `tasks.md` planning waves.
   - Add dependency links where needed.
   - Use `discovered-from` only for new work discovered during execution, not during planning.
   - Reuse existing Beads IDs when the mapping is still valid.

7. **Write Beads linkage back into `beads-identity.md`**
   Record:
   - the OpenSpec change name
   - the Beads epic ID
   - child task IDs
   - mapping from planning waves to Beads work items
   - last sync note or timestamp
   - the statement that Beads is the live execution ledger

8. **Show completion state**
   ```bash
   openspec status --change "<name>"
   ```
   Report what was created or updated and confirm whether the pack is ready for `modsim-apply`.

**Output**

- Change name and path
- Artifacts created or updated
- Beads epic and child task IDs
- Readiness statement: ready for implementation with `/modsim-apply`

**Guardrails**

- Keep scope tight to the stable contract.
- Ask clarifying questions only when needed to resolve blocking ambiguity.
- If new uncertainty appears that changes scope materially, pause and offer `modsim-explore`.
- Do not report readiness until artifact completion, self-review, and Beads sync all succeed.
- Do not leave placeholder Beads IDs in `beads-identity.md`.

Finish with the `question` tool and concrete next-step options.
