# Contributing

## Layout

- `engine/`: the Python engine. Standard library only, Python 3.9+. No third-party packages.
- `setup/`: the kit your agent follows. It is itself ICM-shaped: folders with a `CONTEXT.md` each.
- `examples/`: a tree before and after integration.
- `docs/`, `templates/`: docs and file templates.

## Run the tests

    python -B -m unittest discover -s engine/tests
    python -B engine/dagr/cli.py doctor --root examples/after
    python -B engine/dagr/cli.py ports --root examples/after

CI runs these on Linux, Windows and macOS, with Python 3.9 and 3.12.

## Rules

- Every change to `setup/` must keep `examples/after` in sync.
- Engine code stays standard library only.
- No hype words. Say what the thing does, plainly.
- Keep changes small. One idea per pull request.

## Bugs

Use the issue templates. If dagr mis-read your tree, use the integration report.
