---
id: graph-loop
consumes: [request]
produces: [map, run-receipts, learned-notes]
---

# graph-loop: request, map, one go, reviewed run, write-back

**Trigger:** a multi-step request: more than one session of work, several deliverables, or work
that crosses more than one of the workflows under `{{workflows_root}}`. A single-step job goes
straight to its own workflow and does not need this loop.

**How it works.** You brainstorm the request with the human, retrieve what the human's knowledge
folders already say, and turn the request into a DAG (a graph of tickets with arrows and no loops)
by wiring the `consumes` and `produces` ports of the workflows under `{{workflows_root}}`. The human
approves the whole graph once with `go`. A runner launches every ready ticket as a headless agent;
independent tickets run in parallel. A separate reviewer scores each output (pass at 0.8, up to 3
attempts). What was learned is written back into the knowledge folders so the next request finds it.

Engine: `{{engine_cmd}}` (default: `python -B .dagr/engine/dagr/cli.py`).

<!-- template-only:begin -->
## Placeholders (template-only: delete this whole section, markers included, when you copy this file)

| placeholder | meaning | where it comes from |
|---|---|---|
| `{{workflows_root}}` | folder holding the human's workflows | `.dagr/config.json` |
| `{{contract_name}}` | `CONTEXT.md` or `README.md` | scan.md |
| `{{knowledge_dirs}}` | the human's L3 folders, comma-separated | scan.md |
| `{{notes_dir}}` | the one knowledge folder write-back writes to | proposal item, chosen from `knowledge_dirs` |
| `{{output_dirs}}` | the human's L4 folders | scan.md |
| `{{l0_file}}` | the human's root agent file | scan.md |
| `{{engine_cmd}}` | the engine command | always `python -B .dagr/engine/dagr/cli.py` |
| `{{workflow_ids}}` | ids of the human's workflows | ports.md |
<!-- template-only:end -->

## Stages

| # | Stage | Output |
|---|---|---|
| 01 | [brainstorm](stages/01-brainstorm/{{contract_name}}) | request statement and first test case |
| 02 | [retrieve](stages/02-retrieve/{{contract_name}}) | `.dagr/maps/<slug>/assets/pack.md` |
| 03 | [plan-to-graph](stages/03-plan-to-graph/{{contract_name}}) | `map.md` and `tickets/T##-*.md` |
| 04 | [go](stages/04-go/{{contract_name}}) | `GO.md` |
| 05 | [run](stages/05-run/{{contract_name}}) | work outputs, `STATUS.md`, `run-summary.json` |
| 06 | [review](stages/06-review/{{contract_name}}) | verdicts and an integration review |
| 07 | [write-back](stages/07-write-back/{{contract_name}}) | notes filed in `{{notes_dir}}` |

## Two rules for the planner

**Rule A: find the class.** An example in the request is a sample of a class of work. Scope the
graph to the class and use the example as the first test case.

**Rule B: reuse before you build.** Every proposed ticket names the existing workflow it reuses.
Only propose new work where no workflow under `{{workflows_root}}` fits, and say so.

## Inputs

The request, and the human's reason for it. Each stage's own Inputs table names exactly what it
loads. Context for this folder lives in `{{l0_file}}`.

## Outputs

A map under `.dagr/maps/<slug>/`: `map.md`, `tickets/`, `assets/pack.md`, `GO.md`, `state.json`,
`STATUS.md`, plus learned notes in `{{notes_dir}}`.

## Verify

- No ticket ran before `GO.md` existed.
- Every closed ticket has a reviewer verdict from a different agent than the worker.
- The retrieve stage's pack was used by the planning stage.

## Done when

All seven stages' Done-when conditions hold, and the next request in the same area retrieves what
this run learned without being told where to look.
