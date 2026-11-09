# Notes per agent

dagr has two jobs for an agent. The **setup** job is reading `INTEGRATE.md` and following `setup/`. The **worker** job is running one ticket headlessly during `dagr run`. Any agent that can read files and run Python can do the setup. Workers need a CLI that runs without a person at the keyboard.

Worker command templates live in `.dagr/config.json` under `workers`. One function, `launch_worker()` in the engine's `runner_lib`, builds every command line. If a worker fails to start, that is the place to look.

> Status: no real `claude`, `codex`, or `opencode` binary has been smoke-tested with the engine. Every test uses a fake agent. Use `--dry-run`, read the line, then run one small ticket.

## Setup entry points

The normal entry point is the install line, which tells your agent to integrate the repo. The repo also ships `AGENTS.md` and `CLAUDE.md`, each a short pointer that says "read `INTEGRATE.md`, it is the whole procedure". They only matter when an agent is opened inside a clone of this repo. Neither file is copied into your tree. The setup adds its own block to your L0 file.

| Agent | How it finds the procedure |
|---|---|
| Claude Code | Paste the install line. Opened inside a clone of this repo, it reads `CLAUDE.md`, which points at `INTEGRATE.md`. |
| Codex | Paste the install line. Opened inside a clone, it reads `AGENTS.md`, which points at `INTEGRATE.md`. |
| OpenCode | Paste the install line. Opened inside a clone, it reads `AGENTS.md`, which points at `INTEGRATE.md`. |
| Cursor | Paste the install line, or tell it to read `INTEGRATE.md`. |

## Workers

Pick one with `dagr run SLUG --worker <name>`.

| Worker | Template starts with | Notes |
|---|---|---|
| `claude` | `claude -p --output-format stream-json ...` | Print mode with streamed JSON, so the runner can see progress and stalls. |
| `codex` | `codex exec ...` | Non-interactive execution. |
| `opencode` | `opencode run ...` | Works with whatever model you configured in OpenCode. |
| `custom` | your own `command` string | Placeholders: `{brief_file}` (path to the ticket brief), `{cwd}` (working folder), `{model}`, `{max_turns}`, `{max_budget_usd}`. |

Example custom entry (the `command` is split like a POSIX shell, so quote Windows paths or use forward slashes):

```json
"custom": { "command": "my-agent --prompt-file {brief_file} --dir {cwd}", "output": "text" }
```

The exact flags in the built-in templates may change. Treat `.dagr/config.json` as the source of truth, not this page.

## Reviewer model

`--reviewer-model M` sets the model for scoring. Using a different model from the worker's is a good idea, since a second opinion is the point of the review. `--no-review` skips scoring; use it only for experiments.

## Instruction files

Your root agent file gets one block added at setup. It tells the agent that multi-step requests enter through `graph-loop/CONTEXT.md` and gives the engine command. If you use more than one agent file (say `CLAUDE.md` and `.cursorrules`), the proposal lists each one separately, so you can approve the ones you use.

## Cost and safety with each

Every worker can spend money or call tools on your behalf. Before you say `go`:

1. Read `map.md`. Check each ticket's `affects` paths.
2. Set `--max-minutes`, and `--max-budget-usd` if you use `claude`. The spend cap only works for agents that report cost; for the others cost shows as $0.00.
3. Start with `--scope` on a single ticket.

## Reporting results

If a worker works or fails in a way this page does not describe, open an issue with the command line from `.dagr/config.json` (remove secrets) and the last lines of the ticket's output in `.dagr/maps/SLUG/assets/T##/` (for example `worker-1.out`).
