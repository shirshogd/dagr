# 05-run

## Purpose

Run every ready ticket as a headless agent worker, in parallel where the graph allows, within the
limits the human set.

## Inputs

| File | Why |
|---|---|
| `.dagr/maps/<slug>/GO.md` | the approval and scope; no `GO.md`, no run |
| `.dagr/maps/<slug>/tickets/*.md` | what each worker does |
| `.dagr/config.json` | worker command templates (`workers`) |

## Process

1. Preview: `python -B .dagr/engine/dagr/cli.py run <slug> --dry-run`. Check the order and the parallel groups.
2. Run: `python -B .dagr/engine/dagr/cli.py run <slug> --max-budget-usd <N> --max-minutes <M>` (add `--worker
   claude|codex|opencode|custom` to pick the agent that does the work).
3. The runner starts each ticket whose `blocked-by` are all closed, up to its parallel limit. A
   worker that writes outside its ticket's `affects` is held, not committed.
4. A ticket with `needs_human: true` writes `.dagr/maps/<slug>/questions/Q-<ticket>.md` and waits.
   Ask the human; they answer in that file and set `status: answered`; the hold releases.
5. Watch with `python -B .dagr/engine/dagr/cli.py status <slug>` (writes `STATUS.md`). Report it in plain words.
6. The runner stops on budget, wall-clock limit, a stalled worker, or repeated rate limiting. Say
   which, and what finished.

## Outputs

Each ticket's own outputs (in `output/` or wherever its workflow writes), plus
`.dagr/maps/<slug>/{state.json,STATUS.md,run-summary.json,assets/T##/}`.

## Verify

- Every ticket that ran is in `state.json` with a status.
- The `RUN-SUMMARY` line and `run-summary.json` agree.
- Nothing was written outside the tickets' `affects`.

## Done when

Every ticket is closed, failed or held, and the human has been told which.
