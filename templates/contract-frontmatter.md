# Template: contract frontmatter

The block dagr adds to the top of a workflow contract (a `CONTEXT.md`, or a `README.md` used as
one). It is the minimum dagr needs: an id and the ports.

```yaml
---
id: {{workflow_id}}
consumes: [{{consumes}}]
produces: [{{produces}}]
---
```

## Fields

| key | meaning | rules |
|---|---|---|
| `id` | short unique name of the workflow | kebab-case, unique across the root; the planner and `plan "<id>"` use it |
| `consumes` | ports the workflow needs before it can start | list of kebab-case nouns; may be empty `[]` |
| `produces` | ports the workflow leaves behind when done | list of kebab-case nouns; may be empty `[]` |

Optional keys dagr reads if present (add only when the human's tree already says so):

| key | meaning |
|---|---|
| `description` | one line, used by the keyword fallback planner |
| `stages` | ordered list of stage ids, for unnumbered stages |

Stage-level contracts may carry the same `consumes` and `produces`. Optional; skip unless every
stage in the workflow names distinct artifacts.

## Merge rules (when the file already has frontmatter)

1. Never remove or reorder their keys. Never touch their comments.
2. Add `id`, `consumes`, `produces` only where absent.
3. If `consumes` or `produces` exists, append missing ports to the existing list; do not replace.
4. Keep their quoting style (`"x"` vs `x`) and list style (flow `[a, b]` vs block).
5. If their frontmatter uses TOML (`+++`) or JSON, do not convert. Ask.
6. Keep line endings and BOM.

Example. Before:

```yaml
---
title: Newsletter
tags: [email]
---
```

After:

```yaml
---
title: Newsletter
tags: [email]
id: newsletter
consumes: [script-draft]
produces: [newsletter-draft]
---
```

## Port naming

Lowercase ASCII, digits and hyphens: `^[a-z0-9]+(-[a-z0-9]+)*$`. A noun for the artifact, not an
action. `outline`, `draft-post`, `thumbnail-set`. Same artifact, same name, everywhere.
