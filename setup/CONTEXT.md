# setup: the dagr integration workflow

This folder is itself an ICM workflow. You (the agent) run it against the human's folder tree.
It has six stages. Each stage has a `CONTEXT.md` with Purpose, Inputs, Process, Outputs, Verify
and Common situations. Do them in order. Do not skip ahead and do not load files a stage does not
list in its Inputs table.

## Stages

| # | Stage | Reads | Writes | Gate |
|---|---|---|---|---|
| 01 | [scan](01-scan/CONTEXT.md) | the human's tree | `.dagr/scan.json`, `.dagr/scan.md` | none |
| 02 | [map](02-map/CONTEXT.md) | `scan.md` + each contract | `.dagr/ports.md` | none |
| 03 | [propose](03-propose/CONTEXT.md) | `ports.md`, `templates/` | `.dagr/PROPOSAL.md` | none |
| 04 | [approve](04-approve/CONTEXT.md) | `PROPOSAL.md` | `.dagr/approval.md` | the human |
| 05 | [apply](05-apply/CONTEXT.md) | `PROPOSAL.md`, `approval.md` | edits, `.dagr/backup/` | approved items only |
| 06 | [verify](06-verify/CONTEXT.md) | the result | `.dagr/VERIFY.md` | none |

## Vocabulary

- **Root**: the folder holding the human's L0 file. All `.dagr/` paths are relative to it.
- **L0 / L1 / L2 / L3 / L4**: root agent file / root `CONTEXT.md` routing table / one contract per
  workflow and per stage / knowledge and reference folders / `output/` folders. Their tree may use
  other names or skip layers. Layers are a way to read the tree, not a requirement.
- **Contract**: a `CONTEXT.md` (or `README.md` used the same way) that says what a workflow or
  stage reads, does and writes.
- **Port**: a kebab-case noun naming an artifact that crosses between workflows or stages, such as
  `brief`, `outline`, `draft-post`. A workflow lists the ports it `consumes:` and `produces:`.
  The planner wires one workflow's `produces` to another's `consumes`.
- **DAG**: the graph of tickets the planner builds from a request.

## Rules that hold in every stage

1. Stages 01 to 04 write only inside `.dagr/`.
2. Never delete, rename or move a user file. Additions only.
3. Back up before any edit (stage 05 does this; no one else edits).
4. Confidence is `high`, `medium` or `low`. Anything `low` becomes a question for the human.
   It does not become a port.
5. Windows and POSIX both occur. Record paths in `.dagr/` files with forward slashes, relative to
   the root. Keep each file's original line endings (CRLF or LF) when you edit it, and keep its
   BOM if it has one.
6. Preserve the human's language. If their contracts are in German, the ports you add are still
   kebab-case ASCII nouns, but "why" lines in the proposal can use the human's language. Ask if
   unsure.
7. When something is ambiguous, ask. Put questions in `.dagr/ports.md` under "Questions", and
   repeat the blocking ones to the human at stage 04.

## State

`.dagr/state.md` is optional. If you are interrupted, write one line per finished stage there so a
fresh agent can resume: `01-scan done 2026-01-01T10:00`. Re-running any stage is safe; stages 01
to 04 overwrite their own output, and stage 05 is idempotent.
