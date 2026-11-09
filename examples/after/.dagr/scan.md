# Scan

- root: .
- scanned: 2026-01-12T10:05
- git: no
- line-endings: lf
- language: en
- shape: icm

## L0 files
| file | notes |
|---|---|
| CLAUDE.md | main agent file, 11 lines, rules and voice |

## L1 routing
| file | notes |
|---|---|
| CONTEXT.md | routing table with two rows (video, newsletter) |

## Workflows area
- path pattern: workflows/*/
- contract name: CONTEXT.md

## Workflows
| id | path | contract | stages | numbering | frontmatter |
|---|---|---|---|---|---|
| video-script | workflows/video-script | CONTEXT.md | 3 | 01-x | none |
| newsletter | workflows/newsletter | CONTEXT.md | 3 | 01-x | none |

## Knowledge folders
- knowledge/ (3 files: voice.md, audience.md, past-topics.md)

## Output folders
- output/video-script/ (1 file)
- output/newsletter/ (1 file)

## Other folders
- inbox/ (1 file: topic.md, human-written, read by video-script stage 01)

## Oddities
- Workflow ids are not declared anywhere; derived from folder names.
- Stage order is clear from the numbered folders and the workflow tables; both agree.
- Nothing ignored (no .git, no build folders).
