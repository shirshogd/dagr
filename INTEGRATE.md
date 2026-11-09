# INTEGRATE.md: turn the user's ICM into a graph-engineering setup

You are an AI coding agent. The human asked you something like
"Integrate https://github.com/shirshogd/dagr into my ICM". This file is your entry point.

## What you are about to do (5 lines)

1. Scan the human's existing ICM folders (an "ICM" is a tree of `CONTEXT.md` contracts: a root
   agent file, a routing table, one contract per workflow and per stage).
2. Work out what each workflow consumes and produces (its "ports").
3. Write one proposal file, `.dagr/PROPOSAL.md`, showing every edit as a diff.
4. Apply only the items the human approves, with backups.
5. Check the result, then report. Nothing runs and nothing costs money until the human says `go`.

Result: any multi-step request becomes a DAG (a directed acyclic graph: tasks with arrows, no
loops) of stages that agents run in parallel. A separate reviewer scores each output.

## Golden rules

1. **Read-only until approval.** Stages 01 to 04 write only inside `.dagr/`. Stage 05 is the first
   time you touch the human's own files, and only for approved items.
2. **Never delete, rename or move a user file.** Edits are additions: frontmatter at the top of a
   contract, a new file, or an appended block.
3. **Every change goes in `.dagr/PROPOSAL.md`** as a numbered item with a diff. No change exists
   outside the proposal.
4. **Back up before you edit.** Copy each file to `.dagr/backup/<timestamp>/` (same relative path)
   before the first edit to it.
5. **Do not guess.** If you cannot infer something with at least medium confidence, write it as a
   question for the human in `.dagr/ports.md`. A wrong port is worse than a missing one.
6. **Stop and ask if the tree is not ICM-shaped.** If there is no root agent file and no
   contracts of any kind, say so, and offer a minimal ICM scaffold as a separate proposal
   (see `setup/01-scan/CONTEXT.md`, "Not ICM-shaped"). Do not scaffold unasked.
7. **Stay inside the human's root.** Never write outside it. Never push, publish or commit
   unless the human asks. (Applying changes to a git repo leaves them uncommitted.)
8. **Prose stays theirs.** Never rewrite their wording. Add around it.

## Step 0: get the engine

The engine is stdlib-only Python (3.9 or newer). No pip install.

1. Locate the dagr repo: use the clone you are reading, or clone it to a temp folder outside the
   human's tree (for example `git clone https://github.com/shirshogd/dagr <tmp>/dagr`).
2. Decide the **root**: the folder that holds the human's L0 file (`CLAUDE.md`, `AGENTS.md`,
   `GEMINI.md`, `.cursorrules`) and root `CONTEXT.md`. If there are several candidates, see
   `setup/01-scan/CONTEXT.md` ("Common situations") and ask which one.
3. Copy `engine/dagr/` from the clone to `<root>/.dagr/engine/dagr/`. (Creating `.dagr/` is the
   one write allowed before approval; it is dagr's own folder and removable.)
4. Check it runs: `python -B .dagr/engine/dagr/cli.py doctor --root .` from the root. On
   Windows use `python` or `py -3`; paths below use `/` but `\` works too. A tree with 0 contracts exits 0
   and prints "no contracts yet"; that is fine. A Python traceback is not: stop and tell the human.

All commands below are run from the root as `python -B .dagr/engine/dagr/cli.py <cmd>`.

## The 6 stages, in order

Read `setup/CONTEXT.md` once, then do each stage by opening its `CONTEXT.md` and following it.
Each stage names the exact files to load. Load nothing else.

| # | Stage | You write | Stops for the human? |
|---|---|---|---|
| 01 | [scan](setup/01-scan/CONTEXT.md) | `.dagr/scan.md` | only if the root is unclear or the tree is not ICM-shaped |
| 02 | [map](setup/02-map/CONTEXT.md) | `.dagr/ports.md` | no (gaps become questions) |
| 03 | [propose](setup/03-propose/CONTEXT.md) | `.dagr/PROPOSAL.md` | no |
| 04 | [approve](setup/04-approve/CONTEXT.md) | `.dagr/approval.md` | **yes: this is the gate** |
| 05 | [apply](setup/05-apply/CONTEXT.md) | the approved edits, `.dagr/backup/` | no |
| 06 | [verify](setup/06-verify/CONTEXT.md) | `.dagr/VERIFY.md` | no |

Templates you copy from live in `templates/`. A finished example (before and after) is in
`examples/`. Read the example if you are unsure what good output looks like.

## If the human asks to undo

`python -B .dagr/engine/dagr/cli.py uninstall --root .` restores everything from `.dagr/backup/`
and removes `.dagr/`. Ask for `--yes` only after the human confirms.

## Report format (end of stage 06)

Keep it short: what you found (workflows, stages), what you changed (item numbers), what is
untested or uncertain, and one "try it" line the human can paste. dagr is new; say plainly which
parts have not been exercised on their tree.
