---
title: {{ticket_title}}
status: open
blocked-by: []
affects: [{{paths_this_ticket_writes}}]
model: {{model_or_default}}
needs_human: false
created: {{date}}
---

# {{ticket_id}}: {{ticket_title}}

<!-- One ticket = one unit of work a fresh agent can do from this file alone. -->
<!-- Status values: open, in-progress, review, closed, failed, blocked. -->
<!-- `blocked-by` lists ticket ids (for example [T01, T02]). `affects` lists the files or folders -->
<!-- this ticket writes; tickets whose `affects` overlap run one after the other. -->
<!-- Set needs_human: true when a person must answer something first; the runner then writes -->
<!-- .dagr/maps/<slug>/questions/Q-<ticket>.md and waits until that file says `status: answered`. -->

## Goal

{{one_or_two_sentences_what_done_looks_like}}

## Inputs

| File | Why |
|---|---|
| `{{contract_path_of_the_workflow_or_stage}}` | the contract to follow |
| `{{upstream_ticket_output_path}}` | output of a blocking ticket |
| `{{knowledge_file_from_the_context_pack}}` | background from the retrieve step |

Load exactly these. Nothing else.

## Process

1. {{concrete_step}}
2. {{concrete_step}}

## Outputs

- `{{output_path}}`: {{what_it_contains}}

## Acceptance

- {{a_check_a_separate_reviewer_can_judge}}
- {{another}}

## Notes for the reviewer

{{anything_the_reviewer_should_weigh_extra}}
