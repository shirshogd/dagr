# 03-propose: write PROPOSAL.md

## Purpose

Turn the port map into one reviewable file: every change dagr wants to make to the human's tree,
as a numbered item with a diff, a reason and a risk. The human reads this file and nothing else
to decide. If a change is not in it, it must not happen.

## Inputs

| File | Why |
|---|---|
| `.dagr/scan.md` | paths, line endings, which L0 files exist |
| `.dagr/ports.md` | ports, confidence, questions |
| `templates/contract-frontmatter.md` | frontmatter shape and merge rules |
| `templates/graph-loop/` (whole folder) | the workflow to add, with `{{placeholders}}` |
| `templates/l0-pointer.md` | the block to add to the L0 file(s) |
| `templates/cursor-rule.mdc` | the Cursor rule file, when the scan found Cursor |
| `<root>/.dagr/engine/dagr/cli.py` | to write `config.json` fields consistently (see item 1) |

## Item types (only these three)

| action | meaning | When |
|---|---|---|
| `add-frontmatter` | insert or merge a YAML block at the top of an existing contract | one per workflow contract (and per stage if stage ports were mapped) |
| `add-file` | create a new file that does not exist | `.dagr/config.json`, each graph-loop file, `.cursor/rules/dagr.mdc`, `.gitignore` when absent, the optional `<knowledge>/notes/` folder; nothing else |
| `append-block` | add a delimited block at the end of an existing file | the L0 file(s); the existing `.gitignore`; optionally the L1 routing table |

There is no `edit`, `replace`, `delete`, `rename` or `move`. If you think you need one, you do not.
Ask the human instead.

## Item format

Each item uses exactly this shape, so stage 04 can count and stage 05 can parse them:

````markdown
### 3. add-frontmatter: workflows/newsletter/CONTEXT.md

- file: workflows/newsletter/CONTEXT.md
- action: add-frontmatter
- confidence: high
- risk: low

Why: declares that this workflow turns a `script-draft` into a `newsletter-draft`, so the
planner can run it after video-script.

```diff
--- a/workflows/newsletter/CONTEXT.md
+++ b/workflows/newsletter/CONTEXT.md
@@ -1,3 +1,8 @@
+---
+id: newsletter
+consumes: [script-draft]
+produces: [newsletter-draft]
+---
 # Newsletter
 
 Weekly email for subscribers.
```
````

Required fields on every item: **number, file, action, confidence, risk, why, diff**. Risk is
`low`, `medium` or `high` with a few words if not low. A diff is a real unified diff: `---`/`+++`
headers, `@@` hunks, three lines of context. For `add-file`, the diff is against `/dev/null`
(`--- /dev/null`, `+++ b/<path>`) and shows the whole file.

## Process

1. Create `.dagr/PROPOSAL.md` with this header, then items:

   ```markdown
   # dagr proposal

   - root: .
   - generated: 2026-01-01T10:30
   - items: 9
   - nothing in this file has been applied
   - reply in the chat with: approve | approve except 3,5 | edit 4: <change> | cancel

   ## Summary
   (5 lines: what dagr will add, how many files touched, anything risky)

   ## Open questions
   (copy the blocking questions from ports.md; the human may answer them with the approval)

   ## Items
   ```
2. **Item 1: `add-file: .dagr/config.json`.** Fields:
   `root`, `l0_files` (list), `workflows_root` (where graph-loop goes), `workflow_glob`,
   `knowledge_dirs` (list), `output_dirs` (list), `contract_name` (`CONTEXT.md` or `README.md`),
   `workers` (leave the engine's defaults, do not invent commands), `created`. All paths relative
   with `/`. Show the full file in the diff.
3. **One `add-frontmatter` item per workflow** that has at least one `high` or `medium` port or
   a clear id. Compute the diff for real: read the file, produce the exact result.
   - No frontmatter: insert the block above line 1. Keep a leading BOM before `---` only if the
     file had one (the BOM stays at byte 0).
   - Frontmatter exists: **merge**. Keep every existing key and its order. Add only `id` (if
     absent), `consumes`, `produces`. If a key exists with other values, do not overwrite: add
     your values to the list and say so in Why, or ask. Leave their comments in place. Show the
     merge as a diff inside the existing block.
   - If frontmatter exists but does not parse: do not propose an edit; put it under Open questions.
   - A `README.md` used as a contract gets the same treatment.
   - Keep the file's line endings (CRLF files get CRLF in the diff content).
4. **Stage-level frontmatter items** only if stage ports were mapped; same rules.
5. **Graph-loop items:** one `add-file` per file in `templates/graph-loop/` (the workflow
   `CONTEXT.md` plus seven stage contracts, plus `templates/reviewer-rubric.md` copied as
   `graph-loop/reviewer-rubric.md`), placed at `<workflows_root>/graph-loop/...`. Delete the
   `<!-- template-only -->` section of the workflow `CONTEXT.md` in the copy. Fill every `{{placeholder}}` from scan.md and config. See
   the placeholder table in `templates/graph-loop/CONTEXT.md`. No `{{` may remain in a proposed
   file. If the human's workflows use `README.md` as contract, name graph-loop's files the same
   way (`README.md`), and mention it in Why. If numbering is `01_x`, use underscores to match.
   If a path would collide with an existing file, do not overwrite: choose `graph-loop-dagr/`
   and say why.
6. **L0 items:** one `append-block` per L0 file, using `templates/l0-pointer.md`, with the
   `<workflows_root>/graph-loop/CONTEXT.md` path filled in. `CLAUDE.md`, `AGENTS.md` and
   `GEMINI.md` all get the same markdown block, wrapped in `<!-- dagr:begin -->` and
   `<!-- dagr:end -->` markers so re-runs are idempotent.
   **Cursor:** if the scan found `.cursor/` or `.cursorrules`, do NOT edit `.cursorrules`. Propose
   `add-file: .cursor/rules/dagr.mdc` from `templates/cursor-rule.mdc` (frontmatter
   `description` + `alwaysApply: true`, then the same pointer text). If the file already exists with
   different content, do not overwrite; ask.
7. **L1 item:** if the root `CONTEXT.md` has a routing table, propose a diff that **inserts a
   row** for graph-loop inside the table, in place, matching their columns and wording (not a
   block at the end of the file). The item's action is `append-block`; the row sits between
   `<!-- dagr:begin -->` / `<!-- dagr:end -->` comment lines only if the table tolerates it, else
   just the row, with a Why note. If no insertion fits the table's format, say so in Open
   questions instead.
7a. **`.gitignore` item (always).** If `.gitignore` exists: `append-block` (markers
   `# dagr:begin` / `# dagr:end`); if absent: `add-file`. Block:

   ```gitignore
   # dagr:begin
   # dagr
   .dagr/engine/
   .dagr/backup/
   .dagr/maps/*/assets/**/worker-*.out
   .dagr/maps/*/assets/**/worker-*.err
   .dagr/maps/*/assets/**/*.prompt.txt
   .dagr/maps/*/assets/*.pid
   # dagr:end
   ```

   Maps, tickets, `GO.md`, verdicts and state stay tracked: they are the audit trail. Say so in
   Why. (The patterns are the files the engine really writes: worker stdout/stderr/prompt per
   attempt, and `runner.pid`.)
7b. **Notes folder (write-back target).** Default: `{{notes_dir}}` is the first knowledge dir.
   **Exception:** if their L0 or L1 describes the knowledge folder as read-only, reference-only,
   canonical or "never edit", default `{{notes_dir}}` to a new `<knowledge>/notes/` instead and
   propose `add-file: <knowledge>/notes/README.md` (one line saying what the folder is). Otherwise
   offer that same item as optional (the human may decline it). Decide this before writing the
   graph-loop files so `{{notes_dir}}` is filled consistently; if the item is optional and
   undecided, fill the default and list the choice under Open questions.
8. **Order the items** so each depends only on earlier ones: config, then frontmatter, then
   graph-loop files, then the optional notes folder, then L0/Cursor/L1 blocks, then `.gitignore` last.
9. Update `items:` in the header to the true count.
10. **Generate diffs mechanically.** Produce each diff with a script or the engine where
    possible, not by hand. Before presenting, check that every diff applies: use the engine's
    dry-run (`apply --dry-run`) if your copy of the engine has it; otherwise re-read each diff
    against the file as it is on disk now.
11. Self-check against Verify before you hand over.

## Outputs

`.dagr/PROPOSAL.md`

## Verify

- Header count equals the number of `### N.` items; numbers are consecutive from 1.
- Every item has all seven fields; action is one of the three allowed.
- Every `add-frontmatter` and `append-block` target exists on disk now. Every `add-file` target
  does not.
- Every diff applies cleanly to the current file (re-read the file and check the context lines).
- No item touches a path outside the root, and none touches `.dagr/` except item 1.
- No `{{` appears anywhere in the proposal.
- Every port in the proposal appears in `ports.md` with confidence `high` or `medium`.
- No file would lose any existing byte: removing the added lines from a diff must give the original.

## Common situations

**Multiple L0 files.** One `append-block` item each, same block. If one is a symlink to another,
do it once.

**README contracts / no CONTEXT.md.** Frontmatter goes in the README. Do not create new
`CONTEXT.md` files next to them.

**Numbered vs unnumbered stages.** graph-loop's stage folders copy the human's style. If the human
numbers stages `1-x`, use `1-brainstorm`; if they do not number, use bare names and let the
workflow contract's table give the order.

**Nested workflows (lines, departments).** `workflows_root` is the shallowest common folder. If
there is none (workflows scattered), propose `<root>/workflows/graph-loop/` and say so as a medium
risk.

**Existing frontmatter.** Show the merged result as a diff on the existing block. Example: they
have `title: Newsletter` and `tags: [email]`; the diff adds three lines inside the block and leaves
both of theirs.

**Monorepo.** One proposal per root. Never mix roots in one file.

**Windows.** Use `/` in `file:` fields and diff headers. Keep CRLF in added lines for CRLF files.
Do not add BOMs to files that had none.

**A workflow you could not map.** Do not propose frontmatter. List it under Open questions with
the specific question.

**The human has no L0 file.** If the human has an L1 `CONTEXT.md` but no L0 file, propose
`add-file: AGENTS.md` containing only the dagr block, as a separate, clearly marked item and
mark risk `medium`: it creates a new agent entry file they did not have.
