---
title: Script, episode 1
status: open
blocked-by: []
affects: [output/video-script/ep1-script.md]
model: default
needs_human: false
created: 2026-01-12
---

# T01: Script, episode 1

## Goal

A 6 to 8 minute spoken script for episode 1 (reading a Git diff), in Nora's voice, with
`[screen]` markers at the walk-through.

## Inputs

| File | Why |
|---|---|
| `workflows/video-script/CONTEXT.md` | the contract; follow its three stages in order |
| `inbox/topic.md` | the topic and angle |
| `knowledge/voice.md`, `knowledge/audience.md` | tone and reader |
| `output/video-script/script.md` | an earlier script as a style reference |

## Process

1. Run the video-script stages 01 to 03, writing intermediate files under
   `output/video-script/` as the stages say.
2. Save the final script as `output/video-script/ep1-script.md`.

## Outputs

- `output/video-script/ep1-script.md`: the finished script (port `script-draft`)

## Acceptance

- Opens with the viewer's problem within the first three sentences.
- Three beats, one `[screen]` walk-through, ends with one next step.
- Reads to 6 to 8 minutes (about 900 to 1,200 words).
