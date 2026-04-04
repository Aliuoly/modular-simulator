# Beads Skill for OpenCode

Repo-local OpenCode adaptation of the official [Beads](https://github.com/steveyegge/beads) skill for using `bd` as a persistent issue and context ledger.

## What This Skill Does

This skill teaches OpenCode agents how to use `bd` effectively for:
- **Multi-session work tracking** - Persistent memory across conversation compactions
- **Dependency management** - Graph-based issue relationships
- **Session handoff** - Writing notes that survive context resets
- **Beads-aware worktrees** - Use `bd worktree` so execution worktrees keep Beads working correctly

## Installation

This repo-local copy is the [`beads` skill](.). No extra installation step is required for this repository.

## When OpenCode Uses This Skill

The skill activates when conversations involve:
- "multi-session", "complex dependencies", "resume after weeks"
- "project memory", "persistent context", "side quest tracking"
- Work that spans multiple days or compaction cycles
- Tasks too complex for simple `todowrite` lists

## File Structure

```
beads/
├── SKILL.md                 # Main skill file
├── README.md                # This file (for humans)
└── resources/               # Detailed documentation (loaded on demand)
    ├── BOUNDARIES.md        # When to use bd vs todowrite
    ├── CLI_REFERENCE.md     # CLI command reference
    ├── DEPENDENCIES.md      # Dependency semantics (A blocks B vs B blocks A)
    ├── INTEGRATION_PATTERNS.md # todowrite and workflow integration
    ├── ISSUE_CREATION.md    # When and how to create issues
    ├── PATTERNS.md          # Common usage patterns
    ├── RESUMABILITY.md      # Writing notes for post-compaction recovery
    ├── TROUBLESHOOTING.md   # Common issues and fixes
    ├── WORKFLOWS.md         # Step-by-step workflow guides
    └── WORKTREES.md         # Parallel development patterns
```

Only workflow-relevant docs are kept in this repo-local copy. Upstream maintainer notes and advanced Beads features that do not help the Modsim workflow were intentionally removed.

## Key Concepts

### bd vs todowrite

| Use bd when... | Use `todowrite` when... |
|----------------|------------------------|
| Work spans multiple sessions | Single-session tasks |
| Complex dependencies exist | Linear step-by-step work |
| Need to resume after weeks | Just need a quick checklist |
| Knowledge work with fuzzy boundaries | Clear, immediate tasks |

### The Dependency Direction Trap

`bd dep add A B` means **"A depends on B"** (B must complete before A can start).

```bash
# Want: "Setup must complete before Implementation"
bd dep add implementation setup  # ✓ CORRECT
# NOT: bd dep add setup implementation  # ✗ WRONG
```

### Surviving Compaction

When session context gets compacted, conversation history is lost but bd state survives. Write notes as if explaining to a future agent session with zero context:

```bash
bd update issue-123 --notes "COMPLETED: JWT auth with RS256
KEY DECISION: RS256 over HS256 for key rotation
IN PROGRESS: Password reset flow
NEXT: Implement rate limiting"
```

## Requirements

- [bd CLI](https://github.com/steveyegge/beads) installed (`brew install beads`)
- A git repository (bd requires git for sync)
- Initialized database (`bd init` in project root)

## Version Compatibility

| Version | Features |
|---------|----------|
| v0.60.0+ | CLI credential pass-through for Dolt server push/pull |
| v0.58.0+ | `bd prime --claim`, `bd show --long`, `--stdin` flag |
| v0.54.0+ | `bd doctor` detects committed runtime/sensitive files, `BD_BACKUP_ENABLED=false` |
| v0.52.0+ | `bd sync` deprecated (use `bd dolt push`), `--claim` for atomic start-work |
| v0.47.0+ | Pull-first sync, resolve-conflicts, dry-run create, gate auto-discovery |
| v0.43.0+ | Full support: agents, gates, worktrees, chemistry patterns |
| v0.40.0+ | Agent beads, async gates, worktree management |
| v0.34.0+ | Molecules, wisps, cross-project dependencies |
| v0.15.0+ | Core: dependencies, notes, status tracking |

## Contributing

This repo-local copy is adapted from the official Beads skill bundle maintained at [github.com/steveyegge/beads](https://github.com/steveyegge/beads).

Issues and PRs welcome for:
- Documentation improvements
- New workflow patterns
- Bug fixes in examples
- Additional troubleshooting scenarios

## License

MIT (same as beads)
