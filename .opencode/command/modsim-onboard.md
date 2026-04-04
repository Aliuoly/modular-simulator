---
description: Guided onboarding for the repo-owned modsim OpenSpec plus Beads workflow.
agent: planner
---

Guide the user through their first complete `modsim-*` workflow cycle. This is a teaching experience. Do real work in the codebase while explaining each phase.

---

## Preflight

Before starting, check if the required tooling is available:

```bash
openspec --version 2>&1 || echo "OPENSPEC_NOT_INSTALLED"
bd version 2>&1 || echo "BEADS_NOT_INSTALLED"
```

If OpenSpec or Beads is unavailable, explain what is missing and stop.

---

## Phase 1: Welcome

Display a short welcome that explains the workflow:

```text
## Welcome to the Modsim Workflow

We'll walk through one small real change in this repository.

What we'll do:
1. pick a small real task
2. explore the problem briefly
3. create a change pack with proposal, specs, design, tasks, and beads-identity
4. sync execution items into Beads
5. implement the work
6. verify it
7. sync specs and archive the change
```

Then pause with the `question` tool before continuing.

---

## Phase 2: Task Selection

Scan the codebase for a small useful task. Look for:
- TODO or FIXME comments
- missing tests
- small correctness issues
- narrow docs or validation gaps
- small workflow or CLI inconsistencies

Also check recent git activity to understand what is already in motion.

Present 3-4 good starter options with:
- file or area
- estimated scope
- why it is a good onboarding task

If nothing obvious appears, ask the user what small task they want to use.

If the task is too large, suggest slicing it smaller, but let the user override.

---

## Phase 3: Explore Demo

Briefly demonstrate `modsim-explore`:
- read the relevant code
- show a short analysis
- draw an ASCII diagram when helpful
- explain that explore mode is for thinking before committing to a direction

Pause with the `question` tool before moving on.

---

## Phase 4: Create The Change

Explain that a change is the container for the work.

Create it with:
```bash
openspec new change "<derived-name>" --schema modsim-contract
```

Show the folder structure, including:
- `proposal.md`
- `design.md`
- `specs/`
- `tasks.md`
- `beads-identity.md`

---

## Phase 5: Proposal

Explain that the proposal captures why the change matters and what the scope is.

Draft a concise proposal with:
- `Why`
- `What Changes`
- `Capabilities`
- `Impact`

Pause for confirmation before saving.

---

## Phase 6: Specs

Explain that specs capture what the system must do in testable terms.

Draft one or more delta specs with:
- requirement headings
- scenario headings
- concrete WHEN and THEN outcomes

Explain that these are acceptance criteria, not implementation notes.

---

## Phase 7: Design

Explain that the design captures how the work will be implemented.

Draft `design.md` with:
- context
- goals and non-goals
- decisions
- risks and trade-offs
- verification strategy

Keep it proportionate to the task size.

---

## Phase 8: Tasks

Explain that `tasks.md` is the planning breakdown, not the live execution ledger.

Draft tasks with:
- a dependency gate
- numbered waves
- exact files when known
- verification commands
- expected evidence

---

## Phase 9: Beads Linkage

Explain that Beads owns live execution state.

Create or refresh:
- one Beads epic for the change
- child tasks derived from planning waves

Then write the IDs and mapping into `beads-identity.md`.

Show the user how `tasks.md` and `beads-identity.md` differ:
- `tasks.md` = planning breakdown
- Beads = live execution state

Pause with the `question` tool before implementation.

---

## Phase 10: Apply Demo

Demonstrate `modsim-apply`:
- read the change artifacts
- resolve linked Beads work
- claim the correct task
- implement a small slice
- update Beads while working

Keep the narration light.

---

## Phase 11: Verify Demo

Demonstrate `modsim-verify`:
- compare the implementation to the contract
- review correctness and test coverage
- include realism review when required

---

## Phase 12: Sync And Archive Demo

Demonstrate:
- `modsim-sync` to merge delta specs into main specs
- `modsim-archive` to close the change after evidence, review, and Beads closure

Explain that archive is evidence-driven, not checkbox-driven.

---

## Recap And Next Steps

Summarize the workflow:
- `modsim-explore`
- `modsim-propose`
- `modsim-apply`
- `modsim-verify`
- `modsim-sync`
- `modsim-archive`

If the user wants to stop mid-way, explain how to resume with `modsim-continue` or `modsim-apply`.

Use the `question` tool for the final handoff.
