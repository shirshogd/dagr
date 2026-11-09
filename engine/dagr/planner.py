"""planner: free text in, a goal and a set of workflows out. Stdlib only.

    plan_from_prompt(prompt, units, model_fn, ledger) -> {
        "goal", "target_ports": [...], "workflows": [id], "gaps": [{"port", "why"}]}
    keyword_plan(prompt, units, ledger) -> same shape, no model

`model_fn(text) -> str` is injected, so the planner is testable with a stub. This module
never builds graph nodes and never invents a workflow id; compose resolves the ids it returns.
The planner sees only the workflow table (id, purpose, consumes, produces) and the ports the
ledger already holds, so nothing from the rest of the tree reaches the prompt.
"""
from __future__ import annotations

import json
import re

from . import runner_lib

INSTRUCTIONS = (
    "Reply with one JSON object with keys goal, target_ports, workflows, gaps. "
    "Use only workflow ids from the table. A port nothing in the table produces goes in gaps.\n"
    "goal: one sentence. target_ports: the ports the request should end up producing. "
    "workflows: the ids needed to produce them. "
    'gaps: a list of {"port": "...", "why": "..."} objects. '
    "Do not use any tools and do not change any file; reply with the JSON object only."
)

STOP = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "my", "me", "i",
        "please", "make", "prepare", "create", "do", "run", "write", "after", "before", "then",
        "all", "some", "new", "this", "that", "is", "are", "be", "it", "from", "by", "at"}


class PlannerError(Exception):
    """The model reply could not be used. `.raw` keeps the reply text."""

    def __init__(self, message: str, raw: str = ""):
        super().__init__(message)
        self.raw = raw


def _cell(v) -> str:
    return ", ".join(v) if v else "-"


def build_planner_prompt(prompt: str, units: dict, ledger: dict = None) -> str:
    rows = ["| id | purpose | consumes | produces |", "|---|---|---|---|"]
    for uid in sorted(units):
        u = units[uid]
        purpose = (u.description() or "-").replace("|", "/")[:200]
        rows.append(f"| {uid} | {purpose} | {_cell(u.consumes)} | {_cell(u.produces)} |")
    parts = ["You plan work for a workflow engine. The user's request:", "", prompt.strip(), "",
             "Workflows available:", "", *rows, ""]
    if ledger:
        parts += ["Ports this project already has (no workflow needed for these): "
                  + ", ".join(sorted(ledger)), ""]
    parts.append(INSTRUCTIONS)
    return "\n".join(parts) + "\n"


def extract_json_object(text: str) -> dict:
    """The first balanced JSON object in `text` (tolerates prose and code fences around it)."""
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    raise PlannerError("planner reply holds no JSON object", text)


def _strs(v) -> list:
    if isinstance(v, str):
        v = [v]
    out = []
    for x in v if isinstance(v, list) else []:
        if isinstance(x, str) and x.strip() and x.strip() not in out:
            out.append(x.strip())
    return out


def parse_reply(raw: str, units: dict, ledger: dict = None) -> dict:
    obj = extract_json_object(raw)
    ledger = ledger or {}
    gaps, seen = [], set()

    def gap(port, why):
        if port not in seen:
            seen.add(port)
            gaps.append({"port": port, "why": why})

    workflows = []
    for wid in _strs(obj.get("workflows")):
        if wid in units:
            if wid not in workflows:
                workflows.append(wid)
        else:
            gap(wid, f"`{wid}` is not a workflow in the table")

    for g in (obj.get("gaps") if isinstance(obj.get("gaps"), list) else []):
        if isinstance(g, dict) and isinstance(g.get("port"), str) and g["port"].strip():
            gap(g["port"].strip(), str(g.get("why") or "no workflow produces it"))
        elif isinstance(g, str) and g.strip():
            gap(g.strip(), "no workflow produces it")

    producers = {}
    for uid in sorted(units):
        for p in units[uid].produces:
            producers.setdefault(p.rstrip("?"), uid)

    target_ports = _strs(obj.get("target_ports"))
    for port in target_ports:
        if port in ledger:
            continue
        pid = producers.get(port)
        if pid is not None:
            if pid not in workflows and not any(
                    port in [q.rstrip("?") for q in units[w].produces] for w in workflows):
                workflows.append(pid)
            seen.discard(port)
            gaps[:] = [g for g in gaps if g["port"] != port]
        else:
            gap(port, f"nothing in the table produces `{port}`")

    return {"goal": str(obj.get("goal") or "").strip(), "target_ports": target_ports,
            "workflows": workflows, "gaps": gaps}


def plan_from_prompt(prompt: str, units: dict, model_fn, ledger: dict = None) -> dict:
    if not prompt or not prompt.strip():
        raise PlannerError("empty prompt")
    raw = model_fn(build_planner_prompt(prompt, units, ledger))
    if not isinstance(raw, str):
        raise PlannerError("model_fn did not return text", repr(raw))
    return parse_reply(raw, units, ledger)


def worker_model_fn(worker, model, root, workdir, timeout=600):
    """A model_fn that runs the configured worker command once, read-only."""
    def fn(text: str) -> str:
        data, err = runner_lib.run_blocking(
            worker, text, root, workdir, "planner", model=model or None, timeout=timeout,
            allowed_tools=["Read", "Glob", "Grep"],
            disallowed_tools=["Write", "Edit", "Bash"])
        if err:
            raise PlannerError(err)
        res = data.get("result")
        return res if isinstance(res, str) else json.dumps(res)
    return fn


# ---- keyword fallback (no model) -----------------------------------------------

def tokens(text: str) -> set:
    """Lowercase word stems; unicode-aware, so non-English requests still tokenise."""
    out = set()
    for w in re.findall(r"[^\W_]+", (text or "").lower()):
        if w in STOP or len(w) < 2:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def keyword_plan(prompt: str, units: dict, ledger: dict = None) -> dict:
    """Score each workflow by word overlap with the request: id words (3), produced/consumed
    port words (2), words of the first paragraph (1). Keeps the best and anything close to it
    (up to 3). Says nothing is found (`workflows` empty, one gap) when no word matches."""
    req = tokens(prompt)
    scores = {}
    for uid, u in units.items():
        s = 0
        s += 3 * len(req & tokens(uid.replace("-", " ").replace("_", " ")))
        ports = " ".join(p.replace("-", " ").replace("_", " ") for p in u.produces + u.consumes)
        s += 2 * len(req & tokens(ports))
        s += len(req & tokens(u.description()))
        if s > 0:
            scores[uid] = s
    if not scores:
        return {"goal": prompt.strip(), "target_ports": [], "workflows": [],
                "gaps": [{"port": "request", "why": "no workflow id, port or description "
                          "matches the words of the request"}]}
    best = max(scores.values())
    chosen = [u for u, s in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
              if s >= max(1, 0.6 * best)][:3]
    return {"goal": prompt.strip(), "target_ports": [], "workflows": sorted(chosen),
            "gaps": []}
