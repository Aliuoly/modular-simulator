import { existsSync, readFileSync } from "node:fs"
import path from "node:path"
import { tool } from "@opencode-ai/plugin"

const EXTRA_IGNORES = [".worktree/**", ".worktrees/**"]

function quoteArg(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`
}

function sanitizeBranchName(value) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._/-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^[-./]+|[-./]+$/g, "")
}

async function ensureRepoRoot($, directory) {
  const result = await $`git -C ${directory} rev-parse --git-common-dir`.quiet()
  if (result.exitCode !== 0) {
    throw new Error("Could not resolve git repository root")
  }
  const commonDir = result.text().trim()
  return path.dirname(path.resolve(directory, commonDir))
}

async function ensureWorkingTreeCleanForPath($, targetDirectory) {
  if (existsSync(targetDirectory)) {
    throw new Error(`Refusing to create worktree: path already exists: ${targetDirectory}`)
  }
}

async function createRepoWorktree($, repoRoot, targetDirectory, branchName) {
  const created = await $`git -C ${repoRoot} worktree add -b ${branchName} ${targetDirectory}`.quiet()
  if (created.exitCode !== 0) {
    throw new Error(`Failed to create repo worktree: ${created.text().trim()}`)
  }
}

async function cleanupCreatedWorktree($, repoRoot, targetDirectory, branchName) {
  const remove = await $`git -C ${repoRoot} worktree remove --force ${targetDirectory}`.quiet()
  const branch = await $`git -C ${repoRoot} branch -D ${branchName}`.quiet()

  if (remove.exitCode !== 0 || branch.exitCode !== 0) {
    throw new Error(
      `Failed to clean up partial worktree state: ${remove.text().trim()} ${branch.text().trim()}`.trim(),
    )
  }
}

async function bootstrapJcodemunchWatcher($, targetDirectory, worktreeName) {
  const check = await $`uvx jcodemunch-mcp config --check`.quiet()
  //if (check.exitCode !== 0) {
  //  throw new Error(`jCodeMunch prerequisite check failed: ${check.text().trim()}`)
  //}

  const watcherCommand = [
    "uvx",
    "jcodemunch-mcp",
    "watch",
    targetDirectory,
    "--extra-ignore",
    ...EXTRA_IGNORES,
    "--no-ai-summaries",
    "--log-level",
    "ERROR",
  ]
  const watcherLogName = worktreeName.replaceAll("/", "-")
  const watcherLog = `/tmp/jcodemunch-watch-${watcherLogName}.log`
  const spawnCommand = `nohup ${watcherCommand.map(quoteArg).join(" ")} >${quoteArg(watcherLog)} 2>&1 & echo $!`
  const spawn = await $`sh -lc ${spawnCommand}`.quiet()

  if (spawn.exitCode !== 0) {
    throw new Error(`Failed to launch jCodeMunch watcher: ${spawn.text().trim()}`)
  }

  const pid = spawn.text().trim()
  if (!/^\d+$/.test(pid)) {
    throw new Error(`Could not determine jCodeMunch watcher PID: ${pid}`)
  }

  try {
    process.kill(Number(pid), 0)
  } catch {
    const logs = existsSync(watcherLog) ? readFileSync(watcherLog, "utf-8") : ""
    throw new Error(
      `jCodeMunch watcher exited during bootstrap for ${targetDirectory}. Logs: ${logs.trim()}`,
    )
  }

  return { pid: Number(pid), log: watcherLog }
}

export const CreateWorktreePlugin = async ({ client, $, directory }) => {
  return {
    tool: {
      create_worktree: tool({
        description:
          "Create a git worktree via OpenCode client API and bootstrap jCodeMunch indexing/watch for it.",
        args: {
          name: tool.schema.string().min(1).describe("Logical worktree/task name"),
          start_command: tool.schema
            .string()
            .optional()
            .describe("Optional OpenCode worktree start command"),
        },
        async execute(args, context) {
          const repoRoot = await ensureRepoRoot($, directory)
          const safeName = sanitizeBranchName(args.name)

          if (!safeName) {
            throw new Error("Invalid worktree name after sanitization")
          }

          const targetDirectory = path.join(repoRoot, ".worktrees", safeName)
          await ensureWorkingTreeCleanForPath($, targetDirectory)

          context.metadata({
            title: `Creating worktree ${safeName}`,
            metadata: {
              worktree_name: safeName,
              target_directory: targetDirectory,
            },
          })

          await createRepoWorktree($, repoRoot, targetDirectory, safeName)
          let watcher

          try {
            watcher = await bootstrapJcodemunchWatcher($, targetDirectory, safeName)
          } catch (error) {
            await cleanupCreatedWorktree($, repoRoot, targetDirectory, safeName)
            throw error
          }

          return JSON.stringify(
            {
              status: "ok",
              worktree: {
                name: safeName,
                branch: safeName,
                directory: targetDirectory,
              },
              index_bootstrap: {
                command: "uvx jcodemunch-mcp watch",
                watcher_pid: watcher.pid,
                watcher_log: watcher.log,
                extra_ignore_patterns: EXTRA_IGNORES,
              },
            },
            null,
            2,
          )
        },
      }),
    },
  }
}
