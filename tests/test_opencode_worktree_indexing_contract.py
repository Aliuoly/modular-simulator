from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_create_worktree_plugin_exists_and_wires_index_bootstrap() -> None:
    plugin_path = ROOT / ".opencode/plugins/create-worktree.js"
    assert plugin_path.exists(), "Expected repo-local create-worktree plugin file"

    plugin_text = plugin_path.read_text(encoding="utf-8")
    assert "create_worktree" in plugin_text
    assert "client.worktree.create" not in plugin_text
    assert "git -C" in plugin_text
    assert "worktree add -b" in plugin_text
    assert "test -e ${targetDirectory}" not in plugin_text
    assert "kill -0 ${pid}" not in plugin_text
    assert "cleanupCreatedWorktree" in plugin_text
    assert "worktree remove --force" in plugin_text
    assert "branch -D" in plugin_text
    assert 'replaceAll("/", "-")' in plugin_text
    assert "jcodemunch-mcp" in plugin_text
    assert "watch" in plugin_text
    assert "--extra-ignore" in plugin_text
    assert ".worktree/**" in plugin_text
    assert ".worktrees/**" in plugin_text
    assert "watcherLogName" in plugin_text


def test_create_worktree_plugin_derives_repo_root_from_git_common_dir() -> None:
    plugin_text = (ROOT / ".opencode/plugins/create-worktree.js").read_text(encoding="utf-8")
    assert "--git-common-dir" in plugin_text
    assert "--show-toplevel" not in plugin_text


def test_main_repo_jcodemunch_index_hygiene_excludes_worktree_dirs() -> None:
    opencode_config = _read("opencode.json")
    assert "jcodemunch-mcp[watch]" in opencode_config
    assert ".worktree/**" in opencode_config
    assert ".worktrees/**" in opencode_config


def test_root_gitignore_tracks_plugin_dir_and_ignores_worktree_root() -> None:
    gitignore_text = _read(".gitignore")
    assert ".worktree/" in gitignore_text
    assert "!.opencode/plugins/" in gitignore_text
    assert "!.opencode/plugins/**" in gitignore_text


def test_agent_guidance_prefers_create_worktree_and_requires_fail_fast() -> None:
    guidance = _read("AGENTS.md")
    orchestrator = _read(".opencode/agents/hybrid-orchestrator.md")

    assert "create_worktree" in guidance
    assert "create_worktree" in orchestrator
    assert "stop" in orchestrator.lower() and "setup" in orchestrator.lower()
    assert "teardown" in orchestrator.lower()
    assert (
        'pgrep -af "jcodemunch-mcp watch .*<worktree-name-or-path-fragment>" || true'
        in orchestrator
    )
    assert (
        'pkill -f "jcodemunch-mcp watch .*<worktree-name-or-path-fragment>" || true' in orchestrator
    )
    assert "re-check with the same `pgrep -af ... || true`" in orchestrator.lower()
    assert "jcodemunch_resolve_repo" in orchestrator
    assert "invalidate_cache" in orchestrator
    assert "remove the worktree/branch via the normal landing/removal flow" in orchestrator.lower()
