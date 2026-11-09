# 02-map: infer ports for every workflow

## Purpose

Decide, for each workflow (and optionally each stage), which artifacts it `consumes` and
`produces`. Those are its **ports**. The planner can only chain workflows whose ports match, so
this is the most important judgment in the whole setup. Be conservative: a missing port costs
nothing, a wrong port builds a wrong graph.

## Inputs

| File | Why |
|---|---|
| `.dagr/scan.md` | the list of workflows, contract paths, stage order |
| each workflow's contract (path from scan.md) | the workflow-level Inputs and Outputs |
| each stage's contract (`CONTEXT.md` or `README.md`) | the stage-level Inputs and Outputs tables |
| `templates/contract-frontmatter.md` | the target shape and the naming rules |

Do not read knowledge folders or output files here, except to check that a path named in an
Outputs table is a real file or folder.

## What a port is

A port is a **kebab-case noun naming one artifact**: `brief`, `outline`, `draft-post`,
`script-draft`, `thumbnail-set`, `research-notes`. Rules:

- Lowercase ASCII letters, digits, hyphens. No spaces, no slashes, no file extensions.
- A noun for the thing, not the action. `outline`, not `outlining` or `write-outline`.
- Specific enough to tell apart: `newsletter-draft` and `video-script-draft`, not two things both
  called `draft`. But not so specific that nothing can match: `final-newsletter-v2-for-june` is too
  narrow.
- The same artifact gets the same name everywhere. If one workflow writes "the brief" and another
  reads "the creative brief", pick one name (`brief`) and use it in both.
- Do not make ports for static reference material (style guides, brand files). Those are
  knowledge, found by retrieval, not wired by ports.

## Process

1. For each workflow in `scan.md`, read its contract. Note its Inputs and Outputs.
2. For each stage, read its Inputs and Outputs tables. Read the actual rows, not just headings.
3. **Infer ports from the tables.** The rule:
   - A file or folder a stage **reads** that is **written by an earlier stage** in the same
     workflow is an internal hand-off. It is not a workflow port.
   - A file a stage reads that **no earlier stage writes**, and that lives in an `output/` folder,
     an `inbox/`, an `input/` folder, or is named by the human as "provided by" someone, is a
     **workflow input**: it becomes a `consumes` port.
   - A file a stage **writes** to an output area (usually the last stage's main file) is a workflow
     output: it becomes a `produces` port.
   - Files read from knowledge or reference folders (L3) are not ports.
   - A file one workflow reads from **another workflow's output folder** is a strong signal: the
     two workflows are already wired by hand. Give both sides the same port name.
4. **Name the port** from the artifact's file name or its description in the table. Strip dates,
   versions and extensions: `output/newsletter/2026-01-draft.md` gives `newsletter-draft`.
5. **Assign confidence.**
   - `high`: the tables name the file explicitly, and (for a cross-workflow port) both sides agree.
   - `medium`: the file is named but its role is read from context, or only one side mentions it.
   - `low`: you are guessing from the folder name or prose. **Low means do not propose it.** List it
     as a question instead.
6. **Wire.** Build a table of which workflow `produces` a port another `consumes`. List
   **unbound inputs** (a `consumes` nothing produces; normal for human-supplied inputs such as a
   `topic`) and **dangling outputs** (a `produces` nobody consumes; normal for final deliverables).
7. **Stage ports (optional).** Add stage-level ports only when the human's own tables already name
   distinct artifacts for every stage in a workflow. The workflow level is the minimum. When in
   doubt, skip stage ports.
8. **Write gaps and questions.** Anything you could not settle goes under "Questions" as a short
   question the human can answer in one line, with the options you see.
9. Write `.dagr/ports.md` in the format below.

### Worked example 1: a clear table

`workflows/newsletter/stages/01-research/CONTEXT.md` Inputs:

| File | Why |
|---|---|
| `output/video-script/script.md` | reuse the video's argument |
| `knowledge/audience.md` | who we write for |

Outputs: `output/newsletter/research.md`.

Stage 03 (draft) Outputs: `output/newsletter/draft.md`.

Reading it: `audience.md` is knowledge, so no port. `script.md` is not written by any newsletter
stage and lives in another workflow's output folder, so the newsletter **consumes** it. The
video-script workflow's last stage writes `output/video-script/script.md`, so that workflow
**produces** it. Both sides use `script-draft`. `research.md` is internal. `draft.md` is the final
output: `newsletter-draft`, produced.

Result: newsletter `consumes: [script-draft]`, `produces: [newsletter-draft]`, confidence high.

### Worked example 2: a vague table

A workflow's contract says "Inputs: whatever the client sends" and "Outputs: the deliverable".
There is nothing to name. Do **not** write `consumes: [client-input]`. Record confidence `low`,
leave the ports empty, and ask: "What does the `onboarding` workflow take in (a form, a call
transcript, a folder) and what is the finished artifact called?"

### Worked example 3: medium confidence

A stage reads `inbox/ideas.md` and nothing writes it. Plausibly a human-supplied input. Port
`idea-list`, confidence `medium`, note "assumed human-supplied; confirm". Medium ports are
proposed, but flagged in the proposal for the human to check.

### Worked example 4: no tables at all

A stage `CONTEXT.md` that is only prose ("Write the draft using the outline"). Look for file names
in the prose. `outline` and `draft` are artifacts; but without paths they are `medium` at best.
Prefer workflow-level ports from the workflow contract and skip that stage.

## ports.md format

```markdown
# Ports

generated: 2026-01-01T10:20
convention: kebab-case nouns; confidence high | medium | low (low is not proposed)

## Workflows
| workflow | contract | consumes | produces | confidence | evidence |
|---|---|---|---|---|---|
| newsletter | workflows/newsletter/CONTEXT.md | script-draft | newsletter-draft | high | stage 01 reads output/video-script/script.md; stage 03 writes output/newsletter/draft.md |
| video-script | workflows/video-script/CONTEXT.md | topic-brief | script-draft | high | stage 01 reads inbox/topic.md; stage 03 writes output/video-script/script.md |

## Stage ports (optional)
| workflow | stage | consumes | produces | confidence |
|---|---|---|---|---|

## Wiring
- video-script --script-draft--> newsletter

## Unbound inputs (nothing produces these; expected for human-supplied inputs)
- topic-brief (video-script): human writes inbox/topic.md

## Dangling outputs (nobody consumes these; expected for final deliverables)
- newsletter-draft (newsletter)

## Ids
| workflow | id |
|---|---|
| newsletter | newsletter |

## Questions for the human
1. (question, with the options you see, and which workflow it blocks)

## Not proposed (low confidence)
- (workflow: why)
```

## Outputs

`.dagr/ports.md`

## Verify

- Every port is kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`) and has a confidence.
- Every `high` or `medium` port has an evidence cell naming a real file or table row.
- No `low` port appears in the Workflows table.
- Every cross-workflow wire uses one name on both sides.
- No port names a knowledge file.
- Run `python -B .dagr/engine/dagr/cli.py ports --root .` (it reads existing frontmatter only, so
  it will usually say nothing yet). If it lists ports the human already declared, reconcile your
  names with theirs and prefer theirs.

## Common situations

**The human already declared `consumes`/`produces` (maybe under other names such as `inputs:`).**
Keep their keys and values. Only add what is missing, and say so in evidence. If their key is
`inputs:` rather than `consumes:`, list it as a question; do not rename it.

**Workflow-level contract has no Inputs/Outputs, but the stages do.** Derive the workflow ports
from the first stage's external reads and the last stage's writes. Confidence `medium`.

**Stages that read from several earlier stages (fan-in), or write several files (fan-out).** Keep
one port per distinct artifact. If a stage writes a folder of items (`output/thumbnails/*.png`),
use one plural noun (`thumbnail-set`).

**A workflow has two separate output kinds** (a post and an image set). Two produce ports.

**Different spellings of one artifact** across stages or workflows. Pick the shortest clear name,
record the aliases in evidence, and do not create two ports.

**Numbered vs unnumbered stages.** For unnumbered stages whose order is unverified, do not infer
"earlier stage writes it" claims. Mark the port `medium` and ask.

**Workflows under lines or departments.** Ports are global across the whole root, so a name used in
one department must mean the same artifact in another. Prefix only if two artifacts truly clash
(`sales-brief` vs `design-brief`), and then use the prefix everywhere.

**Monorepo.** Ports are per root. Never wire across roots.

**Windows paths in tables** (`output\draft.md`). Normalise to `/` when you compare, and leave the
human's table untouched.

**Non-English tables.** Read by meaning. Port names stay English kebab-case ASCII; add the
human's term in the evidence cell.

**You cannot tell whether a thing is a port or knowledge.** Ask: "Is `X` produced fresh for each
run (a port) or kept and reused (knowledge)?"
