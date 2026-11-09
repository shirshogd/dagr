# 05-apply: make the approved edits, safely

## Purpose

Apply exactly the approved items, in order, with a backup of every file before its first edit, and
so that running this stage twice changes nothing the second time.

## Inputs

| File | Why |
|---|---|
| `.dagr/PROPOSAL.md` | the diffs to apply |
| `.dagr/approval.md` | which item numbers are approved |
| `.dagr/scan.md` | line endings and BOM to preserve |

## Process

**Primary method: the engine.** Run
`python -B .dagr/engine/dagr/cli.py apply --root . --items <approved numbers, e.g. 1,2,3>`. It
backs up, writes `MANIFEST.md`, applies the diffs and is idempotent (re-running skips applied
items). Then continue at step 5 below (doctor) and write the apply log from its output. If the
`apply` command does not exist in your copy of the engine, or it fails on an item, use the
manual steps below for what is left. The manual method is the fallback and must produce the same
MANIFEST format.

1. Read `approval.md`. If `status` is not `approved`, stop.
2. Make the backup folder once: `.dagr/backup/<timestamp>/` with a timestamp like
   `20260101-104300` (no colons, so it is valid on Windows).
3. Write `.dagr/backup/<timestamp>/MANIFEST.md`. **Exact format** (the engine's `uninstall`
   parses it; any other shape breaks undo): one line per file you expect to touch, in the form

   ```
   item N  <path>  existing|new
   ```

   Two spaces between the three fields, `<path>` root-relative with `/`, `existing` for a file
   that is already there (backed up) and `new` for one you create (uninstall deletes it, then
   removes emptied parent folders). No table, no bullets, no other columns. Example:

   ```
   item 1  .dagr/config.json  new
   item 2  workflows/newsletter/CONTEXT.md  existing
   item 13  CLAUDE.md  existing
   item 14  .gitignore  new
   ```

   Any other lines (a heading, the list of approved item numbers) are ignored by uninstall.
4. For each approved item, **in numeric order**:
   1. **Idempotency check first.** Decide whether the item is already applied.
      - `add-frontmatter`: the file's frontmatter already has the same `id`, `consumes` and
        `produces`. Skip, record "already applied".
      - `add-file`: the target exists and its bytes equal the proposed content. Skip, record
        "already applied". If it exists with different content, **do not overwrite**: stop and
        report a conflict for that item.
      - `append-block`: the file already contains the `<!-- dagr:begin -->` marker. If the
        block between the markers differs from the proposed block, replace only what is between
        the markers (the block is dagr's own), after backing up. Otherwise skip.
   2. **Back up.** For an existing file, copy it to `.dagr/backup/<timestamp>/<same relative
      path>` (create folders as needed) **before** the first edit. Copy once per run per file.
      Do not back up files that do not exist yet; instead record them in the manifest as `new` so
      uninstall knows to remove them.
   3. **Apply the diff.** Use your file-edit tool, not a shell redirect that could rewrite the
      whole file. Confirm the context lines match what is on disk right now. If they do not, the
      file changed since the proposal: **stop that item**, report it, continue with the others only
      if they do not depend on it.
   4. **Preserve bytes you were not told to change:** line endings (CRLF stays CRLF), BOM, trailing
      newline, tabs versus spaces.
   5. Record the result in the apply log (below).
5. After all items, run `python -B .dagr/engine/dagr/cli.py doctor --root .`. If it reports parse
   errors in a file you edited, restore that file from the backup, mark the item `failed`, and
   report. Do not leave a broken contract behind.
6. Write `.dagr/APPLY-LOG.md`.

## apply log format

```markdown
# Apply log

- run: 20260101-104300
- backup: .dagr/backup/20260101-104300/
- approved: 1,2,3,4,5,6,8,9

| item | file | action | result |
|---|---|---|---|
| 1 | .dagr/config.json | add-file | applied |
| 2 | workflows/newsletter/CONTEXT.md | add-frontmatter | applied |
| 3 | workflows/video-script/CONTEXT.md | add-frontmatter | already applied |
| 9 | CLAUDE.md | append-block | applied |
```

Results are `applied`, `already applied`, `conflict` (stopped, why), `failed` (restored), or
`excluded` (not approved).

## Outputs

- the approved edits in the human's tree
- `.dagr/backup/<timestamp>/` with originals and `MANIFEST.md`
- `.dagr/APPLY-LOG.md`

## Verify

- Every changed pre-existing file has a copy under the backup folder, byte for byte the original.
- No file outside the approved items changed. (In a git repo, `git status` shows exactly the files
  in the log, uncommitted. Do not commit.)
- Re-running this stage produces an apply log where every item is `already applied` and no new
  backup folder holds any copy of a file (a run that applies nothing creates no backup folder).
- `doctor` shows no parse errors.

## Common situations

**Re-run after a partial failure.** Run the stage again. Done items are skipped; failed or
conflicting items are tried again. A new run that applies something gets a new timestamped backup.

**The file changed between proposal and apply** (the human edited it). Stop that item, report the
conflict, and offer to regenerate the proposal item (go back to stage 03 for that item, then 04).

**Existing frontmatter.** The diff inserts lines inside their block. Apply it as a text edit; do
not parse and re-serialise their YAML, which would reorder keys and drop comments.

**CRLF files.** Write your added lines with CRLF. If your edit tool normalises line endings, check
after the edit and fix.

**Windows file locks** (an editor has the file open). Retry once; if still locked, report it.

**Read-only files.** Do not change permissions. Report and skip.

**Approved item depends on an excluded item.** You should have caught this in stage 04. If not,
skip the dependent item and report.

**Git repo.** Leave all changes uncommitted unless the human told you to commit. If they did,
commit only the files in the log, and never `.dagr/backup/` or `.dagr/engine/` unless they ask.
(Whether `.dagr/` is tracked is the human's choice; mention it in the report.)

**Undo.** `python -B .dagr/engine/dagr/cli.py uninstall --root .` restores each file from
`.dagr/backup/` and removes files recorded as `new` in manifests. Describe this to the human; run
it only if asked.
