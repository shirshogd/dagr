---
id: newsletter
consumes: [script-draft]
produces: [newsletter-draft]
---
# Newsletter

Weekly email that follows the week's video.

## Stages

| # | Stage | Output |
|---|---|---|
| 01 | `stages/01-research/` | `output/newsletter/research.md` |
| 02 | `stages/02-outline/` | `output/newsletter/outline.md` |
| 03 | `stages/03-draft/` | `output/newsletter/draft.md` |

## Inputs

| File | Why |
|---|---|
| `output/video-script/script.md` | the video this issue follows |
| `knowledge/voice.md` | tone |
| `knowledge/audience.md` | who reads it |

## Outputs

`output/newsletter/draft.md`
