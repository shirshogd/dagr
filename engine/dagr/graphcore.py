"""graphcore: the single place the ready set of a graph-run map is computed.

Parses a map's ticket files, answers ready(), propagates `held`, decides when the run has
terminated, and defines the state.json schema. Stdlib only. The runner and compose import
this; nothing else re-implements a ready-set.
"""
from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import frontmatter as fmt

__all__ = [
    "GraphError", "Ticket", "Graph", "parse_ticket", "load_graph", "validate",
    "blocker_closed", "affects_overlap", "effective_status", "held_set", "ready",
    "terminated", "new_state", "load_state", "save_state", "ensure_ticket_record",
    "reconcile_on_start", "question_path", "question_status",
]

_KNOWN = {"title", "status", "assignee", "blocked_by", "affects", "model", "needs_human",
          "created"}
_RECORD_DEFAULTS = {"status": "open", "worker": None, "attempts": 0, "started": None,
                    "finished": None, "cost_usd": 0.0, "reviewer_score": None,
                    "receipt": None}


# On disk a ticket's status is one of: open, in-progress, review, closed, failed, blocked.
# Internally the runner uses running (= in-progress or review) and held (= blocked).
FM_TO_STATUS = {"in-progress": "running", "in_progress": "running", "review": "running",
                "blocked": "held"}
STATUS_TO_FM = {"running": "in-progress", "held": "blocked"}


class GraphError(Exception):
    pass


@dataclass
class Ticket:
    id: str
    path: str = ""
    title: str = ""
    status: str = "open"
    assignee: str = ""
    blocked_by: list = field(default_factory=list)
    affects: list = field(default_factory=list)
    model: str = "default"
    needs_human: str = "none"
    created: str = ""
    extra: dict = field(default_factory=dict)
    sections: dict = field(default_factory=dict)
    has_model: bool = False   # explicit `model:` key
    in_scope: bool = True


class Graph(dict):
    """dict[id, Ticket] plus the root, the map folder, and a lazy cross-map cache."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.root = None
        self.map_dir = None
        self.xcache = {}


def parse_ticket(path) -> Ticket:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    fm_lines, body, _state = fmt.split_frontmatter(text)
    fm, _errs = fmt.parse_lines(fm_lines)
    t = Ticket(id=p.stem.split("-", 1)[0], path=str(p))

    def scal(k, d=""):
        v = fm.get(k)
        return v if isinstance(v, str) and v != "" else d

    t.title = scal("title")
    t.status = FM_TO_STATUS.get(scal("status", "open").lower(), scal("status", "open").lower())
    t.assignee = scal("assignee")
    t.blocked_by = fmt.as_list(fm.get("blocked_by"))
    t.affects = fmt.as_list(fm.get("affects"))
    t.model = scal("model", "default")
    t.has_model = bool(scal("model"))
    nh = scal("needs_human", "none")
    t.needs_human = ("none" if nh.lower() in ("false", "no", "none", "0", "n/a") else
                     "a human answer is needed (no question text given)"
                     if nh.lower() in ("true", "yes", "1") else nh)
    t.created = scal("created")
    t.extra = {k: v for k, v in fm.items() if k not in _KNOWN}
    t.sections = fmt.sections(body)
    return t


def load_graph(map_dir, scope=None, root=None) -> Graph:
    g = Graph()
    g.map_dir = Path(map_dir)
    if root:
        g.root = Path(root)
    else:   # <root>/.dagr/maps/<slug>
        g.root = Path(map_dir).resolve().parents[2]
    for f in sorted((Path(map_dir) / "tickets").glob("T*.md")):
        t = parse_ticket(f)
        if t.id in g:
            raise GraphError(f"duplicate ticket id {t.id}: {g[t.id].path} and {t.path}")
        g[t.id] = t
    for t in g.values():
        t.in_scope = (t.id in scope) if scope is not None else t.has_model
    return g


# ---- questions (the human-hold files) --------------------------------------

def question_path(map_dir, tid) -> Path:
    return Path(map_dir) / "questions" / f"Q-{tid}.md"


def question_status(map_dir, tid) -> str:
    """`status:` of questions/Q-<tid>.md: "open" | "answered" | "dropped" | ... ; "" if the
    file does not exist."""
    p = question_path(map_dir, tid)
    if not p.is_file():
        return ""
    fm, _e, _s = fmt.parse_text(p.read_text(encoding="utf-8", errors="replace"))
    return (fm.get("status") or "open").strip().lower()


# ---- cross-map blockers ------------------------------------------------------

def _xticket(b: str, graph):
    """Resolve `slug/T##` lazily from .dagr/maps/<slug>/tickets/; None if absent."""
    slug, _, tid = b.partition("/")
    root = getattr(graph, "root", None)
    cache = getattr(graph, "xcache", None)
    if cache is None or root is None:
        return None
    if slug not in cache:
        d = Path(root) / ".dagr" / "maps" / slug
        try:
            cache[slug] = load_graph(d, root=root) if (d / "tickets").is_dir() else None
        except GraphError:
            cache[slug] = None
    sub = cache[slug]
    return sub.get(tid) if sub else None


def _find(b: str, graph):
    return _xticket(b, graph) if "/" in b else graph.get(b)


# ---- validation ------------------------------------------------------------

def validate(graph) -> list:
    msgs = []
    for tid in sorted(graph):
        t = graph[tid]
        for b in t.blocked_by:
            if _find(b, graph) is None:
                msgs.append(f"{t.id}: unknown blocker {b}")
        if "Inputs" not in t.sections:
            msgs.append(f"{t.id}: no ## Inputs section")
    color = {}

    def dfs(tid, stack):
        color[tid] = 1
        for b in graph[tid].blocked_by:
            if b not in graph:
                continue
            if color.get(b) == 1:
                cyc = stack[stack.index(b):] + [b]
                msgs.append("dependency cycle: " + " -> ".join(cyc))
            elif color.get(b) is None:
                dfs(b, stack + [b])
        color[tid] = 2

    for tid in sorted(graph):
        if color.get(tid) is None:
            dfs(tid, [tid])
    return msgs


# ---- state access ----------------------------------------------------------

def effective_status(ticket, state) -> str:
    """state.json is the authority; frontmatter is only synced at close."""
    rec = ((state or {}).get("tickets") or {}).get(ticket.id)
    if rec and rec.get("status"):
        return rec["status"]
    return ticket.status


def blocker_closed(blocker, graph, state) -> bool:
    if "/" in blocker:
        t = _xticket(blocker, graph)
        return t is not None and t.status == "closed"
    t = graph.get(blocker)
    return t is not None and effective_status(t, state) == "closed"


# ---- affects ---------------------------------------------------------------

def _norm(p: str) -> str:
    p = p.replace("\\", "/").strip()
    while p.endswith("/**"):
        p = p[:-3]
    return p.rstrip("/")


def _pair_overlap(x: str, y: str) -> bool:
    a, b = _norm(x), _norm(y)
    if not a or not b:
        return False
    if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
        return True
    return fnmatch.fnmatch(a, b) or fnmatch.fnmatch(b, a)


def affects_overlap(a, b) -> bool:
    return any(_pair_overlap(x, y) for x in (a or []) for y in (b or []))


# ---- held / ready / terminated --------------------------------------------

def _answered_fn(graph, answered):
    if answered:
        return answered
    md = getattr(graph, "map_dir", None)
    return lambda tid: bool(md) and question_status(md, tid) == "answered"


def held_set(graph, state, answered=None) -> set:
    """Tickets that must not launch: status held, needs_human not yet answered, or any
    transitive dependent of those."""
    fn = _answered_fn(graph, answered)
    held = set()
    for t in graph.values():
        if effective_status(t, state) == "held":
            held.add(t.id)
        elif t.needs_human != "none" and not fn(t.id):
            held.add(t.id)
    changed = True
    while changed:
        changed = False
        for t in graph.values():
            if t.id not in held and any(b in held for b in t.blocked_by):
                held.add(t.id)
                changed = True
    return held


def ready(graph, state, answered=None) -> list:
    held = held_set(graph, state, answered)
    running = [t for t in graph.values() if effective_status(t, state) == "running"]
    chosen = []
    for tid in sorted(graph):
        t = graph[tid]
        if not t.in_scope or effective_status(t, state) != "open":
            continue
        rec = ((state or {}).get("tickets") or {}).get(tid) or {}
        if t.assignee and not rec.get("worker"):
            continue
        if t.id in held or t.model == "integrator":
            continue
        if not all(blocker_closed(b, graph, state) for b in t.blocked_by):
            continue
        if any(affects_overlap(t.affects, o.affects) for o in running + chosen):
            continue
        chosen.append(t)
    return [t.id for t in chosen]


def terminated(graph, state, answered=None):
    def st(t):
        return effective_status(t, state)

    live = [t for t in graph.values() if t.in_scope]
    if any(st(t) == "running" for t in live):
        return False, "work-remains"
    if all(st(t) == "closed" for t in live):
        return True, "all-closed"
    if ready(graph, state, answered):
        return False, "work-remains"
    held = held_set(graph, state, answered)
    dead = {t.id for t in graph.values() if st(t) == "failed"}
    changed = True
    while changed:
        changed = False
        for t in graph.values():
            if t.id not in dead and any(b in dead for b in t.blocked_by):
                dead.add(t.id)
                changed = True
    for t in live:
        if st(t) == "closed":
            continue
        if t.id in held or t.id in dead or t.model == "integrator":
            continue
        return False, "work-remains"
    return True, "only-held-failed-integrator-left"


# ---- state schema + IO -----------------------------------------------------

def new_state(map_slug) -> dict:
    return {"version": 1, "map": map_slug, "max_concurrency_reached": 0,
            "rate_limit_events": [], "tickets": {}}


def ensure_ticket_record(state, tid) -> dict:
    rec = state.setdefault("tickets", {}).setdefault(tid, {})
    for k, v in _RECORD_DEFAULTS.items():
        rec.setdefault(k, v)
    return rec


def load_state(path, map_slug="") -> dict:
    p = Path(path)
    if not p.exists():
        return new_state(map_slug)
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(path, state) -> None:
    """Atomic: write <path>.tmp then os.replace, so a kill mid-write never corrupts."""
    p = str(path)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def reconcile_on_start(graph, state) -> list:
    """Runner died mid-run: running -> open, attempts unchanged, recovered=true."""
    fixed = []
    for tid, rec in (state.get("tickets") or {}).items():
        if rec.get("status") == "running":
            rec["status"] = "open"
            rec["recovered"] = True
            fixed.append(tid)
    return fixed
