---
title: Script, episode 2
status: open
blocked-by: []
affects: [output/video-script/ep2-script.md]
model: default
needs_human: false
created: 2026-01-12
---

# T02: Script, episode 2

## Goal

A 6 to 8 minute script for episode 2 (what a design token is), in Nora's voice.

## Inputs

| File | Why |
|---|---|
| `workflows/video-script/CONTEXT.md` | the contract |
| `inbox/topic.md` | the topic for the series; episode 2 angle is "design tokens" per `knowledge/past-topics.md` |
| `knowledge/voice.md`, `knowledge/audience.md` | tone and reader |

## Process

1. Run the video-script stages 01 to 03.
2. Save the final script as `output/video-script/ep2-script.md`.

## Outputs

- `output/video-script/ep2-script.md`: the finished script (port `script-draft`)

## Acceptance

- Explains "design token" in one plain sentence before using the term again.
- Same length and structure rules as T01.
- Does not repeat the episode 1 walk-through.

## Notes for the reviewer

T01 and T02 run in parallel and write different files. Do not penalise T02 for not referencing
T01's output.
