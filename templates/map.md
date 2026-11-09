# Map: {{map_title}}

- slug: {{slug}}
- request: "{{the_request_in_the_humans_words}}"
- created: {{date}}
- status: planned
- planner: {{model-or-keyword-fallback}}

## Goal

{{one_paragraph_what_the_whole_graph_delivers}}

## Graph

```
T01 --> T02 --> T04
  \              ^
   --> T03 ------/
```

(T02 and T03 are independent; they run in parallel after T01. T04 waits for both.)

## Tickets

| id | title | workflow | blocked-by | affects | model | needs_human |
|---|---|---|---|---|---|---|
| T01 | {{title}} | {{workflow_id}} | none | {{path}} | default | no |
| T02 | {{title}} | {{workflow_id}} | T01 | {{path}} | default | no |

Each row links to `tickets/T##-<slug>.md`.

## Ports

| port | produced by | consumed by |
|---|---|---|
| {{port}} | T01 | T02, T03 |

## Context pack

Files retrieved for this map (from {{knowledge_dirs}}): see `assets/pack.md`.

## Risks and open questions

- {{item}}

## Approval

Not approved. The human approves the whole graph once with `go {{slug}}`, which writes `GO.md`.
