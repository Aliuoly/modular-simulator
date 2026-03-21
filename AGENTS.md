Use 'bd' for task tracking

## Hybrid OpenCode Workflow

- Prefer the repo-local OpenCode agents: `hybrid-planner`, `hybrid-plan-reviewer`, `hybrid-orchestrator`, `hybrid-explore`, `hybrid-general-low`, `hybrid-general-high`, and `hybrid-code-reviewer`.
- OpenSpec owns durable intent and documentation: `proposal.md`, `design.md`, delta specs, and `tasks.md`.
- Beads is the only task tracker. Use `bd --json`, link discovered follow-up work with `discovered-from:*`, and run all `bd` commands from the project root `/home/alden/projects/ModularSimulator`, not from git worktrees.
- Superpowers is limited to execution discipline in this repo. Keep `using-git-worktrees`, `dispatching-parallel-agents`, `test-driven-development`, `systematic-debugging`, and `verification-before-completion`. Do not create `docs/superpowers/plans/*.md` as a second planning system.
- Make OpenSpec `tasks.md` execution-ready: concrete task waves, exact files when known, explicit verification commands, and clear TDD expectations for behavior changes.
- `hybrid-orchestrator` owns delegation and closure. It should use Beads from the project root to claim/update work, keep implementation inside a git worktree, dispatch coding agents with bounded task packets, require independent code review before completion, and only close work after evidence-backed verification.
- If OpenSpec artifacts changed during implementation, run change verification, sync delta specs into `openspec/specs/` when appropriate, and archive only when the change is actually complete.
