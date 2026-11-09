"""holds: a ticket that needs a human answer goes on hold alone.

A ticket whose frontmatter says `needs_human: <question>` gets a file
`.dagr/maps/<slug>/questions/Q-<T##>.md`. The human answers inside that file and changes
`status: open` to `status: answered`; that releases the hold. (`status: dropped` fails the
ticket with `replan_needed`.) `tick(...)` is the runner's first `before_launch` hook. Each tick:

  a. writes ONE question file per `needs_human` ticket (idempotent: an existing file is kept)
     and holds the ticket (state + frontmatter `status: held`);
  b. notices answered files, copies the answer into the ticket, clears `needs_human`, releases;
  c. holds every transitive dependent of a held ticket and releases dependents that are no
     longer downstream of anything held (fixed point);
  d. returns the held ids so the runner skips them. Independent work keeps launching.

No notification of any kind is sent. The files are the queue.
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

from . import frontmatter as fmt
from . import graphcore, runner_lib as rl

KILLED = {"dropped", "killed", "rejected", "withdrawn", "superseded"}
PLACEHOLDER = "<!-- dagr: write your answer below this line, then set status: answered -->"


def dependents(graph, tid) -> list:
    """Transitive dependents of `tid` (sorted)."""
    out = set()
    changed = True
    while changed:
        changed = False
        for t in graph.values():
            if t.id not in out and any(b == tid or b in out for b in t.blocked_by):
                out.add(t.id)
                changed = True
    return sorted(out)


def _rel(root, p):
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(p).as_posix()


def write_question(ticket, slug, map_dir, graph=None) -> Path:
    """Create questions/Q-<tid>.md if it does not exist. -> its path."""
    p = graphcore.question_path(map_dir, ticket.id)
    if p.is_file():
        return p
    deps = dependents(graph, ticket.id) if graph is not None else []
    blocks = ", ".join([ticket.id] + deps)
    lines = ["---", f"ticket: {ticket.id}", f"map: {slug}", "status: open",
             f"asked: {rl.now_iso()}", "---", "",
             f"# Question for {ticket.id}: {ticket.title}", "",
             ticket.sections.get("Question") if ticket.needs_human.startswith(
                 "a human answer is needed") and ticket.sections.get("Question")
             else ticket.needs_human, "",
             f"Blocks: {blocks}", "",
             "To release the hold: write your answer under `## Answer`, then change "
             "`status: open` at the top to `status: answered`. To stop this branch instead, "
             "set `status: dropped`.", "",
             "## Answer", "", PLACEHOLDER, ""]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return p


def parse_question(path):
    """-> (status, answer_text)"""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    fm, _e, _s = fmt.parse_text(text)
    status = (fm.get("status") or "open").strip().lower()
    _l, body, _st = fmt.split_frontmatter(text)
    m = re.search(r"^##[ \t]+Answer[^\n]*\n(.*)\Z", body, re.M | re.S | re.I)
    ans = m.group(1) if m else body
    ans = re.sub(r"<!--.*?-->", "", ans, flags=re.S).strip()
    return status, ans or "(answered with no text)"


def _set(ticket, key, value):
    rl.set_ticket_fm(ticket, key, value)


def _insert_section(path, heading, body):
    """Insert `## heading` before `## Resolution` (else append); keeps line endings."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    block = ["## " + heading] + body.splitlines() + [""]
    idx = next((i for i, l in enumerate(lines) if l.strip() == "## Resolution"), None)
    if idx is None:
        while lines and lines[-1] == "":
            lines.pop()
        lines += [""] + block
    else:
        lines[idx:idx] = block
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(nl.join(lines))


def _log_event(state, ev):
    evs = state.setdefault("events", [])
    if not any(e.get("event") == ev for e in evs):
        evs.append({"ts": rl.now_iso(), "event": ev})


def _mark_held(ticket, state, reason):
    rec = graphcore.ensure_ticket_record(state, ticket.id)
    rec["status"] = "held"
    rec["held_reason"] = reason
    _set(ticket, "status", "held")


def _mark_open(ticket, state):
    rec = graphcore.ensure_ticket_record(state, ticket.id)
    rec["status"] = "open"
    rec.pop("held_reason", None)
    _set(ticket, "status", "open")


def _status(t, state):
    return graphcore.effective_status(t, state)


def tick(graph, state, slug, root, map_dir=None, out=print) -> set:
    map_dir = Path(map_dir) if map_dir else Path(graph.map_dir)
    live = [t for _, t in sorted(graph.items()) if t.in_scope]

    def answered(tid):
        return graphcore.question_status(map_dir, tid) == "answered"

    # a. one question file per needs_human ticket
    for t in live:
        if t.needs_human != "none" and _status(t, state) in ("open", "held"):
            existed = graphcore.question_path(map_dir, t.id).is_file()
            q = write_question(t, slug, map_dir, graph)
            if not existed:
                out(f"HOLD {t.id}: question filed at {_rel(root, q)} ({t.needs_human[:60]})")
            if graphcore.question_status(map_dir, t.id) in ("open", ""):
                _mark_held(t, state, "needs_human")

    # b. answered / dropped questions: release (or fail)
    for t in live:
        if t.needs_human == "none" or _status(t, state) not in ("open", "held"):
            continue
        qp = graphcore.question_path(map_dir, t.id)
        if not qp.is_file():
            continue
        st, answer = parse_question(qp)
        rec = graphcore.ensure_ticket_record(state, t.id)
        if st in KILLED:
            _log_event(state, f"question-{st} {t.id}")
            rec["status"] = "failed"
            rec["replan_needed"] = True
            rec["notes_last_failure"] = f"question {st}"
            rec.pop("held_reason", None)
            _set(t, "status", "failed")
            rl.append_resolution(t.path, [f"- replan_needed: question {st}: {answer[:200]}"])
            out(f"FAILED {t.id}: question {st}, replan needed")
            continue
        if st != "answered":
            continue
        _log_event(state, f"question-answered {t.id}")
        _insert_section(t.path, f"Human answer ({datetime.date.today().isoformat()})", answer)
        _set(t, "needs_human", "none")
        rec["status"] = "open"
        rec.pop("held_reason", None)
        rec["released"] = rl.now_iso()
        _set(t, "status", "open")
        out(f"RELEASE {t.id}: question answered")

    # c. hold the downstream set, release dependents no longer held (fixed point).
    # blocker-held tickets are derived, not inputs: view them as open so they recompute
    view = {**state, "tickets": {
        k: ({**v, "status": "open"} if str(v.get("held_reason") or "").startswith("blocker:")
            else v) for k, v in (state.get("tickets") or {}).items()}}
    held = graphcore.held_set(graph, view, answered)
    for t in live:
        st = _status(t, state)
        if t.id in held:
            if st != "open":
                continue   # running/closed/failed/already held: leave alone
            if t.needs_human != "none" and not answered(t.id):
                _mark_held(t, state, "needs_human")
            else:
                b = next((b for b in t.blocked_by if b in held), "?")
                _mark_held(t, state, f"blocker:{b}")
        elif st == "held" and str(
                (state["tickets"].get(t.id) or {}).get("held_reason") or "").startswith("blocker:"):
            _mark_open(t, state)
            out(f"RELEASE {t.id}: no longer downstream of a hold")
    return {tid for tid in held if graph[tid].in_scope}


def held_report(graph, state) -> list:
    """[(ticket id, question file name, question)] for tickets waiting on the human."""
    rows = []
    for t in sorted(graph.values(), key=lambda x: x.id):
        if t.in_scope and t.needs_human != "none" \
                and graphcore.effective_status(t, state) == "held":
            rows.append((t.id, f"questions/Q-{t.id}.md", t.needs_human))
    return rows
