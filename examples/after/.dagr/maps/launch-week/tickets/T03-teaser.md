---
title: Teaser newsletter
status: blocked
blocked-by: [T01]
affects: [output/newsletter/teaser.md]
model: default
needs_human: false
created: 2026-01-12
---

# T03: Teaser newsletter

## Goal

A 400 to 600 word newsletter issue that follows episode 1 and points to it.

## Inputs

| File | Why |
|---|---|
| `workflows/newsletter/CONTEXT.md` | the contract; follow its three stages |
| `output/video-script/ep1-script.md` | output of T01 (port `script-draft`) |
| `knowledge/voice.md`, `knowledge/audience.md` | tone and reader |
| `output/newsletter/draft.md` | an earlier issue as a style reference |

## Process

1. Run newsletter stages 01 to 03, reading `ep1-script.md` where the contract says
   `output/video-script/script.md`.
2. Save the final issue as `output/newsletter/teaser.md`.

## Outputs

- `output/newsletter/teaser.md` (port `newsletter-draft`)

## Acceptance

- Subject line first; 400 to 600 words; one call to action.
- Adds at least two things episode 1 did not have time to say.
- Every claim about the video matches `ep1-script.md`.
