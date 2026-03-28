Use 'bd' for task tracking

When user input is genuinely required and the `question` tool is available, use it rather than freeform prompting.

## Code Exploration Policy

Always use jCodemunch-MCP tools for code navigation. Never fall back to Read, Grep, Glob, or Bash for code exploration.

**Start any session:**
1. `resolve_repo { "path": "." }` — confirm the project is indexed. If not: `index_folder { "path": "." }`
2. `suggest_queries` — when the repo is unfamiliar

**Finding code:**
- symbol by name → `search_symbols` (add `kind=`, `language=`, `file_pattern=` to narrow)
- string, comment, config value → `search_text` (supports regex, `context_lines`)
- database columns (dbt/SQLMesh) → `search_columns`

**Reading code:**
- before opening any file → `get_file_outline` first
- one or more symbols → `get_symbol_source` (single ID → flat object; array → batch)
- symbol + its imports → `get_context_bundle`
- specific line range only → `get_file_content` (last resort)

**Repo structure:**
- `get_repo_outline` → dirs, languages, symbol counts
- `get_file_tree` → file layout, filter with `path_prefix`

**Relationships & impact:**
- what imports this file → `find_importers`
- where is this name used → `find_references`
- is this identifier used anywhere → `check_references`
- file dependency graph → `get_dependency_graph`
- what breaks if I change X → `get_blast_radius` (add `include_depth_scores=true` for layered risk)
- what symbols actually changed since last commit → `get_changed_symbols`
- find unreachable/dead code → `find_dead_code`
- most important symbols by architecture → `get_symbol_importance`
- class hierarchy → `get_class_hierarchy`
- related symbols → `get_related_symbols`
- diff two snapshots → `get_symbol_diff`

**Retrieval with token budget:**
- best-fit context for a task → `get_ranked_context` (query + token_budget)
- bounded symbol bundle → `get_context_bundle` (add token_budget= to cap size)

**After editing a file:** `index_file { "path": "/abs/path/to/file" }` to keep the index fresh.

## Hybrid OpenCode Workflow

- Prefer the repo-local OpenCode agents: `hybrid-planner`, `hybrid-plan-reviewer`, `hybrid-orchestrator`, `hybrid-explore`, `hybrid-general-low`, `hybrid-general-high`, and `hybrid-code-reviewer`.
- For implementation work, create new git worktrees via the repo-local OpenCode `create_worktree` tool (plugin) instead of ad hoc `git worktree add` instructions.
- If `create_worktree` cannot complete full setup (worktree + jCodeMunch bootstrap), treat that as a blocker and stop instead of continuing with a partially prepared worktree.
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
