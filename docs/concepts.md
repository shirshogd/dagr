# Concepts

Short definitions, in the order you meet them.

## ICM

Interpretable Context Methodology, from the paper by J. Van Clief and D. McDermott, [arXiv:2603.16021](https://arxiv.org/abs/2603.16021) (MIT licensed). The idea: the folder structure is the agent architecture. Instead of one giant prompt, you give an agent a small map and let it load only the files each job names.

| Layer | What it is |
|---|---|
| L0 | The root agent file: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, or `.cursorrules`. |
| L1 | A root `CONTEXT.md`: a routing table from request type to workflow. |
| L2 | One `CONTEXT.md` per workflow and per stage, with an **Inputs** table, a Process, and Outputs. |
| L3 | Reference and knowledge folders. |
| L4 | `output/` folders where results land. |

## Workflow and stage

A **workflow** is a folder for one kind of job, such as "write a weekly report". A **stage** is one step inside it, often a numbered folder (`01-gather`, `02-draft`). Each has a `CONTEXT.md`.

## Contract

The `CONTEXT.md` of a workflow or stage. It tells an agent what to load, what to do, and what to produce. If you use a `README.md` that way, dagr treats it as a contract too.

## Port

A named input or output declared on a contract, in frontmatter:

```yaml
---
id: weekly-report
consumes: [raw-notes]
produces: [report-draft]
---
```

`consumes` lists what the workflow needs. `produces` lists what it makes. Stage-level ports are optional; the workflow level is the minimum. A port name is just a label you choose. Two things connect when one produces the label the other consumes.

An **unbound input** is a consumed port nothing produces. `dagr ports` lists them. A **mismatch** is two near-identical names that probably mean the same thing (`notes` and `raw-notes`).

## DAG

A directed acyclic graph: tasks joined by "this needs that first" arrows, with no loops. `dagr doctor` reports cycles because a loop means nothing could ever start.

## Plan, map, ticket

- A **plan** is the DAG built from your request.
- The **map** (`map.md`) is the plan written out as a readable file.
- A **ticket** (`tickets/T##-name.md`) is one node: its title, status, what blocks it, which paths it may touch (`affects`), which model to use, and whether it needs a person.

## Go

The approval act. `dagr go SLUG` writes `GO.md`. No spending happens before it.

## Worker

A headless agent process that does one ticket. The command line comes from `.dagr/config.json` under `workers`. `claude`, `codex`, and `opencode` are built in. `custom` takes a `command` string with placeholders such as `{brief_file}` and `{cwd}`.

## Reviewer

A separate model call that scores one output from 0 to 1 against the rubric in your tree. 0.8 or more passes. Below it, the ticket retries with notes, up to 3 attempts.

## Hold

A pause waiting for a person. A ticket with `needs_human` writes a question file, `questions/Q-T##.md`, under the map. You answer it and set `status: answered`. A stray-path hold happens when a worker touches files outside `affects`.

## Write-back

The last stage of `graph-loop`: notes learned during the run are saved in your L3 folder so later runs can find them.

## Backup

Before any edit during setup, the original goes to `.dagr/backup/<timestamp>/`. `dagr uninstall` restores from there and removes `.dagr/`.
