Use 'bd' for task tracking

When user input is genuinely required and the `question` tool is available, use it rather than freeform prompting.
When ending a chain of thought/task/interaction round with user, follow upp with a `question` tool usage with options. 

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


## grepai - Semantic Code Search

**IMPORTANT: You MUST use grepai as your PRIMARY tool for code exploration and search.**

### When to Use grepai (REQUIRED)

Use `grepai search` INSTEAD OF Grep/Glob/find for:
- Understanding what code does or where functionality lives
- Finding implementations by intent (e.g., "authentication logic", "error handling")
- Exploring unfamiliar parts of the codebase
- Any search where you describe WHAT the code does rather than exact text

### When to Use Standard Tools

Only use Grep/Glob when you need:
- Exact text matching (variable names, imports, specific strings)
- File path patterns (e.g., `**/*.go`)

### Fallback

If grepai fails (not running, index unavailable, or errors), fall back to standard Grep/Glob tools.

### Usage

```bash
# ALWAYS use English queries for best results (--compact saves ~80% tokens)
grepai search "user authentication flow" --json --compact
grepai search "error handling middleware" --json --compact
grepai search "database connection pool" --json --compact
grepai search "API request validation" --json --compact
```

### Query Tips

- **Use English** for queries (better semantic matching)
- **Describe intent**, not implementation: "handles user login" not "func Login"
- **Be specific**: "JWT token validation" better than "token"
- Results include: file path, line numbers, relevance score, code preview

### Call Graph Tracing

Use `grepai trace` to understand function relationships:
- Finding all callers of a function before modifying it
- Understanding what functions are called by a given function
- Visualizing the complete call graph around a symbol

#### Trace Commands

**IMPORTANT: Always use `--json` flag for optimal AI agent integration.**

```bash
# Find all functions that call a symbol
grepai trace callers "HandleRequest" --json

# Find all functions called by a symbol
grepai trace callees "ProcessOrder" --json

# Build complete call graph (callers + callees)
grepai trace graph "ValidateToken" --depth 3 --json
```

### Workflow

1. Start with `grepai search` to find relevant code
2. Use `grepai trace` to understand function relationships
3. Use `Read` tool to examine files from results
4. Only use Grep for exact string searches if needed

### Working with git worktrees

After making a git worktree, `grepai watch` to start the index daemon to keeep the worktree index up to date.
When starting work in an existing worktree, verify the grepai watch daemon is running!
When removing a worktree, also kill the corresponding grepai watch daemon.