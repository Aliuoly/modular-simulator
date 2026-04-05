---
name: beads
description: Use Beads (`bd`) for persistent multi-session task tracking, dependencies, and context recovery that must survive session resets or compaction.
license: "MIT"
compatibility: Requires Beads CLI (`bd`) v0.60.0+ and works best in a repo initialized with `.beads/`.
metadata:
  author: Steve Yegge
  adapted_for: ModularSimulator OpenCode
  upstream_version: "0.60.0"
---

# Beads - Persistent Task Memory for AI Agents

Graph-based issue tracker that survives conversation compaction. Provides persistent memory for multi-session work with complex dependencies.

## bd vs todowrite

**Decision test**: "Will I need this context in 2 weeks?" YES = bd, NO = `todowrite`.

| bd (persistent) | `todowrite` (ephemeral) |
|-----------------|-------------------------|
| Multi-session, dependencies, compaction survival | Single-session linear tasks |
| Dolt-backed team sync | Conversation-scoped |

See [resources/BOUNDARIES.md](resources/BOUNDARIES.md) for detailed comparison.

## Prerequisites

```bash
bd --version  # Requires v0.60.0+
```

- **bd CLI** installed and in PATH
- **Git repository** (optional — use `BEADS_DIR` + `--stealth` for git-free operation)
- **Initialization**: `bd init` run once (humans do this, not agents)

## CLI Reference

**Run `bd prime`** for AI-optimized workflow context.
**Run `bd <command> --help`** for specific command usage.

Essential commands: `bd ready`, `bd create`, `bd show`, `bd update`, `bd close`, `bd dolt push`

Prefer `--json` for agent-driven usage. Avoid interactive editing commands such as `bd edit`.

## Session Protocol

1. `bd ready` — Find unblocked work
2. `bd show <id>` — Get full context
3. `bd update <id> --claim` — Claim and start work atomically
4. Add notes as you work (critical for compaction survival)
5. Delegated executors and reviewers append packet-level outcomes to notes before they return
6. If work stops blocked or rerouted at the orchestrator level, `bd update <id> --status blocked --notes "BLOCKER: ...\nEVIDENCE: ...\nNEXT: ..."` before returning
7. `bd close <id> --reason "..."` — Complete task
8. `bd dolt push` — Push to Dolt remote (if configured)

## Output

Append `--json` to any command for structured output. Use `bd show <id> --long` for extended metadata. Status icons: `○` open `◐` in_progress `●` blocked `✓` closed `❄` deferred.

## Error Handling

| Error | Fix |
|-------|-----|
| `database not found` | `bd init <prefix>` in project root |
| `not in a git repository` | `git init` first |
| `disk I/O error (522)` | Move `.beads/` off cloud-synced filesystem |
| Status updates lag | Use server mode: `bd dolt start` |

See [resources/TROUBLESHOOTING.md](resources/TROUBLESHOOTING.md) for full details.

## Blocked Work Rule

If you claimed a Beads item and cannot continue, do not just report the blocker in chat. Persist it in Beads first.

- Set status to `blocked` when the issue truly cannot proceed.
- Put the exact blocker, supporting evidence, and the next action needed into `notes`.
- If work is being handed off or rerouted without a hard block, keep the handoff reason and next action in `notes` before returning.

## Delegated Packet Rule

When a claimed Beads item is delegated to an implementation or review subagent, that subagent should persist its packet result to the same Beads item before returning.

- Append notes, do not overwrite them.
- Include packet role, outcome, evidence, blockers or concerns, and next action.
- Leave final `closed` and top-level `blocked` status transitions to the orchestrator unless the workflow explicitly delegates that authority.

## Examples

**Track a multi-session feature:**
```bash
bd create "OAuth integration" -t epic -p 1 --json
bd create "Token storage" -t task --deps blocks:oauth-id --json
bd ready --json                    # Shows unblocked work
bd update <id> --claim --json      # Claim and start
bd close <id> --reason "Implemented with refresh tokens" --json
```

**Recover after compaction:** `bd list --status in_progress --json` then `bd show <id> --long`

**Discover work mid-task:** `bd create "Found bug" -t bug -p 1 --deps discovered-from:<current-id> --json`

## Worktrees

When worktrees are needed, use `bd worktree`, not raw `git worktree`, so the worktree inherits the Beads redirect setup correctly.

See [resources/WORKTREES.md](resources/WORKTREES.md).

## Resources

| Category | Files |
|----------|-------|
| **Getting Started** | [resources/BOUNDARIES.md](resources/BOUNDARIES.md), [resources/CLI_REFERENCE.md](resources/CLI_REFERENCE.md), [resources/WORKFLOWS.md](resources/WORKFLOWS.md) |
| **Core Concepts** | [resources/DEPENDENCIES.md](resources/DEPENDENCIES.md), [resources/ISSUE_CREATION.md](resources/ISSUE_CREATION.md), [resources/PATTERNS.md](resources/PATTERNS.md) |
| **Resilience** | [resources/RESUMABILITY.md](resources/RESUMABILITY.md), [resources/TROUBLESHOOTING.md](resources/TROUBLESHOOTING.md) |
| **Execution** | [resources/INTEGRATION_PATTERNS.md](resources/INTEGRATION_PATTERNS.md), [resources/WORKTREES.md](resources/WORKTREES.md) |

## Validation

If `bd --version` reports newer than `0.60.0`, this skill may be stale. Run `bd prime` for current CLI guidance — it auto-updates with each bd release and is the canonical source of truth.
