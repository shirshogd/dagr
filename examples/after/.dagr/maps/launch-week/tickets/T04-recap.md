---
title: Recap newsletter
status: blocked
blocked-by: [T02, T03]
affects: [output/newsletter/recap.md]
model: default
needs_human: false
created: 2026-01-12
---

# T04: Recap newsletter

## Goal

A newsletter issue that recaps both episodes and does not repeat the teaser.

## Inputs

| File | Why |
|---|---|
| `workflows/newsletter/CONTEXT.md` | the contract |
| `output/video-script/ep1-script.md` | episode 1 (from T01, already closed when T03 closed) |
| `output/video-script/ep2-script.md` | output of T02 |
| `output/newsletter/teaser.md` | output of T03: do not repeat it |
| `knowledge/voice.md`, `knowledge/audience.md` | tone and reader |

## Process

1. Run newsletter stages 01 to 03 over both scripts.
2. Save the final issue as `output/newsletter/recap.md`.

## Outputs

- `output/newsletter/recap.md` (port `newsletter-draft`)

## Acceptance

- Covers both episodes in one clear thread, 400 to 600 words, one call to action.
- No paragraph lifted from `teaser.md`.
- Names the next step for the reader (the series continues).
