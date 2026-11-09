# 04-go

## Purpose

One approval for the whole graph. Nothing runs, and nothing costs money, before this.

## Inputs

| File | Why |
|---|---|
| `.dagr/maps/<slug>/map.md` | what the human is approving |
| `.dagr/maps/<slug>/tickets/*.md` | the tickets in scope |
| `.dagr/maps/<slug>/questions/Q-*.md` | open human questions, if any |

## Process

1. Show the human: the graph, the number of tickets, which ones need a human answer, the files that
   will be written, and a budget suggestion (`--max-budget-usd`, `--max-minutes`).
2. Ask for the word `go`. Accept a scope: `go` (all), or `go T01,T03-T05`. No other word counts.
3. On `go`, run `{{engine_cmd}} go <slug> [--scope ...] --who <name>`. This writes `GO.md`.
   Never write `GO.md` by hand and never run `go` unprompted.
4. If the human changes the map after `go`, delete nothing; run `go` again so `GO.md` matches.

## Outputs

`.dagr/maps/<slug>/GO.md`

## Verify

- `GO.md` exists, names who approved, and lists the scope.
- It was created after the human said `go` in this conversation.

## Done when

`GO.md` exists and its scope matches what the human said.
