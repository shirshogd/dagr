# FAQ

## Do I need to know ICM first?

Not much. If your folders have a root agent file, a routing `CONTEXT.md`, and a `CONTEXT.md` per workflow, you are using it already. If your layout differs, the scan reports what it could and could not map. See [concepts](concepts.md).

## What does dagr change in my files?

Four things: a `.dagr/` folder, port frontmatter on your workflow contracts, one `graph-loop` workflow, and one block in your root agent file. All of it is shown as a diff in `.dagr/PROPOSAL.md` before anything is written.

## Does it delete or move anything?

No. Existing files are never deleted, renamed, or moved. Edits are backed up first.

## How do I remove it?

`python -B .dagr/engine/dagr/cli.py uninstall` restores your originals from `.dagr/backup/` and removes `.dagr/`. Add `--yes` to skip the confirmation. The `graph-loop` workflow and L0 block were added by the setup, so check that the restore removed them.

## When does it spend money?

Only after `dagr go`. `plan` may call a model if one is available. `run` can use `--max-minutes` as a hard cap, and `--max-budget-usd` as a spend cap that only works for agents that report cost (`claude`). `--dry-run` launches nothing.

## Which agents does it work with?

Claude Code, Codex, Cursor, and OpenCode can run the setup, since it is just a folder of instructions. For the run phase, built-in worker templates exist for `claude`, `codex`, and `opencode`, plus a `custom` template. See [agents](agents.md).

## Is the worker command tested?

No. No real `claude`, `codex`, or `opencode` binary has been run through the engine; all 98 tests use a fake agent. Run with `--dry-run`, read the command line in `.dagr/config.json`, and try one small ticket first.

## What if my tree is messy?

Run the setup anyway. Gaps are listed in `.dagr/ports.md` with a confidence level, and nothing is applied until you approve. You can answer "approve except 3" to skip items.

## A ticket got stuck. Why?

Three common reasons: it is blocked by a ticket that failed, it has `needs_human` and is waiting for your answer in `questions/Q-<T##>.md`, or a stray-path hold stopped it. Run `dagr status SLUG` and read `STATUS.md`.

## What if the reviewer keeps failing a ticket?

It retries up to 3 times with the reviewer's notes. Then the node fails, and that branch is re-planned or escalated to you. You can also tighten the ticket's brief or edit the rubric in your tree.

## Does it need pip, Node, or the internet?

No pip and no Node. It is Python 3.9+, standard library only. The workers you choose need whatever they need (their own CLI and login).

## Do I have to use git?

No. If your root is a git repo, commits cover only the paths a run touched. If it is not, dagr only writes files.

## Is dagr part of ICM?

No. ICM comes from the paper by J. Van Clief and D. McDermott, [arXiv:2603.16021](https://arxiv.org/abs/2603.16021). dagr is a separate project that builds on it.

## Where do I report a bug?

Open an issue and include your `.dagr/scan.md` (remove anything private) and the command you ran.
