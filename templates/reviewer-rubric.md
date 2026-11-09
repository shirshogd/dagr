# Reviewer rubric

Used by the separate reviewer that scores each finished ticket. The reviewer is a different agent
(and ideally a different model) from the worker. It sees the ticket, the output and the files the
ticket named. It does not see the worker's reasoning.

## Score

Give one number from 0.0 to 1.0. **Pass is 0.8 or higher.** Below 0.8 the ticket goes back to the
worker with your notes, up to 3 attempts in total.

| criterion | weight | question |
|---|---|---|
| Meets acceptance | 0.40 | Does the output satisfy every line under the ticket's Acceptance? |
| Follows the contract | 0.20 | Did it use the stage's Inputs and write only the Outputs listed? |
| Faithful to inputs | 0.20 | Are claims supported by the named inputs? Nothing invented? |
| Fit for next step | 0.10 | Can the downstream ticket use this port as it is? |
| Craft | 0.10 | Clear, correct, in the human's voice and format, no filler? |

Any one of these is an automatic fail, whatever the sum: output missing or empty; a file written
outside `affects`; a claim the inputs contradict; a secret or private data copied into the output.

## Reply format

```markdown
score: 0.74
verdict: retry            # pass | retry | fail
met:
  - (acceptance lines met)
missed:
  - (acceptance lines missed, each with the exact place in the output)
notes-for-worker:
  - (specific, actionable fixes, in priority order, at most 5)
```

## Rules for the reviewer

1. Judge the output against the ticket, not against your own taste.
2. Quote the place in the output for every miss.
3. Do not rewrite the output. Say what to change.
4. If the ticket itself is flawed (impossible, contradictory), say `verdict: fail` and explain;
   the planner will re-plan the branch.
5. Be consistent: the same output scores the same.

## Integration review (once, at the end)

After all tickets close, check the whole graph: do the outputs fit together, do any contradict
each other, did anything in the request go unaddressed? Score it the same way. A low integration
score opens follow-up tickets; it does not rewrite finished work.
