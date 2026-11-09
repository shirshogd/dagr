# 07-write-back

## Purpose

Make what this run learned findable next time. Retrieve (stage 02) and write-back are two ends of
one system: what you file here is what the next request's pack will find.

## Inputs

| File | Why |
|---|---|
| `.dagr/maps/<slug>/assets/T##/review.md` and `integration-review.md` | what worked and what did not |
| `.dagr/maps/<slug>/assets/brainstorm.md` | the class of work |
| `{{notes_dir}}` | where learned notes go (check for an existing note on this class first) |
| `{{knowledge_dirs}}` | to avoid duplicating an existing note |

## Process

1. List what was learned, in plain sentences: decisions the human made, corrections they gave,
   patterns that passed review, mistakes that cost a retry, facts about their audience or style.
2. Search `{{knowledge_dirs}}` for an existing note on each item. Prefer adding to an existing note
   over making a new one.
3. For each learning, write or extend a note in `{{notes_dir}}`: one topic per file, a short title,
   dated lines, a link to the map it came from. Keep each note under one page.
4. If a workflow contract is now wrong (a stage was wrong, a port was missing), do **not** edit it.
   Write it as a suggestion in the note, and tell the human. Contracts change only with their say-so.
5. Show the human the list of notes written and changed.
6. Close the map: set `status: done` in `map.md`.

## Outputs

New or extended notes under `{{notes_dir}}`; `map.md` marked done.

## Verify

- Each learning appears in a note, with its source map.
- No existing note lost content.
- A search for the class of work (stage 02's method) now finds the new note.

## Done when

The next request on the same class retrieves this run's lessons without being told where they are.
