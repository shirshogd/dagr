# 06-verify: prove it works, then report

## Purpose

Check that the integrated tree parses, the ports wire up, and the planner can build a graph from
one of the human's real workflows. Then tell the human what changed and give them one line to try.
Nothing in this stage runs a model (plan uses `--no-model`), spends money or edits their files.

## Inputs

| File | Why |
|---|---|
| `.dagr/APPLY-LOG.md` | what changed |
| `.dagr/ports.md` | expected ports and wiring |
| `.dagr/config.json` | where graph-loop lives |
| `.dagr/scan.md` | workflow ids, to build a sample request |

## Process

1. **doctor.** Run `python -B .dagr/engine/dagr/cli.py doctor --root .`. It checks contracts
   against disk, frontmatter parse errors, and cycles. Expected: no errors. Warnings are fine if you
   can explain them. Any error: fix by restoring from backup (stage 05) or report it. Never "fix" by
   editing outside the proposal.
2. **ports.** Run `python -B .dagr/engine/dagr/cli.py ports --root .`. Compare to `ports.md`:
   every approved port is listed; the wiring and unbound inputs match what you predicted. Record
   differences.
3. **Pick a sample request** built from **their real workflows**. Prefer one that crosses two
   workflows through a wired port: for example, if `video-script` produces `script-draft` and
   `newsletter` consumes it, the request is "Write the newsletter for this week's video." If no
   workflows are wired, use a single-workflow request using their own words from the contract title.
4. **Dry run the plan.** Run
   `python -B .dagr/engine/dagr/cli.py plan "<the sample request>" --map verify-sample --no-model`.
   `--no-model` matches keywords against contract ids and descriptions and never calls a model, so
   verify cannot spend money. Planning only writes files under `.dagr/maps/verify-sample/`; it
   launches no worker. Then run `python -B .dagr/engine/dagr/cli.py run verify-sample --dry-run`,
   which prints the order it would run in without a `GO.md`. Verify stops there: **do not run
   `go` or a real `run`.** `go` is the human's act; the final report offers it as their choice.
5. **Read the map.** Open `.dagr/maps/verify-sample/map.md` and the tickets. Check:
   - tickets exist for the workflows you expected, in the right order
   - `blocked-by` follows the port wiring (the consumer waits for the producer)
   - independent tickets have no `blocked-by` between them (they will run in parallel)
   - each ticket's Inputs name real files in the human's tree
6. **Clean up the sample.** Leave `.dagr/maps/verify-sample/` in place (it is dagr's folder and
   it shows the human what a map looks like), and say so in the report. Do not delete it.
7. Write `.dagr/VERIFY.md`:

   ```markdown
   # Verify

   - date: 2026-01-01T11:00
   - doctor: pass (0 errors, 1 warning: <text>)
   - ports: matches ports.md | differs: <what>
   - sample request: "Write the newsletter for this week's video"
   - plan: ok, 5 tickets, 2 parallel branches (--no-model, keyword matching)
   - run --dry-run: ok
   - not tested: a real run with a worker; reviewer scoring; write-back
   ```
8. **Final report to the human** (in chat, under 200 words):
   - what you found: N workflows, M stages
   - what changed: item numbers and file count; "all originals are in `.dagr/backup/<ts>/`"
   - what is uncertain or untested, plainly (dagr is new; a real run has not been exercised on
     their tree; ports marked medium)
   - open questions you still have
   - **a "try it" line** the human can paste into their agent, using their real workflow names:
     `Use graph-loop: write the newsletter for this week's video, plan only.`
   - offer the next step as their choice: "say `go verify-sample` if you want to run this sample
     (it launches agents and may spend money)"
   - how to undo: `uninstall`

## Outputs

- `.dagr/VERIFY.md`
- `.dagr/maps/verify-sample/` (map and tickets, nothing run)
- the final report in chat

## Verify

- `doctor` ran and its result is quoted in `VERIFY.md`.
- The sample request used the human's own workflow names, not generic ones.
- No `GO.md` exists under `verify-sample`.
- The report lists untested parts and includes the "try it" line and the undo line.

## Common situations

**`doctor` reports a cycle.** Two workflows each consume what the other produces. Report the cycle
with the port names; do not remove ports yourself. Propose a fix (a new proposal item) and send it
through stages 03 and 04.

**The plan has one ticket only.** The sample request matched one workflow. Fine if it was a
single-workflow request. If you expected a chain, check the port names on both sides match exactly.

**The plan has no tickets / "no match".** Keyword matching found nothing. Retry with the
workflow's own id as the request (`plan "newsletter"`), which the engine accepts.

**No python, or Python older than 3.9.** Tell the human; stop. Do not install anything without
asking.

**Windows.** If `python` is not found, try `py -3`. Paths in output may use `\`; that is fine.

**Monorepo.** Verify each root separately, from inside that root.

**The human wants a real run now.** Explain the flow: `plan`, they read `map.md`, they say `go`
(you run `go SLUG`, which writes `GO.md`), then `run SLUG`. A run launches headless agents and may
spend money, so confirm the budget flags (`--max-budget-usd`, `--max-minutes`) with them first.
