# dagr engine

The engine is a Python package (`dagr`) that uses only the standard library and runs on
Python 3.9 or newer, on Windows and POSIX. You do not install it. The integration step copies
`engine/dagr/` into your tree as `.dagr/engine/dagr/`, and you run it like this:

```
python -B .dagr/engine/dagr/cli.py <command> [--root R]
```

From a checkout of this repo, `python -B engine/dagr/cli.py <command>` works the same way.

**Root.** The engine never guesses its root from where its own files sit. The root is `--root`,
or else the nearest folder above the current folder that holds a `.dagr/` folder, or else the
current folder.

## Commands

| Command | What it does |
|---|---|
| `scan` | Deterministic inventory of your tree: L0 files, `CONTEXT.md` files, workflow-looking folders and stages, which have an Inputs table, `output/` folders, knowledge-looking folders, existing frontmatter. Writes `.dagr/scan.json` and `.dagr/scan.md`. No model, no timestamps. |
| `ports` | Lists every contract's `consumes` / `produces`, the wiring between them, unbound inputs, near-miss port names (an unbound input that is close to a produced port), dangling outputs. `--json` for machines. Always exits 0. |
| `doctor` | Checks contracts against disk: frontmatter parse errors, duplicate ids, half-declared contracts, stage folders without a `CONTEXT.md`, config paths that do not exist, dependency cycles. Exit 1 if there is an error. |
| `plan "<request or workflow id>" [--map SLUG] [--stages] [--no-model] [--also ID]...` | Turns a request into a map in `.dagr/maps/SLUG/` (`map.md` and `tickets/T##-*.md`). A bare workflow id is used as is. Free text goes to the planner (below). Required input ports that another workflow produces pull that workflow in. `--stages` makes one ticket per stage folder. `--no-model` never calls a model (keyword match only); without it, a line `plan: calling <worker> as planner (may cost money)` is printed first, and `map.md` records the planner used. **Repeated workflows:** `--also <workflow-id>` adds a workflow to the plan and may be repeated, or name a workflow the plan already has to run it again (`plan video-script --also video-script` makes two instances). Extra instances get distinct slugs (`T02-video-script-2.md`), wait for the previous instance, and write to their own `run-2/` output folder. |
| `go SLUG [--scope T01,T02-T05] [--who NAME]` | Writes `GO.md`, the approval. Nothing runs without it. |
| `run SLUG [--dry-run] [--strict-exit] [--worker NAME] [--reviewer-model M] [--no-review] [--max-budget-usd N] [--max-minutes N]` | The runner. Launches every ready ticket as its own headless agent, reviews, commits (git repos only), stops when nothing can move. `--dry-run` needs no `GO.md`. Also `--stall-minutes`, `--max-turns`, `--poll`. |
| `apply [--items 1,2,5-7\|all] [--dry-run]` | Applies the items of `.dagr/PROPOSAL.md` (`### N. add-frontmatter\|add-file\|append-block: path` plus a unified diff). Without `--items` it uses `.dagr/approval.md` (must say `status: approved`). Existing files are first copied to `.dagr/backup/<ts>/`, and `MANIFEST.md` lists `item N  <path>  existing\|new`. Idempotent: an applied item reports `already applied`; a re-run writes no backup. If any diff does not apply cleanly, exit 2 naming the item and nothing is written. `--dry-run` checks every diff and writes nothing. Only `.dagr/config.json` may be written inside `.dagr/`. |
| `status SLUG` | Writes `STATUS.md` and prints the table. |
| `uninstall [--yes]` | Restores files from `.dagr/backup/<ts>/` (the oldest copy of each file wins), deletes files that a backup `MANIFEST.md` lists as `new`, removes `.dagr/`. Reads the manifest line form `item 3  <path>  new` and a markdown table form. Safety net: an L0 file (`l0_files`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) that holds a `<!-- dagr:begin -->` ... `<!-- dagr:end -->` block no backup restored has that block stripped and reported; nothing else is touched. Shows what it will do and asks first unless `--yes`. |

`doctor` exits 0 with `no contracts yet (expected before setup apply)` when the tree has none; 1 only for real errors. Every command: 0 ok, 2 refused or invalid input (`apply`, `plan`, `go`, `run`).

`run --dry-run` also prints `ARGV T##: ...` for each ready ticket, the command it would launch.

`run` exit codes: 0 finished, 2 refused or invalid, 3 another runner is active, 4 stuck,
5 finished with held or failed tickets (only with `--strict-exit`). The last line of a finished
run is `RUN-SUMMARY {json}`; the same JSON is in `assets/run-summary.json`.

## Contracts

A contract is any `CONTEXT.md`, or a `README.md` inside a folder that has stage subfolders,
whose YAML frontmatter has `id` and at least one of `consumes` / `produces`:

```yaml
---
id: newsletter
consumes: [script-draft]
produces: [newsletter-draft]
---
```

Lists may be `[a, b]` or a block of `- a` lines. Other keys are left alone. A BOM and CRLF line
endings are fine. A port ending in `?` is optional. Optional extra keys: `prerequisites`
(workflow ids, or `condition:<name>` for something a human must confirm) and `composable_with`.
Discovery skips `.git`, `node_modules`, `.dagr`, virtualenvs and `output/` folders. If
`.dagr/config.json` sets `workflow_glob` and `contract_name`, those folders are read first.

## Maps and tickets

```
.dagr/maps/<slug>/
  map.md  GO.md  STATUS.md  state.json
  tickets/T01-name.md
  questions/Q-T01.md        (only when a ticket needs a human)
  assets/T01/               (brief.md, worker output, receipt.md, verdict-N.md)
```

Ticket frontmatter: `title`, `status`, `blocked-by`, `affects`, `model`, `needs_human`,
`created` (plus `consumes` / `produces`, kept for the ledger). While the reviewer runs the ticket's `status` is `review`. A ticket held for "affects already dirty before launch" also gets `questions/Q-T##.md` naming the dirty paths; commit or discard them, then answer it to release. On disk `status` is one of
`open`, `in-progress`, `review`, `closed`, `failed`, `blocked`. `model: default` means "the
worker's configured model". Tickets whose `affects` overlap never run at the same time.

**Human questions.** A ticket with `needs_human: <question>` (or `true`, with a `## Question`
section) gets `questions/Q-<T##>.md` and goes on hold with everything that depends on it.
Independent tickets keep running. Write your answer under `## Answer`, then change `status:
open` to `status: answered`. The answer is copied into the ticket and the hold is released.
`status: dropped` fails the ticket and marks it `replan_needed`.

## Workers and the reviewer

`.dagr/config.json` -> `workers` holds one template per agent CLI: `claude`, `codex`,
`opencode`, `custom`. `launch_worker()` in `runner_lib.py` is the only place an argv is built
and the only process spawn. A template has `argv` (or `command` for `custom`), `model`,
`stdin` (`"brief"` pipes the brief file to the child), `output` (`claude-stream` or `text`),
`optional_flags` (dropped when a placeholder is empty), `tail`, and for `claude` a `tools`
mapping. Placeholders: `{model}` `{brief_file}` `{cwd}` `{max_turns}` `{max_budget_usd}`.
`DAGR_WORKER_BIN` (or `DAGR_<NAME>_BIN`, or `CLAUDE_BIN` for claude) replaces the binary, which
is how the tests use a fake agent.

The reviewer is a separate process started the same way, with `reviewer.worker` and
`reviewer.model` (default: the same worker). It scores a ticket against its `Definition of
done` (or `Acceptance`) section. Pass is 0.8 or higher (`pass_threshold`). Below that the
worker retries with the reviewer's notes, up to 3 attempts (`max_attempts`), then the ticket
fails with `replan_needed`. A reviewer that crashes or prints no score never passes a ticket.

| Config key | Meaning (default) |
|---|---|
| `worker` | worker template to use (`claude`) |
| `workers` | the templates above |
| `reviewer` | `{worker, model}` for the reviewer |
| `planner` | `{worker, model}` for `plan` with free text |
| `pass_threshold`, `max_attempts` | 0.8, 3 |
| `max_turns`, `max_minutes`, `stall_minutes`, `max_budget_usd` | 150, 90, 20, 10 |
| `git_commits` | commit per closed ticket when the root is a git repo (true) |
| `commit_trailer` | optional trailer line added to commit messages |
| `root`, `l0_files`, `workflows_root`, `workflow_glob`, `contract_name`, `knowledge_dirs`, `output_dirs`, `created` | written by the integration step; `workflow_glob`, `contract_name`, `output_dirs` are read |

## Planning without a model

`plan` with free text calls the planner worker. If no worker binary is found, `DAGR_NO_MODEL`
is set, `--no-model` is given, or the call fails, it falls back to matching the words of your
request against workflow ids, port names and the first paragraph of each contract, picks the
best matches (at most 3), and says so in `map.md`. Matching strips a trailing `s` and works on
any language that splits on spaces; it is a rough tool, so read the map before you approve.

## Safety

- Nothing runs without `GO.md`; `--scope` approves part of a map.
- A worker may write only its ticket's `affects` and its assets folder. A path that changed
  during the run and is neither one is a stray write: the ticket is held, not committed.
- In a git repo, `affects` already modified before launch hold the ticket without spending a worker.
- Commits happen only in a git repo, only on the ticket's own paths (existing, inside the root,
  not git-ignored), with path-limited `git add` and `git commit`. Never `git add -A`, never a push.
  Outside git, files are written and nothing is committed.
- One runner per map (pid file), a 429 / overloaded back-off that does not use up an attempt,
  a stall kill, a wall-clock kill, a spend cap, and a pid check so a recycled pid is never killed.
- State is in `state.json` (written atomically), so a killed run can be restarted.

## Module map

| File | Role |
|---|---|
| `cli.py` | argument parsing, one function call per command |
| `config.py` | root discovery, `config.json`, worker templates |
| `frontmatter.py` | small YAML-subset reader, one-line frontmatter writer |
| `contracts.py` | contract discovery, stage folders, `Unit` |
| `scan.py` | the `scan` inventory |
| `compose.py` | ledger, resolve, `ports`, `doctor`, `plan` (map and tickets), `go` |
| `planner.py` | planner prompt and reply parser, keyword fallback |
| `graphcore.py` | tickets, ready set, holds, termination, state file |
| `runner.py` | the run loop, go gate, pid file, rate-limit, stray detection, commit |
| `runner_lib.py` | `launch_worker()`, argv builder, briefs, back-off, pid tools, git helpers |
| `reviewer.py`, `review_step.py` | the separate reviewer process and the pass/retry/fail decision |
| `holds.py` | `questions/Q-<T##>.md` holds |
| `status.py` | `STATUS.md` |
| `scaffold.py` | `.dagr/` setup, vendoring, `uninstall` |

## Tests

```
python -B -m unittest discover -s engine/tests
```

No model and no network. A fake agent script stands in for every agent CLI, as worker,
reviewer and planner. The tests also use `examples/after/` when it is present.

## Known limits

Read these before you rely on it.

- **Smoke-tested (2026-11-10).** The `claude` template ran for real once: one ticket
  (`affects: [hello.md]`, worker and reviewer both haiku) in a throwaway git repo went plan, go,
  `run --strict-exit --max-budget-usd 0.5 --max-minutes 5`. Exit 0, worker wrote `hello.md`,
  reviewer scored 1.0, ticket closed, path-limited commit, `RUN-SUMMARY` printed, cost about
  $0.01. Flags checked against `claude --help`; `--max-turns` is not listed there, so the probe
  drops it. `codex exec` (`--sandbox workspace-write`, `--model`, `-` for stdin) and
  `opencode run` (`--auto`, `--model provider/model`, `--file`) were checked against `--help`
  and their argv printed, but never run. Still unverified: codex and opencode real runs and auth,
  the `--allowedTools` write globs against a multi-file ticket, retry and 429 paths with the
  real CLI. Check `assets/T##/worker-1.out` before you trust a big map.
- Only the `claude` template enforces the reviewer's read-only tool lockdown and the worker's
  write allow-list through flags. For other agents the rules are in the brief and the stray-write
  check catches violations afterward; it cannot prevent them.
- Stray-write detection compares `git status` (or a file snapshot outside git) before and after.
  It cannot see edits to a file that was already modified at launch, and in a non-git tree a
  snapshot walk is capped at 20,000 files.
- Cost is only known for agents whose output reports it (claude). For others the spend cap does
  nothing and cost shows as $0.00.
- `plan` makes one ticket per workflow. If a request needs the same workflow twice (two
  episodes), edit the map or run `plan` twice; the planner does not duplicate nodes.
- Text-format workers (`codex`, `opencode`, `custom`) are judged "done" by exit code 0 plus a
  `receipt.md`; their stdout is not parsed.
- The keyword fallback is deliberately simple. It will miss synonyms.
- The runner holds a ticket whose `affects` were already modified before launch. That is a
  safety choice; reset the ticket's `status` to `open` after you commit or stash your changes.
- Runner-owned ticket edits touch one frontmatter line at a time, but a worker or human editing
  the same ticket file at the same moment can still clash.
- Windows: `custom` commands are split like a POSIX shell, so use forward slashes or quotes
  around paths in the `command` string.
