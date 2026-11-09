"""config: finding the root, reading `.dagr/config.json`, resolving worker templates.

The root is never inferred from where this file lives (the engine is vendored into
`.dagr/engine/`). It comes from `--root`, else from the current directory walking up to the
first folder that holds a `.dagr/` folder, else the current directory.
"""
from __future__ import annotations

import copy
import json
import os
import shlex
from pathlib import Path

DAGR_DIR = ".dagr"

# A worker template says how to start one headless agent. `argv` is the fixed part.
# `optional_flags` are [flag, value?] groups, dropped when a placeholder is empty (or, with
# `probe`, when the CLI's help text does not list the flag). `stdin: "brief"` feeds the brief
# file to the child's stdin. `output` is "claude-stream" (JSON lines, last `result` object) or
# "text" (stdout is the result). `tools` maps allowed/disallowed tool lists to CLI flags.
DEFAULT_CONFIG = {
    "worker": "claude",
    "reviewer": {"worker": "claude", "model": ""},
    "planner": {"worker": "claude", "model": ""},
    "pass_threshold": 0.8,
    "max_attempts": 3,
    "max_turns": 150,
    "max_minutes": 90.0,
    "stall_minutes": 20.0,
    "max_budget_usd": 10.0,
    "git_commits": True,
    "commit_trailer": "",
    "workers": {
        "claude": {
            "argv": ["claude", "-p", "--output-format", "stream-json", "--verbose",
                     "--permission-mode", "dontAsk"],
            "model": "sonnet",
            "stdin": "brief",
            "output": "claude-stream",
            "probe": ["-p", "--help"],
            "optional_flags": [["--model", "{model}"], ["--include-partial-messages"],
                               ["--max-turns", "{max_turns}"],
                               ["--max-budget-usd", "{max_budget_usd}"]],
            "tools": {"allowed": "--allowedTools", "disallowed": "--disallowedTools"},
        },
        "codex": {
            "argv": ["codex", "exec", "--sandbox", "workspace-write"],
            "model": "",
            "stdin": "brief",
            "output": "text",
            "optional_flags": [["--model", "{model}"]],
            "tail": ["-"],
        },
        "opencode": {
            "argv": ["opencode", "run", "--auto"],
            "model": "",
            "stdin": "",
            "output": "text",
            "optional_flags": [["--model", "{model}"]],
            "tail": ["--file", "{brief_file}", "Follow the attached brief exactly."],
        },
        "custom": {
            "command": "",
            "model": "",
            "stdin": "",
            "output": "text",
        },
    },
}


class ConfigError(Exception):
    pass


def find_root(explicit=None, start=None) -> Path:
    """`--root`, else walk up from `start` (default cwd) to a folder holding `.dagr/`, else cwd."""
    if explicit:
        return Path(explicit).resolve()
    here = Path(start or os.getcwd()).resolve()
    for d in [here] + list(here.parents):
        if (d / DAGR_DIR).is_dir():
            return d
    return here


def dagr_dir(root) -> Path:
    return Path(root) / DAGR_DIR


def maps_dir(root) -> Path:
    return dagr_dir(root) / "maps"


def map_dir(root, slug) -> Path:
    return maps_dir(root) / slug


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(root) -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    p = dagr_dir(root) / "config.json"
    if p.is_file():
        try:
            user = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ConfigError(f"cannot read {p}: {e}")
        if not isinstance(user, dict):
            raise ConfigError(f"{p} must hold a JSON object")
        workers = user.pop("workers", None)
        _merge(cfg, user)
        if isinstance(workers, dict):   # a non-object entry (a note, "") keeps the default
            for k, v in workers.items():
                if isinstance(v, dict):
                    cfg["workers"][k] = _merge(cfg["workers"].get(k, {}), v)                         if isinstance(cfg["workers"].get(k), dict) else v
    return cfg


def write_default_config(root) -> Path:
    p = dagr_dir(root) / "config.json"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    return p


def split_command(val: str) -> list:
    """A path to one binary, or a whole command line (`python /x/fake.py`)."""
    if Path(val).exists():
        return [val]
    return shlex.split(val, posix=True)   # on Windows use forward slashes inside a command line


def worker_cfg(cfg: dict, name=None) -> dict:
    """The template for worker `name` (default: cfg["worker"]), with `_name` filled in and
    the binary override applied: DAGR_<NAME>_BIN, DAGR_WORKER_BIN, or CLAUDE_BIN (claude)."""
    name = name or cfg.get("worker") or "claude"
    t = (cfg.get("workers") or {}).get(name)
    if not isinstance(t, dict):
        raise ConfigError(f"no worker template named `{name}` in .dagr/config.json -> workers")
    t = copy.deepcopy(t)
    t["_name"] = name
    env = (os.environ.get(f"DAGR_{name.upper()}_BIN") or os.environ.get("DAGR_WORKER_BIN")
           or (os.environ.get("CLAUDE_BIN") if name == "claude" else None))
    if env:
        t["_bin"] = split_command(env)
    return t


def role_cfg(cfg: dict, role: str) -> tuple:
    """-> (worker template, model) for role "reviewer" or "planner"."""
    r = cfg.get(role) or {}
    w = worker_cfg(cfg, r.get("worker") or cfg.get("worker"))
    return w, (r.get("model") or w.get("model") or "")
