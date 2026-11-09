# Template: L0 pointer block

Appended to the end of each L0 markdown file (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`). Cursor gets
`cursor-rule.mdc` instead of an edit to `.cursorrules`. The markers make a
re-run replace the block instead of adding a second one. Keep it this short.

```markdown
<!-- dagr:begin -->
## Multi-step requests (dagr)

Multi-step request? Enter through `{{workflows_root}}/graph-loop/{{contract_name}}`.
Engine: `python -B .dagr/engine/dagr/cli.py <cmd>` (cmds: scan, ports, doctor, plan, go, run, status).
Nothing runs until the human says `go`.
<!-- dagr:end -->
```

## Placeholders

| placeholder | filled from |
|---|---|
| `{{workflows_root}}` | `config.json` `workflows_root`, root-relative with `/` |
| `{{contract_name}}` | `CONTEXT.md`, or `README.md` if that is how the human's contracts are named |

For a CRLF file, write the block with CRLF line endings. Add one blank line before the opening
marker. If the language of the L0 file is not English, keep the block in English (it is a command
pointer) and add nothing else.
