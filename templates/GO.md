# GO: {{slug}}

<!-- Written by `python -B .dagr/engine/dagr/cli.py go {{slug}}`. Do not write it by hand. -->
<!-- This file is the approval act. No ticket runs until it exists. Deleting it stops new launches. -->

- approved-by: {{name}}
- approved-at: {{timestamp}}
- scope: {{all | T01,T02-T05}}
- map: .dagr/maps/{{slug}}/map.md
- tickets approved: {{count}}
- budget: {{max-budget-usd and max-minutes, if given at run time}}

## What the human saw before approving

- the map (`map.md`) and every ticket in scope
- which tickets need a human answer (`needs_human: true`)
- which files the graph will write (`affects`)

## Terms

- Only tickets in `scope` may run.
- A ticket that writes outside its `affects` is held, not committed.
- The reviewer scores each output. Pass is 0.8 or higher. Below that the ticket retries with the
  reviewer's notes, up to 3 attempts, then it fails and the branch waits for the human.
