Use 'bd' for task tracking

When user input is genuinely required and the `question` tool is available, use it rather than freeform prompting.

## Hybrid OpenCode Workflow

- Prefer the repo-local OpenCode agents: `hybrid-planner`, `hybrid-plan-reviewer`, `hybrid-orchestrator`, `hybrid-explore`, `hybrid-general-low`, `hybrid-general-high`, and `hybrid-code-reviewer`.
- Intake lifecycle is Beads-first:
  - If no suitable Beads goal exists, create one top-level Beads goal as the overall container.
  - If a suitable goal already exists, add new work under that goal instead of creating another top-level goal.
  - Start fuzzy requests as a Beads discovery/spec task under the goal.
  - Start OpenSpec only after scope, capabilities, and success criteria are stable.
  - Create implementation Beads tasks from approved OpenSpec `tasks.md` items.
- State ownership split:
  - OpenSpec is the durable contract and source of truth for requirements, design, acceptance criteria, and implementation tasks (`proposal.md`, `design.md`, delta specs, `tasks.md`).
  - OpenSpec `tasks.md` tracks progress inside one active change.
  - Beads tracks cross-change hierarchy, queueing, blockers, discovered follow-ups (`discovered-from:*`), and overall workflow state.
  - Beads is the only cross-change workflow tracker; OpenSpec `tasks.md` tracks implementation progress within the active change. Run all `bd --json` commands from the project root `/home/alden/projects/ModularSimulator`, not from git worktrees.
- OpenSpec change naming rule: do **not** create or use date-prefixed change directory names (for example `2026-03-24-my-change`). The repo's OpenSpec CLI rejects change names that do not start with a letter. Use letter-prefixed kebab-case names instead (for example `harden-unit-metadata-error-translation`).
- Superpowers is limited to execution discipline in this repo. Keep `using-git-worktrees`, `dispatching-parallel-agents`, `test-driven-development`, `systematic-debugging`, and `verification-before-completion`. Do not create `docs/superpowers/plans/*.md` as a second planning system.
- Make OpenSpec `tasks.md` execution-ready: concrete task waves, exact files when known, explicit verification commands, and clear TDD expectations for behavior changes.
- `hybrid-orchestrator` owns delegation and closure. It should start from discovery (Beads-only) or execution (Beads + approved OpenSpec), use Beads from the project root to claim/update work, keep implementation inside a git worktree, dispatch coding agents with bounded task packets, require independent code review before completion, and only close work after evidence-backed verification.
- Changes affecting simulation behavior, unit-operation semantics, thermodynamics, fluids or flow behavior, chemistry, controls, named engineering heuristics/correlations, or rough engineering economics/CAPEX should set `simulation-realism-required: true` in the task packet so `hybrid-code-reviewer` can perform the merged realism review before closure.
- Use real names for equations, correlations, and heuristics in prompts, specs, code, and tests when practical; avoid placeholders like `generic_scaling_law` when the rule is actually Darcy-Weisbach, Antoine, six-tenths rule, Lang factor, or similar.
- If OpenSpec artifacts changed during implementation, run change verification, sync delta specs into `openspec/specs/` when appropriate, and archive only when the change is actually complete.
