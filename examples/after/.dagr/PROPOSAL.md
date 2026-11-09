# dagr proposal

- root: .
- generated: 2026-01-12T10:30
- items: 16
- nothing in this file has been applied
- reply in the chat with: approve | approve except 3,5 | approve only 1,2 | edit 4: <change> | cancel
- example note: to keep this example readable, the diffs for the graph-loop files (items 4 to 12)
  are shortened to their first lines. A real proposal shows each file in full.

## Summary

- 2 workflows found (video-script, newsletter), 6 stages. Both have clear ports and are wired:
  video-script produces `script-draft`, newsletter consumes it.
- dagr adds 3 lines of frontmatter to each of 2 workflow contracts, adds one new `workflows/graph-loop/`
  folder (9 files), creates `knowledge/notes/` for write-back (your `knowledge/` is read-only), appends one block to
  `CLAUDE.md`, inserts one row in `CONTEXT.md`, adds a `.gitignore`, and creates `.dagr/config.json`.
- No existing line of yours is changed. No file is deleted, renamed or moved.
- Riskiest item: 14 (it edits your main agent file). It is an appended, marked block.

## Open questions

1. Is `inbox/topic.md` a port (`topic-brief`)? Assumed yes. (see `ports.md`)

## Items

### 1. add-file: .dagr/config.json

- file: .dagr/config.json
- action: add-file
- confidence: high
- risk: low

Why: tells the engine where your workflows, knowledge folders and outputs are.

```diff
--- /dev/null
+++ b/.dagr/config.json
@@ -0,0 +1,14 @@
+{
+  "root": ".",
+  "l0_files": ["CLAUDE.md"],
+  "workflows_root": "workflows",
+  "workflow_glob": "workflows/*/",
+  "contract_name": "CONTEXT.md",
+  "knowledge_dirs": ["knowledge"],
+  "output_dirs": ["output"],
+  "workers": { "claude": "(engine default, unchanged)", "...": "..." },
+  "created": "2026-01-12T10:30:00"
+}
```

### 2. add-frontmatter: workflows/video-script/CONTEXT.md

- file: workflows/video-script/CONTEXT.md
- action: add-frontmatter
- confidence: high
- risk: low

Why: declares that this workflow needs a `topic-brief` (your inbox/topic.md) and leaves a
`script-draft`, so a planner can run newsletter after it.

```diff
--- a/workflows/video-script/CONTEXT.md
+++ b/workflows/video-script/CONTEXT.md
@@ -1,3 +1,8 @@
+---
+id: video-script
+consumes: [topic-brief]
+produces: [script-draft]
+---
 # Video script
 
 Turns a one-line topic into a spoken script for the weekly video.
```

### 3. add-frontmatter: workflows/newsletter/CONTEXT.md

- file: workflows/newsletter/CONTEXT.md
- action: add-frontmatter
- confidence: high
- risk: low

Why: declares that the newsletter consumes the video's `script-draft` and produces a
`newsletter-draft`. This is the wire between the two workflows.

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
 
 Weekly email that follows the week's video.
```

### 4. add-file: workflows/graph-loop/CONTEXT.md

- file: workflows/graph-loop/CONTEXT.md
- action: add-file
- confidence: high
- risk: low

Why: the front door for multi-step requests. Filled from `templates/graph-loop/CONTEXT.md`:
`workflows`, `CONTEXT.md`, `knowledge/`, `output/`, `CLAUDE.md`.

```diff
--- /dev/null
+++ b/workflows/graph-loop/CONTEXT.md
@@ -0,0 +1,74 @@
+---
+id: graph-loop
+consumes: [request]
+produces: [map, run-receipts, learned-notes]
+---
+
+# graph-loop: request, map, one go, reviewed run, write-back
(... shortened for this example ...)
```

### 5. add-file: workflows/graph-loop/stages/01-brainstorm/CONTEXT.md

- file: workflows/graph-loop/stages/01-brainstorm/CONTEXT.md
- action: add-file
- confidence: high
- risk: low

Why: stage 1 of graph-loop; searches nothing yet, just agrees what is being built.

```diff
--- /dev/null
+++ b/workflows/graph-loop/stages/01-brainstorm/CONTEXT.md
@@ -0,0 +1,34 @@
+# 01-brainstorm
(... shortened for this example ...)
```

### 6. add-file: workflows/graph-loop/stages/02-retrieve/CONTEXT.md

- file: workflows/graph-loop/stages/02-retrieve/CONTEXT.md
- action: add-file
- confidence: high
- risk: low

Why: searches your `knowledge/` and `output/` folders before anything is generated.

```diff
--- /dev/null
+++ b/workflows/graph-loop/stages/02-retrieve/CONTEXT.md
@@ -0,0 +1,38 @@
+# 02-retrieve
(... shortened for this example ...)
```

### 7. add-file: workflows/graph-loop/stages/03-plan-to-graph/CONTEXT.md

- file: workflows/graph-loop/stages/03-plan-to-graph/CONTEXT.md
- action: add-file
- confidence: high
- risk: low

Why: turns a request into tickets by wiring the ports of video-script and newsletter.

```diff
--- /dev/null
+++ b/workflows/graph-loop/stages/03-plan-to-graph/CONTEXT.md
@@ -0,0 +1,40 @@
+# 03-plan-to-graph
(... shortened for this example ...)
```

### 8. add-file: workflows/graph-loop/stages/04-go/CONTEXT.md

- file: workflows/graph-loop/stages/04-go/CONTEXT.md
- action: add-file
- confidence: high
- risk: low

Why: the one approval for a whole graph. Nothing runs before it.

```diff
--- /dev/null
+++ b/workflows/graph-loop/stages/04-go/CONTEXT.md
@@ -0,0 +1,30 @@
+# 04-go
(... shortened for this example ...)
```

### 9. add-file: workflows/graph-loop/stages/05-run/CONTEXT.md

- file: workflows/graph-loop/stages/05-run/CONTEXT.md
- action: add-file
- confidence: high
- risk: low

Why: how the runner launches tickets in parallel, and what the human sees.

```diff
--- /dev/null
+++ b/workflows/graph-loop/stages/05-run/CONTEXT.md
@@ -0,0 +1,38 @@
+# 05-run
(... shortened for this example ...)
```

### 10. add-file: workflows/graph-loop/stages/06-review/CONTEXT.md

- file: workflows/graph-loop/stages/06-review/CONTEXT.md
- action: add-file
- confidence: high
- risk: low

Why: a separate reviewer scores each output; pass at 0.8.

```diff
--- /dev/null
+++ b/workflows/graph-loop/stages/06-review/CONTEXT.md
@@ -0,0 +1,33 @@
+# 06-review
(... shortened for this example ...)
```

### 11. add-file: workflows/graph-loop/stages/07-write-back/CONTEXT.md

- file: workflows/graph-loop/stages/07-write-back/CONTEXT.md
- action: add-file
- confidence: high
- risk: low

Why: files what was learned into `knowledge/notes/` (a new folder, item 13, because `knowledge/` is read-only reference) so the next request finds it.

```diff
--- /dev/null
+++ b/workflows/graph-loop/stages/07-write-back/CONTEXT.md
@@ -0,0 +1,35 @@
+# 07-write-back
(... shortened for this example ...)
```

### 12. add-file: workflows/graph-loop/reviewer-rubric.md

- file: workflows/graph-loop/reviewer-rubric.md
- action: add-file
- confidence: high
- risk: low

Why: the scoring rubric the reviewer uses (copied unchanged from `templates/reviewer-rubric.md`).

```diff
--- /dev/null
+++ b/workflows/graph-loop/reviewer-rubric.md
@@ -0,0 +1,48 @@
+# Reviewer rubric
(... shortened for this example ...)
```

### 13. add-file: knowledge/notes/README.md

- file: knowledge/notes/README.md
- action: add-file
- confidence: high
- risk: low (new folder; optional, you can decline it, then write-back would need another target)

Why: your `CONTEXT.md` calls `knowledge/` read-only reference, so write-back gets its own
`knowledge/notes/` instead of editing your files.

```diff
--- /dev/null
+++ b/knowledge/notes/README.md
@@ -0,0 +1 @@
+Notes learned by dagr write-back. One topic per file. Your other knowledge files stay read-only.
```

### 14. append-block: CLAUDE.md

- file: CLAUDE.md
- action: append-block
- confidence: high
- risk: low (edits your main agent file, but only appends a marked block)

Why: so any agent that reads your L0 file knows where multi-step requests enter and how to call
the engine.

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -8,3 +8,10 @@
 - Voice: friendly, concrete, no jargon without a one-line explanation. See `knowledge/voice.md`.
 - Never publish. Drafts only; Nora posts by hand.
 - Past work lives in `output/`. Look there before writing something new.
+
+<!-- dagr:begin -->
+## Multi-step requests (dagr)
+
+Multi-step request? Enter through `workflows/graph-loop/CONTEXT.md`.
+Engine: `python -B .dagr/engine/dagr/cli.py <cmd>` (cmds: scan, ports, doctor, plan, go, run, status).
+Nothing runs until the human says `go`.
+<!-- dagr:end -->
```

### 15. append-block: CONTEXT.md

- file: CONTEXT.md
- action: append-block
- confidence: high
- risk: low (one row inserted into your routing table, in place)

Why: so the routing table sends multi-step requests to graph-loop.

```diff
--- a/CONTEXT.md
+++ b/CONTEXT.md
@@ -3,5 +3,6 @@
 | If the job is... | Go to |
 |---|---|
 | a weekly video script | `workflows/video-script/CONTEXT.md` |
 | the weekly newsletter | `workflows/newsletter/CONTEXT.md` |
+| a multi-step request (several workflows, parallel work) | `workflows/graph-loop/CONTEXT.md` |
 
 ## Folders
```

### 16. add-file: .gitignore

- file: .gitignore
- action: add-file
- confidence: high
- risk: low

Why: keeps the engine copy, backups and worker logs out of git. Maps, tickets, `GO.md`, verdicts
and state stay tracked: they are the audit trail.

```diff
--- /dev/null
+++ b/.gitignore
@@ -0,0 +1,9 @@
+# dagr:begin
+# dagr
+.dagr/engine/
+.dagr/backup/
+.dagr/maps/*/assets/**/worker-*.out
+.dagr/maps/*/assets/**/worker-*.err
+.dagr/maps/*/assets/**/*.prompt.txt
+.dagr/maps/*/assets/*.pid
+# dagr:end
