## Universal Repo Rules

- Check current official documentation before relying on third-party library behavior. Use GitHub issues and discussions only as secondary evidence.
- Repo workflow invariants:
  - OpenSpec is the durable contract.
  - Beads is the live execution ledger.
  - `tasks.md` is planning only, not execution state.
  - `beads-identity.md` stores the OpenSpec to Beads linkage.
- For Beads usage guidance, refer to the `beads` skill.
- If a Beads-backed worktree is needed, use `bd worktree`, not raw `git worktree`, so Beads keeps working inside the worktree.
- Use `grepai search` first for semantic code exploration. Use English queries. Fall back to `grep` or `glob` only for exact text or path matching.
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

After making a git worktree, `grepai watch` to start the index daemon to keep the worktree index up to date.
When starting work in an existing worktree, verify the grepai watch daemon is running!
When removing a worktree, also kill the corresponding grepai watch daemon.
