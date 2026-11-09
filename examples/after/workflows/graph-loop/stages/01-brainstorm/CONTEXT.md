# 01-brainstorm

## Purpose

Understand the request before planning. Find the class of work it belongs to, why the human wants
it, and what "done" looks like.

## Inputs

| File | Why |
|---|---|
| the human's request (chat) | the starting point |
| `CLAUDE.md` | house rules and voice |
| `workflows/*/CONTEXT.md` (headings and frontmatter only) | what workflows exist: newsletter, video-script |

## Process

1. Restate the request in two sentences. Ask the human to correct you.
2. Ask at most five questions, one at a time, only about what you cannot infer: audience, deadline,
   size, quality bar, anything that must not happen.
3. **Find the class.** If the request names one example ("the March newsletter"), state the class
   ("our newsletters") and keep the example as the first test case.
4. List the deliverables the human expects, each as a noun (these become ports).
5. Write the class statement, the first test case, the deliverables and any constraints into
   `.dagr/maps/<slug>/assets/brainstorm.md`. Choose the slug now: lowercase kebab-case, short.
6. If the request is really one workflow's job, say so and hand over to that workflow. Stop here.

## Outputs

`.dagr/maps/<slug>/assets/brainstorm.md`

## Verify

- It states the class, one test case, the deliverables and the constraints.
- The human saw it and did not object.

## Done when

You and the human agree on what is being built and how they will know it is done.
