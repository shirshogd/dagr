# Ports

generated: 2026-01-12T10:20
convention: kebab-case nouns; confidence high | medium | low (low is not proposed)

## Workflows
| workflow | contract | consumes | produces | confidence | evidence |
|---|---|---|---|---|---|
| video-script | workflows/video-script/CONTEXT.md | topic-brief | script-draft | high | stage 01 reads inbox/topic.md and no stage writes it; stage 03 writes output/video-script/script.md, the last stage and the workflow's Outputs line |
| newsletter | workflows/newsletter/CONTEXT.md | script-draft | newsletter-draft | high | stage 01 reads output/video-script/script.md (another workflow's output); stage 03 writes output/newsletter/draft.md |

## Stage ports (optional)
None proposed. Both workflows have an `outline.md` stage output, but they are different artifacts
(`output/video-script/outline.md`, `output/newsletter/outline.md`) and no other workflow reads
either, so they stay internal.

## Wiring
- video-script --script-draft--> newsletter

## Unbound inputs (nothing produces these; expected for human-supplied inputs)
- topic-brief (video-script): the human writes inbox/topic.md

## Dangling outputs (nobody consumes these; expected for final deliverables)
- newsletter-draft (newsletter)

## Ids
| workflow | id |
|---|---|
| video-script | video-script |
| newsletter | newsletter |

## Questions for the human
1. `inbox/topic.md` is a human-written file. I assumed it is a port called `topic-brief`, so a
   planner can say "this workflow needs a topic from you". Is that right, or do you want it treated as
   plain input? (Blocks nothing; medium effect on planning. Default if you do not answer: keep it.)

## Not proposed (low confidence)
- none
