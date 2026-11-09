"""compose: ports, doctor, plan and go. Stdlib only.

Contracts (see contracts.py) declare `consumes` / `produces`. This module:

    ports    list declared ports, unbound inputs and near-miss port names
    doctor   contracts vs disk: parse errors, duplicate ids, cycles, missing folders
    plan     resolve a request (a workflow id, or free text) into a DAG, write it as a map:
             .dagr/maps/<slug>/{map.md, tickets/T##-*.md}
    go       record the approval (GO.md). Nothing runs without it.

Everything is a file. `map.md` is the human copy and the tickets are the machine copy; the
contracts they were built from stay canonical.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import shutil
from datetime import date, datetime
from pathlib import Path

from . import config as cfgmod
from . import contracts as ct
from . import planner as pl


class CycleError(Exception):
    pass


# --------------------------------------------------------------------------
# the artifact ledger: ports that already exist, so their producers are not scheduled
# --------------------------------------------------------------------------

LEDGER_HEADER = ("# Ledger\n\nPorts that already exist in this tree. `plan` does not schedule "
                 "a workflow whose every produced port is listed here. Hand edits are fine: "
                 "a row is an attestation.\n\n| port | path | produced-by | map | date |\n"
                 "|---|---|---|---|---|\n")


def ledger_path(root) -> Path:
    return Path(root) / ".dagr" / "ledger.md"


def read_ledger(root) -> dict:
    p = ledger_path(root)
    have: dict = {}
    if not p.is_file():
        return have
    for line in ct.read(p).splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("port", "") or set(cells[0]) <= {"-", ":"}:
            continue
        have[cells[0].strip("`")] = cells[1]
    return have


def append_ledger(root, rows) -> None:
    p = ledger_path(root)
    body = ct.read(p) if p.is_file() else LEDGER_HEADER
    for r in rows:
        body += "| {port} | {path} | {by} | {map} | {date} |\n".format(**r)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((body).encode("utf-8"))


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------

def _base(port: str) -> str:
    return port.rstrip("?")


def producers_of(units: dict) -> dict:
    out = {}
    for uid in sorted(units):
        for p in units[uid].produces:
            out.setdefault(_base(p), uid)
    return out


def resolve(target: str, units: dict, have: dict, force=()):
    """Walk prerequisites and required input ports recursively. -> (nodes, order).

    A node is one of: workflow (a unit on disk, status pending or satisfied), or condition
    (a prerequisite that is not a workflow: needs a human). A workflow whose produced ports
    are all in the ledger is `satisfied` and is not scheduled.
    """
    nodes: dict = {}
    order: list = []
    stack: list = []
    prod = producers_of(units)

    def satisfied(u) -> bool:
        ports = [_base(p) for p in u.produces]
        return bool(ports) and all(p in have for p in ports) and u.id not in force

    def visit(uid: str, why: str):
        if uid in stack:
            raise CycleError(" -> ".join(stack[stack.index(uid):] + [uid]))
        if uid in nodes:
            return
        stack.append(uid)
        u = units.get(uid)
        if u is None:
            nodes[uid] = {"id": uid, "kind": "condition", "status": "blocked", "why": why,
                          "depends_on": [],
                          "note": "not a workflow in this tree: a precondition a human must "
                                  "confirm"}
            order.append(uid)
            stack.pop()
            return
        deps, unbound = [], []
        for pre in u.prerequisites:
            pid = pre[len("condition:"):] if pre.startswith("condition:") else pre
            if pre.startswith("condition:"):
                if pid not in nodes:
                    nodes[pid] = {"id": pid, "kind": "condition", "status": "blocked",
                                  "why": f"declared prerequisite of `{uid}`", "depends_on": [],
                                  "note": "explicit precondition"}
                    order.append(pid)
                deps.append(pid)
                continue
            pu = units.get(pid)
            if pu is not None and satisfied(pu):
                continue
            visit(pid, f"prerequisite of `{uid}`")
            deps.append(pid)
        for port in u.required_ports():
            b = _base(port)
            if b in have:
                continue
            src = prod.get(b)
            if src is None or src == uid:
                unbound.append(b)
                continue
            if satisfied(units[src]):
                continue
            visit(src, f"produces `{b}`, which `{uid}` consumes")
            if src not in deps:
                deps.append(src)
        nodes[uid] = {"id": uid, "kind": "workflow", "status": "pending", "why": why,
                      "depends_on": deps, "path": u.rel, "contract": u.file_rel,
                      "consumes": u.consumes, "produces": u.produces,
                      "stages": [s.name for s in u.stages], "unbound_inputs": unbound}
        order.append(uid)
        stack.pop()

    visit(target, "the request")
    return nodes, topo(nodes, order)


def topo(nodes: dict, order):
    """Kahn, stable by discovery order."""
    indeg = {n: sum(1 for d in nodes[n]["depends_on"] if d in nodes) for n in order}
    out, ready = [], [n for n in order if indeg[n] == 0]
    while ready:
        n = ready.pop(0)
        out.append(n)
        for m in order:
            if n in nodes[m]["depends_on"]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready.append(m)
    for n in order:
        if n not in out:
            out.append(n)
    return out


def merge(target_results):
    nodes, order = {}, []
    for n2, o2 in target_results:
        for nid in o2:
            if nid not in nodes:
                nodes[nid] = n2[nid]
                order.append(nid)
    return nodes, topo(nodes, order)


def wiring(nodes, order, have) -> dict:
    """node -> {port: producing node id | "ledger" | "unbound"}"""
    prod = {}
    for nid in order:
        for p in nodes[nid].get("produces") or []:
            prod.setdefault(_base(p), nid)
    out = {}
    for nid in order:
        w = {}
        for port in nodes[nid].get("consumes") or []:
            b = _base(port)
            if b in prod and prod[b] != nid:
                w[b] = prod[b]
            elif b in have:
                w[b] = "ledger"
            elif not port.endswith("?"):
                w[b] = "unbound"
        out[nid] = w
    return out


# --------------------------------------------------------------------------
# ports
# --------------------------------------------------------------------------

def ports_report(units: dict, have: dict) -> dict:
    prod = {}
    cons = {}
    for uid in sorted(units):
        for p in units[uid].produces:
            prod.setdefault(_base(p), []).append(uid)
        for p in units[uid].consumes:
            cons.setdefault(_base(p), []).append(uid)
    unbound, mism = [], []
    for uid in sorted(units):
        for p in units[uid].required_ports():
            b = _base(p)
            if b in prod or b in have:
                continue
            near = difflib.get_close_matches(b, list(prod), n=1, cutoff=0.75)
            unbound.append({"port": b, "consumer": uid})
            if near:
                mism.append({"port": b, "consumer": uid, "nearest_produced": near[0],
                             "producer": prod[near[0]][0]})
    dangling = [{"port": p, "producer": u[0]} for p, u in sorted(prod.items())
                if p not in cons]
    dup = [{"port": p, "producers": u} for p, u in sorted(prod.items()) if len(u) > 1]
    return {
        "workflows": [{"id": u.id, "contract": u.file_rel, "consumes": u.consumes,
                       "produces": u.produces} for _i, u in sorted(units.items())],
        "wiring": [{"from": prod[b][0], "port": b, "to": c}
                   for b in sorted(cons) if b in prod for c in cons[b] if c != prod[b][0]],
        "unbound_inputs": unbound, "mismatches": mism,
        "dangling_outputs": dangling, "duplicate_producers": dup}


def render_ports(rep: dict) -> str:
    L = ["## Workflows", "| workflow | contract | consumes | produces |", "|---|---|---|---|"]
    for w in rep["workflows"]:
        L.append(f"| {w['id']} | {w['contract']} | {', '.join(w['consumes']) or '-'} | "
                 f"{', '.join(w['produces']) or '-'} |")
    L += ["", "## Wiring"]
    L += [f"- {w['from']} --{w['port']}--> {w['to']}" for w in rep["wiring"]] or ["- none"]
    L += ["", "## Unbound inputs (nothing produces these; fine for human-supplied inputs)"]
    L += [f"- {u['port']} ({u['consumer']})" for u in rep["unbound_inputs"]] or ["- none"]
    L += ["", "## Possible mismatches (an unbound input is close to a produced port)"]
    L += [f"- {m['port']} ({m['consumer']}) is close to {m['nearest_produced']} "
          f"({m['producer']})" for m in rep["mismatches"]] or ["- none"]
    L += ["", "## Dangling outputs (nobody consumes these; fine for final deliverables)"]
    L += [f"- {d['port']} ({d['producer']})" for d in rep["dangling_outputs"]] or ["- none"]
    if rep["duplicate_producers"]:
        L += ["", "## Ports produced by more than one workflow"]
        L += [f"- {d['port']}: {', '.join(d['producers'])}" for d in rep["duplicate_producers"]]
    return "\n".join(L) + "\n"


def cmd_ports(root, cfg, as_json=False, out=print) -> int:
    units, issues = ct.discover(root, cfg)
    rep = ports_report(units, read_ledger(root))
    if as_json:
        out(json.dumps(rep, indent=2))
    elif not units:
        out("no contracts found (a CONTEXT.md whose frontmatter has `id` and `consumes` or "
            "`produces`). Run `scan`, then add port frontmatter to your workflows.")
    else:
        out(render_ports(rep))
    return 0


# --------------------------------------------------------------------------
# doctor
# --------------------------------------------------------------------------

def doctor_report(root, cfg) -> list:
    """-> list of (level, message); level is "error" or "warn"."""
    root = Path(root)
    units, issues = ct.discover(root, cfg)
    out = []
    for i in issues:
        lvl = "warn" if i["kind"] == "half-declared" else "error"
        out.append((lvl, f"{i['path']}: {i['kind']}: {i['message']}"))
    glob = cfg.get("workflow_glob")
    if cfg.get("workflows_root") and not (root / cfg["workflows_root"]).is_dir():
        out.append(("error", f"config workflows_root `{cfg['workflows_root']}` is not a folder"))
    if glob:
        name = cfg.get("contract_name") or "CONTEXT.md"
        for d in sorted(root.glob(str(glob).rstrip("/\\"))):
            if d.is_dir() and not (d / name).is_file():
                out.append(("warn", f"{ct.rel(d, root)}: matches workflow_glob but has no "
                                    f"{name}"))
    for k in ("l0_files",):
        for f in cfg.get(k) or []:
            if isinstance(f, str) and not (root / f).exists():
                out.append(("warn", f"config {k}: `{f}` does not exist"))
    for k in ("knowledge_dirs", "output_dirs"):
        for f in cfg.get(k) or []:
            if isinstance(f, str) and not (root / f).is_dir():
                out.append(("warn", f"config {k}: `{f}` is not a folder"))
    prod = producers_of(units)
    for u in sorted(units.values(), key=lambda x: x.id):
        for pre in u.prerequisites:
            pid = pre[len("condition:"):] if pre.startswith("condition:") else pre
            if not pre.startswith("condition:") and pid not in units:
                out.append(("warn", f"{u.id}: prerequisite `{pid}` is not a known workflow "
                                    "(write `condition:<name>` for a human precondition)"))
        for c in u.composable_with:
            if c not in units:
                out.append(("warn", f"{u.id}: composable_with `{c}` is not a known workflow"))
        if not u.stages:
            out.append(("warn", f"{u.id}: no stage folders next to {u.file_rel} (numbered "
                                "folders or stages/); a worker has only the contract to follow"))
        else:
            for s in u.stages:
                if ct.context_file(s) is None:
                    out.append(("warn", f"{u.id}: stage folder {ct.rel(s, root)} has no "
                                        "CONTEXT.md"))
        for port in u.consumes + u.produces:
            if not re.fullmatch(r"[\w][\w.\-]*\??", port):
                out.append(("error", f"{u.id}: odd port name `{port}`"))
    # cycles: through prerequisites and through port wiring
    edges = {u.id: set() for u in units.values()}
    for u in units.values():
        for pre in u.prerequisites:
            if pre in units:
                edges[u.id].add(pre)
        for port in u.required_ports():
            src = prod.get(_base(port))
            if src and src != u.id:
                edges[u.id].add(src)
    color: dict = {}
    seen_cycles = set()

    def dfs(n, stack):
        color[n] = 1
        for m in sorted(edges[n]):
            if color.get(m) == 1:
                cyc = stack[stack.index(m):] + [m]
                key = frozenset(cyc)
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    out.append(("error", "dependency cycle: " + " -> ".join(cyc)))
            elif color.get(m) is None:
                dfs(m, stack + [m])
        color[n] = 2

    for n in sorted(edges):
        if color.get(n) is None:
            dfs(n, [n])
    return out


def cmd_doctor(root, cfg, as_json=False, out=print) -> int:
    rep = doctor_report(root, cfg)
    errors = [m for lvl, m in rep if lvl == "error"]
    units, _i = ct.discover(root, cfg)
    if as_json:
        out(json.dumps({"contracts": len(units), "problems": [
            {"level": l, "message": m} for l, m in rep]}, indent=2))
    else:
        out(f"doctor: {len(units)} contract(s) found, {len(errors)} error(s), "
            f"{len(rep) - len(errors)} warning(s)")
        if not units and not errors:
            out("  no contracts yet (expected before setup apply)")
        for lvl, m in rep:
            out(f"  {lvl.upper()}: {m}")
        try:
            w = cfgmod.worker_cfg(cfg)
            first = (w.get("_bin") or (w.get("argv") or [w.get("command", "").split(" ")[0]]))[0]
            if not w.get("_bin") and not Path(first).exists() and not shutil.which(first):
                out(f"  WARN: worker `{w['_name']}`: binary `{first}` not found on PATH "
                    "(plan falls back to keywords; run needs it)")
        except cfgmod.ConfigError as e:
            out(f"  ERROR: {e}")
            return 1
    return 1 if errors else 0


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------

def slugify(text: str, n=40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:n].strip("-")
    return s or "plan"


def _today() -> str:
    return date.today().isoformat()


def _output_path(u, root, cfg) -> str:
    """Where a workflow's worker may write: `<output dir>/<id>/` when the tree keeps a shared
    output folder with a folder for this workflow, else `<workflow folder>/output/`."""
    for od in (cfg.get("output_dirs") or []) + ["output"]:
        if isinstance(od, str) and (Path(root) / od / u.id).is_dir():
            return f"{od.rstrip('/')}/{u.id}/"
    return f"{u.rel}/output/"


def model_available(worker) -> tuple:
    """-> (ok, reason). Checks only that the worker command can be found, not that it works."""
    if os.environ.get("DAGR_NO_MODEL"):
        return False, "DAGR_NO_MODEL is set"
    if worker.get("_bin"):
        first = worker["_bin"][0]
    elif worker.get("command"):
        first = (worker["command"].split() or [""])[0]
    else:
        first = (worker.get("argv") or [""])[0]
    if not first:
        return False, f"worker `{worker.get('_name')}` has no command configured"
    if Path(first).exists() or shutil.which(first):
        return True, ""
    return False, f"worker binary `{first}` not found"


def plan_request(root, cfg, request, slug=None, use_model=True, expand_stages=False,
                 out=print, model_fn=None, also=None) -> int:
    root = Path(root)
    units, issues = ct.discover(root, cfg)
    also = [a.strip() for a in (also or []) if a and a.strip()]
    bad = [a for a in also if a not in units]
    if bad:
        out("! --also: not a workflow id: " + ", ".join(bad) + ". Workflows: "
            + ", ".join(sorted(units)))
        return 2
    if not units:
        out("! no contracts found (a CONTEXT.md whose frontmatter has `id` and `consumes` or "
            "`produces`). Run `scan`, then add port frontmatter to your workflows.")
        return 2
    have = read_ledger(root)
    request = (request or "").strip()
    method, reason, plan = "", "", None
    if request in units:
        method = f"workflow id `{request}`"
        plan = {"goal": f"Run `{request}`", "target_ports": [], "workflows": [request],
                "gaps": []}
    else:
        if use_model:
            try:
                worker, model = cfgmod.role_cfg(cfg, "planner")
            except cfgmod.ConfigError as e:
                worker, model, reason = None, "", str(e)
            if worker is not None:
                ok, reason = model_available(worker)
                if ok or model_fn is not None:
                    out(f"plan: calling {worker['_name']} as planner (may cost money); "
                        "use --no-model to avoid")
                    try:
                        fn = model_fn or pl.worker_model_fn(
                            worker, model, root, cfgmod.dagr_dir(root) / "tmp")
                        plan = pl.plan_from_prompt(request, units, fn, have)
                        method = f"model planner (worker `{worker['_name']}`)"
                    except pl.PlannerError as e:
                        reason = f"the planner call failed: {e}"
                        plan = None
        else:
            reason = "model planning was turned off"
        if plan is None:
            plan = pl.keyword_plan(request, units, have)
            method = f"keyword fallback (no model used: {reason or 'none configured'})"
    if not plan["workflows"] and not plan["gaps"]:
        out("! the planner returned nothing to run")
        return 2
    if not plan["workflows"]:
        out("! nothing in this tree matches the request. Workflows: "
            + ", ".join(sorted(units)))
        out("  Name one directly: `plan <workflow-id>`")
        return 2

    try:
        results = [resolve(w, units, have) for w in dict.fromkeys(plan["workflows"] + also)]
    except CycleError as e:
        out(f"! prerequisite cycle: {e}")
        return 3
    nodes, order = merge(results)
    # a workflow named again (repeated --also, or already planned) becomes another instance
    wanted = list(plan["workflows"]) + also
    for wid in dict.fromkeys(wanted):
        extra = wanted.count(wid) - 1 if wid in nodes else 0
        for k in range(2, 2 + extra):
            iid = f"{wid}#{k}"
            src = nodes[wid]
            nodes[iid] = dict(src, id=iid, unit=wid, instance=k,
                              depends_on=list(src["depends_on"]) + [wid],
                              why=f"instance {k} of `{wid}` (asked for more than once)")
            order.insert(order.index(wid) + k - 1, iid)
    gap_ids = []
    for g in plan["gaps"]:
        gid = "gap-" + slugify(g["port"], 30)
        if gid not in nodes:
            nodes[gid] = {"id": gid, "kind": "gap", "status": "blocked",
                          "why": g.get("why") or f"no workflow produces {g['port']}",
                          "depends_on": [], "note": f"no workflow produces `{g['port']}`"}
            order.append(gid)
            gap_ids.append(gid)
    wires = wiring(nodes, order, have)
    for nid in order:   # a port wire is an ordering edge too
        for src in wires.get(nid, {}).values():
            if src in nodes and src not in nodes[nid]["depends_on"]:
                nodes[nid]["depends_on"].append(src)
    order = topo(nodes, order)
    if any(n["status"] == "pending" for n in nodes.values()) is False:
        out("! every workflow this request needs is already satisfied by the ledger")
        return 2

    slug = slug or f"{_today()}-{slugify(request if request not in units else request)}"
    md = cfgmod.map_dir(root, slug)
    if (md / "tickets").is_dir() and any((md / "tickets").glob("T*.md")):
        out(f"! map `{slug}` already has tickets; pick another with --map")
        return 2
    tickets = build_tickets(nodes, order, units, root, cfg, plan, request, expand_stages)
    for t in tickets:
        p = md / "tickets" / f"{t['id']}-{t['slug']}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes((t["text"]).encode("utf-8"))
    (md / "assets").mkdir(exist_ok=True)
    (md / "map.md").write_bytes((render_map(slug, request, method, plan, tickets, nodes, order,
                                          wires)).encode("utf-8"))
    out(f"map: .dagr/maps/{slug}/map.md  ({len(tickets)} ticket(s); planner: {method})")
    for t in tickets:
        out(f"  {t['id']}  {t['title']}  blocked-by [{', '.join(t['blocked_by'])}]"
            + ("  NEEDS HUMAN" if t["needs_human"] else ""))
    out(f"Review it, then approve with: dagr go {slug}   (nothing runs before that)")
    return 0


def build_tickets(nodes, order, units, root, cfg, plan, request, expand):
    """Ticket specs in dependency order. One ticket per node; with `expand` a workflow with
    stage folders becomes one ticket per stage, chained."""
    first, last, specs = {}, {}, []
    counter = [0]

    def new_id():
        counter[0] += 1
        return f"T{counter[0]:02d}"

    for nid in order:
        n = nodes[nid]
        deps = [last[d] for d in n["depends_on"] if d in last]
        u = units.get(n.get("unit", nid))
        inst = n.get("instance")
        base = dict(node=nid)
        if n["kind"] != "workflow":
            tid = new_id()
            q = (f"`{nid}` is not something dagr can run: {n.get('note') or n['why']}. "
                 "Confirm it is in place (or say what to do instead), then answer here.")
            specs.append(dict(base, id=tid, slug=slugify(nid, 30), title=f"Confirm: {nid}",
                              blocked_by=deps, affects=[], needs_human=q,
                              text=_ticket_text(f"Confirm: {nid}", deps, [], q, n, None, root,
                                                cfg, request, [])))
            first[nid] = last[nid] = tid
            continue
        outp = _output_path(u, root, cfg)
        if inst:
            outp += f"run-{inst}/"
        if expand and u.stages and not inst:
            prev = deps
            for i, s in enumerate(u.stages):
                tid = new_id()
                sc = ct.context_file(s)
                title = f"{nid}: stage {s.name}"
                specs.append(dict(base, id=tid, slug=slugify(f"{nid}-{s.name}", 30),
                                  title=title, blocked_by=list(prev), affects=[outp],
                                  needs_human="",
                                  text=_ticket_text(title, prev, [outp], "", n, u, root, cfg,
                                                    request, [ct.rel(sc, root)] if sc else [],
                                                    stage=s.name)))
                prev = [tid]
                if i == 0:
                    first[nid] = tid
                last[nid] = tid
            continue
        tid = new_id()
        title = f"Run {u.id}" + (f" (instance {inst})" if inst else "")
        specs.append(dict(base, id=tid, slug=slugify(nid.replace("#", "-"), 30), title=title,
                          blocked_by=deps, affects=[outp], needs_human="",
                          text=_ticket_text(title, deps, [outp], "", n, u, root, cfg, request,
                                            [])))
        first[nid] = last[nid] = tid
    return specs


def _ticket_text(title, deps, affects, question, node, u, root, cfg, request, extra_inputs,
                 stage=None):
    created = _today()
    L = ["---", f"title: {title}", "status: open",
         f"blocked-by: [{', '.join(deps)}]",
         f"affects: [{', '.join(affects)}]", "model: default",
         f"needs_human: {question if question else 'false'}", f"created: {created}"]
    if u is not None:
        L += [f"consumes: [{', '.join(u.consumes)}]", f"produces: [{', '.join(u.produces)}]"]
    L += ["---", "", f"# {title}", "", "## Goal", ""]
    if u is None:
        L += [f"A human settles `{node['id']}` before the work that depends on it can start.", ""]
    else:
        what = f"stage `{stage}` of workflow `{u.id}`" if stage else f"the workflow `{u.id}`"
        L += [f"Carry out {what} for this request: \"{request}\"", ""]
    L += ["## Inputs", "", "| File | Why |", "|---|---|"]
    if u is not None:
        L.append(f"| `{u.file_rel}` | the contract; follow its stages in order |")
        for e in extra_inputs:
            L.append(f"| `{e}` | the stage contract |")
        wires = node.get("consumes") or []
        for port in wires:
            L.append(f"| port `{_base(port)}` | " + (
                "output of an upstream ticket" if _base(port) not in node.get("unbound_inputs", [])
                else "no workflow produces it: it should already exist in your tree") + " |")
    else:
        L.append(f"| (none) | {node.get('why', '')} |")
    L += ["", "Load exactly these. Nothing else.", "", "## Process", ""]
    if u is not None:
        L += ["1. Read the contract and follow it" + (f" (stage `{stage}` only)" if stage
                                                        else " stage by stage") + ".",
              f"2. Write everything you produce under `{affects[0]}` and nowhere else.",
              "3. Record what you did in the receipt."]
    else:
        L += ["1. Read the question below and answer it in `questions/`."]
    L += ["", "## Outputs", ""]
    if u is not None:
        L += [f"- `{affects[0]}`: the finished work (ports: "
              f"{', '.join('`' + p + '`' for p in u.produces) or 'none declared'})"]
    else:
        L += ["- a human answer"]
    L += ["", "## Acceptance", ""]
    if u is not None:
        L += ["- Every stage the contract lists was carried out, or the receipt says why not.",
              f"- The files exist under `{affects[0]}` and match what the contract's Outputs "
              "section describes.",
              "- Nothing was written outside the ticket's `affects`."]
    else:
        L += ["- The question is answered."]
    if question:
        L += ["", "## Question", "", question]
    L += ["", "## Resolution", ""]
    return "\n".join(L)


def render_map(slug, request, method, plan, tickets, nodes, order, wires) -> str:
    L = [f"# Map: {slug}", "", f"- slug: {slug}", f"- request: \"{request}\"",
         f"- created: {_today()}", "- status: planned", f"- planner: {method}", ""]
    L += ["## Goal", "", plan.get("goal") or request, ""]
    L += ["## Graph", "", "```"]
    for t in tickets:
        L.append(f"{t['id']} ({t['title']})" + (
            "  <-- " + ", ".join(t["blocked_by"]) if t["blocked_by"] else "  (starts immediately)"))
    L += ["```", "",
          "A ticket starts when every ticket on its right-hand side is closed. Tickets with no "
          "arrow between them run in parallel unless their `affects` paths overlap.", ""]
    L += ["## Tickets", "", "| id | title | workflow | blocked-by | affects | needs_human |",
          "|---|---|---|---|---|---|"]
    for t in tickets:
        L.append(f"| {t['id']} | {t['title']} | {t['node']} | "
                 f"{', '.join(t['blocked_by']) or 'none'} | {', '.join(t['affects']) or '-'} | "
                 f"{'yes' if t['needs_human'] else 'no'} |")
    L += ["", "Tickets are in `tickets/T##-*.md`.", ""]
    L += ["## Ports", "", "| node | port | bound to |", "|---|---|---|"]
    any_w = False
    for nid in order:
        for port, src in (wires.get(nid) or {}).items():
            L.append(f"| {nid} | {port} | "
                     + ("**unbound** (nothing produces it)" if src == "unbound" else src) + " |")
            any_w = True
    if not any_w:
        L.append("| - | - | - |")
    L.append("")
    if plan.get("gaps"):
        L += ["## Gaps", ""]
        L += [f"- `{g['port']}`: {g['why']}" for g in plan["gaps"]]
        L.append("")
    if method_is_fallback(method):
        L += ["## Note", "",
              "No model was used to plan this: the workflows were picked by matching the words of "
              "your request against workflow ids, port names and the first paragraph of each "
              "contract. Check the list above is what you meant.", ""]
    L += ["## Approve", "", f"Run `python -B .dagr/engine/dagr/cli.py go {slug}` to approve "
          "(add `--scope T01,T02-T04` to approve part of it). Nothing runs before that.", ""]
    return "\n".join(L)


def method_is_fallback(method: str) -> bool:
    return method.startswith("keyword fallback")


# --------------------------------------------------------------------------
# go
# --------------------------------------------------------------------------

def cmd_go(root, cfg, slug, scope=None, who=None, out=print) -> int:
    from . import runner
    md = cfgmod.map_dir(root, slug)
    tdir = md / "tickets"
    if not tdir.is_dir():
        out(f"! no such map: .dagr/maps/{slug}/tickets")
        return 2
    ids = sorted(p.stem.split("-", 1)[0] for p in tdir.glob("T*.md"))
    if not ids:
        out(f"! map `{slug}` has no tickets")
        return 2
    scope_txt = scope or "all"
    ok = set(ids) if scope_txt.lower() == "all" else runner.expand_scope(scope_txt, ids)
    if not ok:
        out(f"! scope `{scope_txt}` matches no ticket ({', '.join(ids)})")
        return 2
    who = re.sub(r"\s+", "-", (who or os.environ.get("USERNAME") or os.environ.get("USER")
                               or "human").strip()) or "human"
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    go = md / "GO.md"
    new = not go.is_file()
    body = ""
    if new:
        body += (f"# GO: {slug}\n\n<!-- Written by `dagr go {slug}`. This file is the approval "
                 "act. No ticket runs until it exists. Deleting it stops new launches. -->\n\n")
    body += (f"- approved-by: {who}\n- approved-at: {now}\n- scope: {scope_txt}\n"
             f"- map: .dagr/maps/{slug}/map.md\n- tickets approved: {len(ok)}\n\n")
    with open(go, "a", encoding="utf-8", newline="\n") as f:
        f.write(body)
    out(f"GO recorded for {slug}: {who}, scope {scope_txt} ({len(ok)} ticket(s))")
    return 0
