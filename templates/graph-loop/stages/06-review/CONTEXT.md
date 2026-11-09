# 06-review

## Purpose

A separate reviewer scores each finished ticket, and then the whole graph. The agent that did the
work never grades it.

## Inputs

| File | Why |
|---|---|
| `{{workflows_root}}/graph-loop/reviewer-rubric.md` | the scoring rubric (copied from the dagr templates) |
| `.dagr/maps/<slug>/tickets/T##-*.md` | each ticket's Acceptance |
| the ticket's output files | what is being judged |

## Process

1. The runner calls the reviewer for each ticket after the worker finishes (unless run with
   `--no-review`; then say that nothing was reviewed). Use `--reviewer-model` to pick a different
   model from the worker.
2. Score 0.0 to 1.0 using the rubric. **0.8 or higher passes.** Below that the ticket retries with
   the reviewer's notes, up to 3 attempts, then it fails.
3. A failed ticket stops its branch. Choose: re-plan that branch (back to 03-plan-to-graph for the
   affected tickets only), or hand it to the human with the reviewer's notes.
4. When all tickets close, run an integration review over the whole map: do the outputs fit
   together, do any contradict, was anything in the request missed?
5. Record verdicts in `.dagr/maps/<slug>/assets/T##/review.md` and the integration verdict in
   `.dagr/maps/<slug>/assets/integration-review.md`.

## Outputs

`.dagr/maps/<slug>/assets/T##/review.md` per ticket; `assets/integration-review.md`.

## Verify

- Every closed ticket has a verdict from a reviewer that was not its worker.
- Every miss quotes the place in the output.

## Done when

Every ticket is passed or escalated, and the integration review is written.
