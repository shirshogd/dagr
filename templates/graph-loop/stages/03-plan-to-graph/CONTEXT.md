# 03-plan-to-graph

## Purpose

Turn the request into a DAG: tickets whose ports wire together, with independent tickets free to
run in parallel.

## Inputs

| File | Why |
|---|---|
| `.dagr/maps/<slug>/assets/brainstorm.md` | class, deliverables |
| `.dagr/maps/<slug>/assets/pack.md` | background and candidate workflows |
| `.dagr/ports.md` | the port wiring across `{{workflows_root}}` |
| `{{workflows_root}}/<chosen workflow>/{{contract_name}}` | each ticket follows one of these |

## Process

1. Run `{{engine_cmd}} plan "<the request>" --map <slug>`. The engine proposes a graph and writes
   `map.md` and `tickets/`. (With no model available it falls back to keyword matching and says so;
   then you refine by hand.)
   For the same workflow more than once (episodes 1 and 2), repeat it with the flag:
   `plan video-script --also video-script`; otherwise edit the map by hand.
2. Read the result and fix it:
   - one ticket per unit of work a fresh agent can finish alone; split anything that would take
     more than one working session
   - each ticket follows exactly one existing workflow (Rule B), named in its Inputs
   - `blocked-by` follows the ports: a consumer waits for its producer; nothing else waits
   - tickets that do not depend on each other have no `blocked-by` between them, so they run in
     parallel
   - `affects` lists every file the ticket writes; overlapping `affects` get serialised by the runner
   - each Inputs table is drawn from the pack, never a blank start
3. Mark `needs_human: true` where only a person can decide (a choice, a fact, a credential).
4. Check for cycles and missing ports: `{{engine_cmd}} doctor`.
5. Show the human the graph as one read: the diagram, the table, the questions.

## Outputs

`.dagr/maps/<slug>/map.md` and `.dagr/maps/<slug>/tickets/T##-*.md`

## Verify

- No ticket without an Inputs table; no ticket that follows no workflow, unless flagged "new".
- `doctor` reports no cycle.
- Every `blocked-by` is justified by a port or a file.

## Done when

The graph is complete and the human can approve it from one read.
