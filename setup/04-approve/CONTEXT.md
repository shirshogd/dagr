# 04-approve: the human's gate

## Purpose

Show the proposal, get an explicit answer, and record exactly which items are approved. This is
the only gate in the setup. Until it passes, no user file changes.

## Inputs

| File | Why |
|---|---|
| `.dagr/PROPOSAL.md` | what you are asking about |
| `.dagr/ports.md` ("Questions for the human") | blocking questions to ask together with the approval |

## Process

1. Tell the human, in the chat, in this order and no longer than needed:
   - one line: "I found N workflows and M stages; I propose K changes; nothing has been changed yet."
   - the summary from the top of `PROPOSAL.md`
   - the items as a numbered list, one line each: `3. add-frontmatter workflows/newsletter/CONTEXT.md (low risk)`
   - any item that is `medium` or `high` risk, with its one-line reason
   - the blocking open questions
   - the path of `.dagr/PROPOSAL.md` ("the full diffs are there")
   - the accepted replies (below)
2. **Stop and wait.** Do not apply anything. Do not "start with the safe ones".
3. Interpret the reply with the table below. Match the exact forms first; for anything else, say
   what you understood and ask for a yes before acting.
4. Write `.dagr/approval.md` (format below) the moment you have an answer.
5. Go to stage 05 only when `approval.md` says `status: approved` with at least one approved item.

## Accepted replies

Case does not matter. Extra words are fine ("ok, approve"). Item numbers can be separated by
commas, spaces or ranges.

| reply | meaning |
|---|---|
| `approve` | every item is approved |
| `approve except 3,5` or `approve except 3-5` | all items except those; they stay unapplied |
| `approve only 1,2,4` | just those items |
| `edit 4: <what to change>` | change item 4 as described, then show the new item and ask again. Nothing is approved by an edit. |
| `skip questions` | proceed with answers you proposed for the open questions (only if all are low risk) |
| `cancel` or `no` | nothing is approved; stop; leave `.dagr/` in place |
| an answer to a question | record it; regenerate the affected items; show them; ask again |

These do **not** count as approval: silence, "looks good" without "approve", a thumbs-up, "maybe",
"go" (that word is reserved for running graphs, later), or a reply that names item numbers without
saying approve. Ask once: "Reply `approve` to apply, or `approve except N`."

Approval is for **this version** of the proposal. If you change any item after approval was
given (for instance an edit), the approval is void. Ask again.

## Dependencies between items

If an excluded item is needed by an approved one, tell the human before applying and ask. The
usual case: item 1 (`config.json`) is needed by everything, and the graph-loop files need config. If
`approve except 1` is given, warn that nothing else will work without it and ask to confirm. A
workflow's frontmatter can be approved without graph-loop, and the reverse works too, but ports
without graph-loop only give the human the `ports`/`doctor` commands.

## approval.md format

```markdown
# Approval

- proposal: PROPOSAL.md (items: 9, generated 2026-01-01T10:30)
- answered: 2026-01-01T10:42
- reply: "approve except 7"
- status: approved            # approved | cancelled | pending
- approved: 1,2,3,4,5,6,8,9
- excluded: 7
- answers:
  - Q1: "yes, newsletter consumes script-draft"
```

## Outputs

`.dagr/approval.md`

## Verify

- `approved` plus `excluded` together list every item number exactly once.
- `reply` quotes the human's words verbatim.
- If you edited any item after the reply, the status is `pending` again.

## Common situations

**The human answers some questions and approves in one message.** Apply their answers to the
affected items first, show the changed items, and ask for approval of the new version.

**The human wants a change you cannot express** as add-frontmatter, add-file or append-block
(for example, renaming a folder). Say that dagr never renames or moves files; offer to leave it
as a note in `.dagr/ports.md`.

**The human is unsure what a frontmatter block is.** Show item 3 as the model: three lines at the
top of a contract, nothing else changes.

**Partial approval leaves a stage with half its setup.** Allowed. Say what will not work.

**The human is on a different machine or channel** (for example, the agent is headless). Write the
proposal path and the reply forms into your final message and stop. Resume at stage 05 when a
reply is relayed to you.

**Multiple roots.** One approval per root.
