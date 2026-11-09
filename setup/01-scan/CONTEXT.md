# 01-scan: inventory the human's tree

## Purpose

Find out what ICM the human has, without judging or changing it. Produce an inventory that later
stages read instead of re-walking the tree. The deterministic part is done by the engine; you add
the judgment the engine cannot (as an appended section; the engine's output stays as written) (which file is really a contract, which tree is the real root).

## Inputs

| File | Why |
|---|---|
| the human's tree (read-only) | the thing being scanned |
| `<root>/.dagr/engine/dagr/cli.py` | the `scan` command (engine copied in Step 0 of `INTEGRATE.md`) |
| `templates/contract-frontmatter.md` | so you know the shape of what you will later add and can spot look-alikes |

## Process

1. Run `python -B .dagr/engine/dagr/cli.py scan --root .`. It writes `.dagr/scan.json` and a first
   `.dagr/scan.md`. If the command is unavailable or fails, do the same walk by hand with your
   file tools; do not stop.
2. Find the **L0 file(s)**: any of `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`,
   `.github/copilot-instructions.md`, `.windsurfrules` at the root. Record each. If there are
   several, note which one the human's main agent reads (ask if not obvious).
3. Find the **L1 routing table**: root `CONTEXT.md`, or a table inside L0, or a `README.md` that
   routes. Record where it is. It is fine if there is none.
4. Find the **workflows area**. Look for a folder whose children each hold a contract and stage
   folders: `workflows/`, `lines/*/workflows/`, `departments/*/`, `projects/*/`, `playbooks/`,
   `pipelines/`, or the root itself. Record the path pattern. See Common situations for nesting.
5. For each workflow, list its **stages** in order. Detect numbering (`01-x`, `01_x`, `1-x`,
   `step-1`, none). For unnumbered stages, order by the workflow contract's own stage table; if
   there is none, order alphabetically and flag it `order-unverified`.
6. Find **knowledge and reference folders** (L3): `knowledge/`, `references/`, `docs/`, `_context/`,
   `notes/`, `wiki/`, `research/`, `brand/`, `style/`. Record paths. These feed the retrieve stage
   of graph-loop (`{{knowledge_dirs}}`).
7. Find **output folders** (L4): `output/`, `outputs/`, `out/`, `dist/`, `_output/`, `runs/`.
8. Record **frontmatter state** per contract: `none`, `present-no-dagr-keys`, `has-ports`, or
   `unparseable`.
9. Record the language, line endings (CRLF or LF) and BOM of the L0 file and a few contracts.
10. Record whether the root is a git repo (`.git/` present) and the path style you observed.
11. **The engine-written `.dagr/scan.md` is canonical.** Do not rewrite or reformat it. If you
    corrected or added anything (the real root, a look-alike contract, `order-unverified`, line
    endings, language, `shape`, oddities), APPEND a `## Agent notes` section at the end with your
    judgment, one bullet each. Later stages read the engine part first, then your notes, and your
    notes win where they disagree. If the engine command failed and you walked the tree by hand,
    write `scan.md` yourself in the shape below.

### scan.md shape (engine output; hand-walk fallback)

```markdown
# Scan

- root: .
- scanned: 2026-01-01T10:00
- git: yes | no
- line-endings: lf | crlf | mixed
- language: en
- shape: icm | partial | not-icm

## L0 files
| file | notes |
|---|---|
| CLAUDE.md | main agent file, 64 lines |

## L1 routing
| file | notes |
|---|---|
| CONTEXT.md | table of workflows |

## Workflows area
- path pattern: workflows/*/
- contract name: CONTEXT.md

## Workflows
| id | path | contract | stages | numbering | frontmatter |
|---|---|---|---|---|---|
| newsletter | workflows/newsletter | CONTEXT.md | 3 | 01-x | none |

## Knowledge folders
- knowledge/ (7 files)

## Output folders
- output/newsletter/
- output/video-script/

## Oddities
- (anything unusual, one bullet each)
```

## Outputs

- `.dagr/scan.json` (engine, machine-readable)
- `.dagr/scan.md` (engine, plus your appended `## Agent notes`)

## Verify

- Every workflow found appears once in the table, with a path that exists.
- Every stage folder you counted exists on disk.
- `shape` is set. If it is `not-icm`, you stopped and asked (below).
- You wrote nothing outside `.dagr/`.

## Common situations

**Not ICM-shaped.** No L0 file, no `CONTEXT.md`, no README contracts, just loose files. Stop.
Tell the human: "This folder does not look like an ICM, so there is nothing to attach graph
engineering to yet." Offer a **minimal ICM scaffold as a separate proposal**: a root `CLAUDE.md`
(or `AGENTS.md`), a root `CONTEXT.md` routing table, and one example workflow with stage contracts
for the one process they describe. Write it as `.dagr/SCAFFOLD-PROPOSAL.md` using the PROPOSAL
format from stage 03, and wait. Do not continue to stage 02 until the human approves the scaffold
or points you to a different root.

**Partially ICM.** An L0 file and some `CONTEXT.md` files, but gaps (a workflow with no contract,
a missing routing table). Continue. Record the gaps under Oddities. Never invent a contract for a
folder that has none; ask.

**Multiple L0 files.** Common (`CLAUDE.md` plus `AGENTS.md`, often one a copy of the other). Record
all and note whether they differ. dagr's L0 block goes in every L0 file that is a real file, so
every agent sees it. Ask only if they differ on purpose (different instructions per agent).

**No `CONTEXT.md`, but `README.md` contracts.** Treat a `README.md` as the contract when it has an
Inputs, Process or Outputs shape, or sits at workflow or stage level next to stage folders. Record
`contract: README.md` per workflow. Do not add `CONTEXT.md` files; put frontmatter in the README.

**Numbered vs unnumbered stages.** Both are fine. Record the order you used and how you got it.
If the workflow contract has a stage table, trust it over folder names.

**Workflows nested under "lines" or "departments".** A tree like `lines/content/workflows/blog/`
or `departments/marketing/campaigns/launch/` is one workflows area with a deeper pattern. Record
the pattern. Give each workflow an id that includes its parent only if bare names collide
(`content-blog`, not just `blog`, when another `blog` exists). The graph-loop template goes in the
shallowest folder that holds all the workflows, or in a planning-style line if one exists.

**Monorepo with several ICM roots.** Several folders each have their own L0 file. Do not merge
them. List the candidates, ask the human which one to integrate, and run the whole setup once per
root, each with its own `.dagr/`. If a parent L0 file points down to child roots, integrate the
parent only when the human says so.

**Frontmatter already present.** Note which keys exist. Stage 03 merges; it never replaces. If a
file's frontmatter does not parse, record it as `unparseable`, do not touch it, and list it as a
question.

**Windows.** Paths may contain backslashes, drive letters or spaces. Record them root-relative
with `/`. Check CRLF. Every command works with `python` on Windows (`py -3` also works). Report
paths over 260 characters as an oddity.

**Huge trees.** Ignore `node_modules/`, `.git/`, `.venv/`, `dist/`, build folders and anything
gitignored that is not an output folder. Say what you ignored.

**Non-English contracts.** Headings may be `Eingaben` or `Entradas` instead of `Inputs`. Map them
by meaning and record the human's heading names under Oddities so stage 02 can read them.
