---
name: modsim-apply
description: Execute a modsim OpenSpec change by resolving linked Beads work and using Beads as the live execution ledger.
license: MIT
compatibility: Requires openspec CLI, Beads CLI, and the repo-local modsim OpenSpec + Beads workflow.
metadata:
  author: ModularSimulator
  version: "1.0"
  workflow: modsim-contract
---

Execute an approved `modsim-contract` change by reading the contract, claiming linked Beads work, and using Beads as the live ledger.

**Input**: An optional change name. If omitted, infer it only when the current context is unambiguous.

**Steps**

1. Resolve the target change.
2. Run:
   ```bash
   openspec status --change "<name>" --json
   ```
3. Run:
   ```bash
   openspec instructions apply --change "<name>" --json
   ```
4. Handle the apply state:
   - `blocked`: stop and route to `modsim-continue` or `modsim-propose`
   - `all_done`: report completion and suggest `modsim-verify` or `modsim-archive`
   - `ready`: continue
5. Read every file listed in `contextFiles`.
6. Treat `tasks.md` as the planning breakdown and `beads-identity.md` as the linkage record.
7. Resolve the linked Beads epic and child tasks from `beads-identity.md`.
8. Claim the correct Beads task before implementation.
9. When a worktree is needed, use `bd worktree`, not raw `git worktree`, so Beads linkage works inside the worktree.
10. Delegate bounded packets when useful, always passing the claimed Beads task ID.
11. Update Beads status and notes as the live progress log.
12. Require delegated executors and reviewers to append packet-level notes to the claimed Beads task before they return.
13. If execution stops blocked or rerouted, update the claimed Beads task with the blocker reason, evidence, and next action before returning.
14. Run fresh verification after each implementation wave.
15. Send completed work through independent review before closure.

**Output**

During execution, report:
- `Change:` active change name
- `Beads task:` claimed task ID
- `Progress:` wave or packet status
- `Evidence:` verification commands run and actual outcomes
- `Next action:` continue, reroute, verify, or archive

**Guardrails**

- Do not use `tasks.md` checkboxes as the live execution ledger.
- Do not guess through ambiguous work packets.
- Stop when `beads-identity.md` is missing or stale, linked Beads work is ambiguous, the contract is defective, or required verification is failing.
- Keep code changes tightly scoped to the claimed task.
- Leave final `closed` and top-level `blocked` state changes to the orchestrator even when subagents append packet notes.
