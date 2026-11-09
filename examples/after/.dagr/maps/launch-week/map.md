# Map: launch week

- slug: launch-week
- request: "Prepare launch week: scripts for episodes 1 and 2, a teaser newsletter after episode 1, and a recap newsletter after both."
- created: 2026-01-12
- status: planned
- planner: keyword fallback (no model available)

## Goal

Two video scripts, one teaser newsletter and one recap newsletter, ready for Nora to review.
Drafts only; nothing is published.

## Graph

```
T01 (script ep1) ----> T03 (teaser) ----> T04 (recap)
                                           ^
T02 (script ep2) --------------------------/
```

T01 and T02 have no arrow between them, so they run in parallel. T03 starts as soon as T01 is
closed, while T02 may still be running. T04 waits for both T02 and T03.

## Tickets

| id | title | workflow | blocked-by | affects | model | needs_human |
|---|---|---|---|---|---|---|
| T01 | Script, episode 1 | video-script | none | output/video-script/ep1-script.md | default | no |
| T02 | Script, episode 2 | video-script | none | output/video-script/ep2-script.md | default | no |
| T03 | Teaser newsletter | newsletter | T01 | output/newsletter/teaser.md | default | no |
| T04 | Recap newsletter | newsletter | T02, T03 | output/newsletter/recap.md | default | no |

Tickets are in `tickets/T##-*.md`.

## Ports

| port | produced by | consumed by |
|---|---|---|
| topic-brief | the human (inbox/topic.md) | T01, T02 |
| script-draft | T01, T02 | T03 (ep1), T04 (ep1 and ep2) |
| newsletter-draft | T03, T04 | the human |

## Context pack

`assets/pack.md` (retrieved from `knowledge/` and `output/`): voice, audience, the "reading a pull
request" script and issue as style references. Not shown in this example.

## Risks and open questions

- Both scripts need a topic. The ticket for episode 2 says "use the topic Nora gives; ask if absent"
  (T02 is marked `needs_human: no` only because inbox/topic.md is present; if it is stale, set it
  to `yes`).
- T03 and T04 both write under `output/newsletter/` but to different files, so they do not clash.

## Approval

Not approved. The human approves the whole graph once with `go launch-week`, which writes `GO.md`.
