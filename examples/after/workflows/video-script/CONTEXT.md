---
id: video-script
consumes: [topic-brief]
produces: [script-draft]
---
# Video script

Turns a one-line topic into a spoken script for the weekly video.

## Stages

| # | Stage | Output |
|---|---|---|
| 01 | `stages/01-hook/` | `output/video-script/hook.md` |
| 02 | `stages/02-outline/` | `output/video-script/outline.md` |
| 03 | `stages/03-script/` | `output/video-script/script.md` |

## Inputs

| File | Why |
|---|---|
| `inbox/topic.md` | the topic and angle |
| `knowledge/voice.md` | tone |
| `knowledge/audience.md` | who is watching |

## Outputs

`output/video-script/script.md`
