# How it works

dagr has two phases. **Setup** runs once, with your agent, and wires your folders. **Use** runs every time you make a multi-step request.

## Phase 1: setup (once)

You paste `Integrate https://github.com/shirshogd/dagr into my ICM`. Your agent reads `INTEGRATE.md`, then walks the six folders in `setup/`:

| Step | Writes | Changes your files? |
|---|---|---|
| 01-scan | `.dagr/scan.md` | No |
| 02-map | `.dagr/ports.md` | No |
| 03-propose | `.dagr/PROPOSAL.md` | No |
| 04-approve | nothing (it asks you) | No |
| 05-apply | edits, plus `.dagr/backup/<ts>/` | Yes, approved items only |
| 06-verify | a report | No |

`dagr scan` does the counting part of step 01 the same way every time. Your agent adds judgment on top: which folder is a workflow, which file acts as a contract, what a stage is for.

Your tree does not need to match ICM exactly. The scan tolerates missing layers, a `README.md` used as a contract, folders named `stages/`, `steps/`, `01_x/` or `01-x/`, and text in any language. Whatever it cannot work out goes in the gaps list in `ports.md`.

## What gets added

1. `.dagr/` at your root: `config.json`, the scan and proposal files, `backup/`, a copy of the engine in `engine/` (so nothing needs installing), and `maps/` for runs.
2. Port frontmatter at the top of each workflow `CONTEXT.md`, merged with any frontmatter you already have. Your prose is not touched.
3. A `graph-loop` workflow in the place your workflows live.
4. A short block in your root agent file that points at `graph-loop`.

Nothing else. Every edit is listed in `PROPOSAL.md` first.

## Phase 2: a graph run

The `graph-loop` workflow is the front door for any multi-step request. Its stages are: brainstorm, retrieve (search your own knowledge folders), plan to graph, `go`, run, review, write-back.

### Plan

`dagr plan "<request>"` resolves the request into a DAG. By default each workflow becomes one ticket; `--stages` makes one ticket per stage. Each node is a **ticket**, a markdown file in `.dagr/maps/SLUG/tickets/` with frontmatter (`title`, `status`, `blocked-by`, `affects`, `model`, `needs_human`, `created`). `blocked-by` is how edges are stored. `map.md` shows the whole graph.

With a model available, the planner asks the configured worker command for the plan. With none (or with `--no-model`), it matches your request against workflow ids and descriptions by keyword, and says that it did.

### Go

`dagr go SLUG` writes `GO.md`. Until it exists, `run` refuses to start. Review `map.md` first. `--scope T01,T02-T05` approves part of the graph.

### Run

`dagr run SLUG` launches every ticket whose blockers are done, each as a headless worker in its own process. The worker gets a brief file built from the ticket and the files its stage lists under Inputs. `--dry-run` shows what it would launch without launching.

### Review

A separate reviewer scores each output from 0 to 1 against a rubric. At 0.8 or more the ticket passes. Below that it retries with the reviewer's notes, up to 3 attempts. After the third failure the node fails, and its branch is re-planned or handed to you.

Using a separate reviewer matters: the worker that wrote the output is a poor judge of it.

### Holds

A ticket with `needs_human` (a question, or `true` plus a `## Question` section) stops and writes `.dagr/maps/SLUG/questions/Q-<T##>.md`. Answer in that file and set `status: answered` to release it.

### Write-back

When the graph finishes, what was learned is written as notes into your L3 (knowledge) folder, so the next run can retrieve it.

## Run safety

Stray-path hold (a worker that writes outside its ticket's `affects` list stops the run), a pidfile so two runs cannot collide, a back-off on rate limits (HTTP 429), a kill on stalled or over-time workers, and the budget flags (`--max-budget-usd` only counts cost for agents that report it). A final `RUN-SUMMARY` line, also saved as `assets/run-summary.json`, records the result.

Per-run files live in `.dagr/maps/SLUG/`: `map.md`, `tickets/`, `GO.md`, `state.json`, `STATUS.md`, `assets/T##/`.
