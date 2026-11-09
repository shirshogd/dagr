# 02-retrieve

## Purpose

Look before you generate. Find what the human's own folders already say about this class of work,
and build a context pack the planner and every ticket can draw from.

## Inputs

| File | Why |
|---|---|
| `.dagr/maps/<slug>/assets/brainstorm.md` | the class, deliverables, constraints |
| `{{knowledge_dirs}}` | the human's knowledge and reference folders (search here) |
| `{{output_dirs}}` | past deliverables of the same class (search here) |
| `{{workflows_root}}/*/{{contract_name}}` | the workflows' own contracts: the "machinery" |
| `.dagr/ports.md` | which workflow produces and consumes which port |

## Process

1. Pick 3 to 6 search terms from the brainstorm: the class, the deliverables, key nouns.
2. Search the knowledge folders with plain text search (`grep -ril` or your file search). Search
   past outputs the same way. Open the best matches only.
3. Read the contracts of the workflows that could do the work.
4. Write `.dagr/maps/<slug>/assets/pack.md` with these sections:
   - **Past work**: file path, one line on why it matters.
   - **Knowledge**: file path, the exact lines to reuse (quote them, short).
   - **Workflow machinery**: each candidate workflow, its ports, what it already does.
   - **Gaps**: what the folders do not cover.
5. Keep the pack small: aim for under two pages. Paths and short quotes, not whole files.
6. Each later ticket's Inputs table is drawn from this pack. If the pack is empty, say so; the
   planner then proceeds with no background and notes the risk.

## Outputs

`.dagr/maps/<slug>/assets/pack.md`

## Verify

- Every path in the pack exists.
- The pack names at least the workflows that will do the work.
- Gaps are listed, not papered over.

## Done when

The planner can start from the pack and a fresh agent could find every cited file.
