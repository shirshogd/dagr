"""runner: owns a map's graph after the human's one `go`. Stdlib only.

Loop: load state from disk -> graphcore.ready() over the go's scope -> launch each ready
ticket as its own headless worker -> poll -> record cost/session -> review -> commit (only in a
git repo, path-limited) -> stop when graphcore.terminated(). All state lives on disk, so
kill/restart is safe.

Exit codes: 0 terminated (or dry-run ok), 2 refused / invalid, 3 runner already running,
4 stuck, 5 terminated with held/failed tickets (only with --strict-exit).

The last stdout line of a terminated run is always `RUN-SUMMARY {json}` (also written to
assets/run-summary.json) with result, reason, closed, held, failed, open and the intended
`exit` code; unattended wrappers should read that, not just the exit status.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from . import config, graphcore, holds, review_step, status as status_mod
from . import runner_lib as rl

GO_RE = re.compile(r"^go:\s*\S+\s+\d{4}-\d{2}-\d{2}\s+scope:\s*(.+)$", re.M)
KIT_SCOPE_RE = re.compile(r"^-\s*scope:\s*(.+)$", re.M)   # the `dagr go` GO.md format
_ID = re.compile(r"^T(\d+)([a-z]?)$")


# ---- go gate -------------------------------------------------------------------

def _num(tok):
    m = re.fullmatch(r"T?(\d+)[a-z]?", tok.strip())
    return int(m.group(1)) if m else None


def expand_scope(text, ids) -> set:
    """`T01,T02,T04-T09` -> set of ids present in `ids`. Numeric inclusive ranges;
    letter-suffixed ids (T03a) are included when their number is in range."""
    out = set()
    for tok in re.split(r"[,\s]+", text.strip()):
        if not tok:
            continue
        if "-" in tok:
            a, _, b = tok.partition("-")
            lo, hi = _num(a), _num(b)
            if lo is None or hi is None:
                continue
            nums = range(lo, hi + 1)
        else:
            n = _num(tok)
            if n is None:
                continue
            nums = [n]
        for i in ids:
            m = _ID.match(i)
            if m and int(m.group(1)) in nums:
                out.add(i)
    return out


def read_go(map_dir, ids):
    """Returns (scope_set, error_or_None). Never writes GO.md."""
    go = Path(map_dir) / "GO.md"
    if not go.is_file():
        return None, "no GO.md"
    text = go.read_text(encoding="utf-8", errors="replace")
    scope, found = set(), False
    for m in list(GO_RE.finditer(text)) + list(KIT_SCOPE_RE.finditer(text)):
        found = True
        if m.group(1).strip().lower() == "all":
            scope |= set(ids)
        else:
            scope |= expand_scope(m.group(1), ids)
    if not found or not scope:
        return None, "no go line with a scope"
    return scope, None


# ---- pidfile -------------------------------------------------------------------

def acquire_pidfile(path) -> bool:
    """Atomic create (O_EXCL). A live or own pid in an existing file refuses; a stale one is
    removed and the create retried once."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(str(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                old = int(p.read_text().strip())
            except (ValueError, OSError):
                old = None
            if old and (old == os.getpid() or rl.pid_alive(old)):
                return False
            try:
                p.unlink()
            except OSError:
                return False
            continue
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        return True
    return False


# ---- runner --------------------------------------------------------------------

class Runner:
    def __init__(self, root, slug, graph, state, worker=None, reviewer_worker=None, cfg=None,
                 poll=5.0, max_turns=150, out=print, stall_minutes=20.0, max_minutes=90.0,
                 max_budget_usd=10.0, backoff_scale=1.0, strict_exit=False,
                 max_rate_retries=5, review=True, reviewer_model=""):
        self.cfg = cfg or config.load_config(root)
        self.root, self.slug, self.graph, self.state = Path(root), slug, graph, state
        self.worker = worker or config.worker_cfg(self.cfg)
        self.reviewer_worker = reviewer_worker
        self.review, self.reviewer_model = review, reviewer_model
        self.poll, self.max_turns, self.out = poll, max_turns, out
        self.stall_minutes, self.max_minutes = stall_minutes, max_minutes
        self.max_budget_usd, self.strict_exit = max_budget_usd, strict_exit
        self.max_rate_retries = max_rate_retries
        self.backoff = rl.Backoff(backoff_scale)
        self.started_at = {}    # tid -> time.time() at launch
        self.killed = {}        # tid -> "stalled" | "wall-clock"
        self.running_at_poll = 0
        self.map_dir = config.map_dir(self.root, slug)
        self.state_path = self.map_dir / "state.json"
        self.procs = {}
        self.idle_sig = None
        self.baseline = {}      # tid -> porcelain snapshot at launch
        self.cohort = {}        # tid -> ids of tickets running at any time during its run
        self.git = bool(self.cfg.get("git_commits", True)) and rl.is_git_repo(self.root)

    # state helpers
    def rec(self, tid):
        return graphcore.ensure_ticket_record(self.state, tid)

    def save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        graphcore.save_state(self.state_path, self.state)

    def set_fm(self, ticket, key, value):
        rl.set_ticket_fm(ticket, key, value)

    def model_for(self, t):
        return t.model if t.model not in ("", "default", "integrator") else None

    def startup_recover(self):
        """Orphans (running at last death) -> open. Kill any live old pid first, clear the
        runner-set assignee (graphcore.ready skips an assigned ticket with no worker)."""
        old = {tid: dict(r) for tid, r in self.state.get("tickets", {}).items()}
        fixed = graphcore.reconcile_on_start(self.graph, self.state)
        for tid in fixed:
            pid = old.get(tid, {}).get("pid")
            if pid and rl.pid_alive(pid):
                res = rl.kill_verified(pid, old.get(tid, {}).get("pid_ident"))
                if res in ("mismatch", "unverified"):
                    self.out(f"WARN {tid}: old worker pid {pid} NOT killed ({res}: pid reused "
                             "or no creation time recorded)")
            t = self.graph.get(tid)
            self.rec(tid)
            if t is not None and t.assignee.startswith("runner-"):
                self.set_fm(t, "assignee", "")
            if t is not None:
                self.set_fm(t, "status", "open")
        self.save()
        stale = self.stale_running()
        if stale:
            self.out("STALE-RUNNING: frontmatter says running but no live worker: "
                     + ", ".join(stale) + " (reset them to open, or finish them by hand)")
        return fixed

    def stale_running(self):
        return sorted(t.id for t in self.graph.values()
                      if graphcore.effective_status(t, self.state) == "running"
                      and t.id not in self.procs)

    # launching
    def launch_worker(self, t):
        rec = self.rec(t.id)
        base = rl.porcelain(self.root)
        if self.git and "baseline_affects_dirty" not in rec:
            # fresh launch: affects dirty now would be swept into the ticket's commit, so hold
            # WITHOUT spending a worker. A later retry keeps the recorded (clean) baseline.
            pre = sorted(p for p in base if graphcore.affects_overlap([p], t.affects))
            if pre:
                self.hold(t, "affects were already dirty before launch: not swept into a "
                          "commit", ["- pre-dirty: " + ", ".join(pre)])
                # file a question so answering it (status: answered) releases the hold
                self.set_fm(t, "needs_human",
                            "these paths had uncommitted changes before launch: "
                            + ", ".join(pre)
                            + " - commit, stash or discard them, then answer this question "
                            "to release the ticket")
                holds.write_question(t, self.slug, self.map_dir, self.graph)
                self.out(f"HOLD {t.id}: question filed at .dagr/maps/{self.slug}/questions/"
                         f"Q-{t.id}.md")
                self.save()
                return
            rec["baseline_affects_dirty"] = []
        attempt = int(rec.get("attempts") or 0) + 1
        adir = rl.assets_dir(self.root, self.slug, t.id)
        adir.mkdir(parents=True, exist_ok=True)
        brief = rl.build_brief(t, self.root, rec.get("notes"))
        proc = rl.launch_worker(
            self.worker, brief, self.root, adir / f"worker-{attempt}.out",
            adir / f"worker-{attempt}.err", self.model_for(t),
            rl.build_allowed_tools(t, self.root, self.slug), rl.DISALLOWED,
            max_turns=self.max_turns, prompt_file=adir / "brief.md",
            max_budget_usd=self.max_budget_usd)
        self.baseline[t.id] = base
        self.started_at[t.id] = time.time()
        self.killed.pop(t.id, None)
        self.cohort[t.id] = set(self.procs)
        for other in self.procs:
            self.cohort.setdefault(other, set()).add(t.id)
        self.procs[t.id] = proc
        rec.update(status="running", pid=proc.pid, pid_ident=rl.proc_ident(proc.pid),
                   started=rl.now_iso(), attempts=attempt)
        rec.pop("recovered", None)
        self.set_fm(t, "assignee", f"runner-{os.getpid()}-{t.id}")
        self.set_fm(t, "status", "running")
        running = sum(1 for x in self.graph.values()
                      if graphcore.effective_status(x, self.state) == "running")
        self.state["max_concurrency_reached"] = max(
            int(self.state.get("max_concurrency_reached") or 0), running)
        self.save()   # before the next launch, so a crash cannot double-launch
        self.out(f"LAUNCH {t.id} attempt {attempt} pid {proc.pid}")

    def _kill_worker(self, tid, proc, why):
        rec = self.rec(tid)
        res = rl.kill_verified(proc.pid, rec.get("pid_ident"))
        if res in ("mismatch", "unverified"):   # we own this Popen: it is ours to kill
            rl.kill_tree(proc.pid)
        try:
            proc.wait(timeout=20)
        except Exception:
            pass
        self.killed[tid] = why
        self.out(f"KILL {tid} ({why})")

    def check_limits(self):
        """Wall-clock ceiling and stall detection for every live worker."""
        now = time.time()
        for tid, proc in list(self.procs.items()):
            if proc.poll() is not None or tid in self.killed:
                continue
            t0 = self.started_at.get(tid, now)
            if self.max_minutes and now - t0 > self.max_minutes * 60:
                self._kill_worker(tid, proc, "wall-clock")
                continue
            if self.stall_minutes:
                adir = rl.assets_dir(self.root, self.slug, tid)
                tk = self.graph.get(tid)
                watch = [adir] + [self.root / a for a in (tk.affects if tk else [])
                                  if not any(c in a for c in "*?[")]
                last = max(t0, rl.newest_mtime(watch))
                if now - last > self.stall_minutes * 60:
                    self._kill_worker(tid, proc, "stalled")

    def poll_workers(self):
        self.check_limits()
        self.running_at_poll = len(self.procs)
        done = []
        for tid, proc in list(self.procs.items()):
            rc = proc.poll()
            if rc is not None:
                done.append((tid, rc))
                del self.procs[tid]
        return done

    # results
    def _fmt(self):
        return self.worker.get("output", "claude-stream")

    def parse_result(self, t, rc):
        """-> (ok, note). Updates worker/cost in state."""
        rec = self.rec(t.id)
        attempt = int(rec.get("attempts") or 1)
        adir = rl.assets_dir(self.root, self.slug, t.id)
        data = rl.read_output(adir / f"worker-{attempt}.out", self._fmt())
        if data:
            rec["worker"] = data.get("session_id") or rec.get("worker")
            try:
                rec["cost_usd"] = float(rec.get("cost_usd") or 0) + float(
                    data.get("total_cost_usd") or 0)
            except (TypeError, ValueError):
                pass
        if t.id in self.killed:
            return False, self.killed[t.id]
        if data is None:
            return False, "unreadable worker output"
        if rc != 0:
            return False, f"exit code {rc}"
        if data.get("is_error"):
            return False, f"worker reported is_error: {str(data.get('result'))[:200]}"
        if not (adir / "receipt.md").is_file():
            return False, "no receipt written"
        return True, ""

    def finish(self, t, rc):
        try:
            self._finish(t, rc)
        except Exception as e:   # one ticket's bug must not kill the loop
            rec = self.rec(t.id)
            rec["status"] = "failed"
            rec["notes_last_failure"] = f"runner error: {type(e).__name__}: {e}"
            try:
                self.set_fm(t, "status", "failed")
            except Exception:
                pass
            self.out(f"FAILED {t.id} (runner error: {type(e).__name__}: {e})")
            self.save()

    def on_worker_done(self, t):
        if not self.review:
            return None
        running_affects = [a for oid in self.procs for a in self.graph[oid].affects]
        self.set_fm(t, "status", "review")   # on disk while the reviewer runs
        return review_step.review_and_decide(
            t, self.state, self.slug, self.root, reviewer_model=self.reviewer_model,
            worker=self.reviewer_worker, threshold=self.cfg.get("pass_threshold"),
            max_attempts=self.cfg.get("max_attempts"), ignore=running_affects)

    def _finish(self, t, rc):
        rec = self.rec(t.id)
        rec["finished"] = rl.now_iso()
        rec.pop("pid", None)
        ok, note = self.parse_result(t, rc)
        if self.rate_limited(t, rc, ok):
            return
        self.rec(t.id)["rate_limit_retries"] = 0   # (a 429 returned above, before this line)
        if ok:
            self.state["rate_limit_consecutive"] = 0
            (self.state.get("backoff_until") or {}).pop(t.id, None)
        verdict = self.on_worker_done(t) if ok else None
        if not ok:
            rec["notes_last_failure"] = note
            verdict = "fail"
        elif verdict is None:
            verdict = "pass"
        if verdict == "pass":
            self.close(t)
        elif verdict == "retry":
            rec["status"] = "open"
            self.set_fm(t, "status", "open")
            self.set_fm(t, "assignee", "")
            self.out(f"RETRY {t.id} ({note or 'review'})")
        else:
            rec["status"] = "failed"
            rec.pop("baseline_affects_dirty", None)
            self.set_fm(t, "status", "failed")
            self.out(f"FAILED {t.id} ({note or 'review'})")
        self.save()

    def rate_limited(self, t, rc, ok) -> bool:
        """429 / overloaded / usage limit: not an attempt. Back off, put the ticket back to
        open. Only a failing run is inspected (a good result may merely mention the words)."""
        if t.id in self.killed:
            return False
        rec = self.rec(t.id)
        attempt = int(rec.get("attempts") or 1)
        adir = rl.assets_dir(self.root, self.slug, t.id)
        texts = []
        data = rl.read_output(adir / f"worker-{attempt}.out", self._fmt())
        if data and data.get("is_error"):
            texts.append(data.get("result"))
        if ok and not texts:
            return False
        try:   # stderr and the result's error text only; never arbitrary stdout
            texts.append((adir / f"worker-{attempt}.err").read_text(
                encoding="utf-8", errors="replace"))
        except OSError:
            pass
        if not rl.Backoff.matches(*texts):
            return False
        n_retry = int(rec.get("rate_limit_retries") or 0)
        if n_retry >= self.max_rate_retries:
            self.out(f"RATE-LIMIT {t.id}: {n_retry} consecutive retries used, counting this "
                     "attempt as a normal failure")
            rec["rate_limit_retries"] = 0
            return False
        rec["rate_limit_retries"] = n_retry + 1
        st = self.state
        now = time.time()
        conc = max(1, self.running_at_poll)
        in_window = now < float(st.get("global_backoff_until") or 0)
        n = int(st.get("rate_limit_consecutive") or 0)
        if in_window:
            until = float(st["global_backoff_until"])   # same burst: do not escalate n
            delay = max(0.0, until - now)
        else:
            delay = self.backoff.delay(n)
            until = now + delay
            st["rate_limit_consecutive"] = n + 1
            st["global_backoff_until"] = until
        st.setdefault("backoff_until", {})[t.id] = until
        st.setdefault("rate_limit_events", []).append(
            {"ts": rl.now_iso(), "concurrency": conc, "delay": round(delay, 3)})
        if st.get("rate_ceiling") is None:
            st["rate_ceiling"] = conc
        rec["attempts"] = max(0, attempt - 1)   # a 429 never consumes an attempt
        rec["status"] = "open"
        rec["notes_last_failure"] = "rate limited (not counted)"
        rec.pop("pid", None)
        self.set_fm(t, "status", "open")
        self.set_fm(t, "assignee", "")
        self.out(f"RATE-LIMIT {t.id}: backing off {delay:.1f}s (attempt not counted, "
                 f"concurrency {conc})")
        self.save()
        return True

    def stray_paths(self, t):
        """Paths changed since launch that are not this ticket's affects/assets, not a ticket
        that ran concurrently. Detection only: a worker with a shell can write anywhere, and
        edits to a file that was already dirty at launch are invisible to a status diff."""
        base = self.baseline.get(t.id)
        if base is None:
            return []
        now = rl.porcelain(self.root)
        ok = list(t.affects) + [f".dagr/maps/{self.slug}"]
        for oid in self.cohort.get(t.id, ()):
            ot = self.graph.get(oid)
            if ot is not None:
                ok += list(ot.affects)
        return sorted(p for p, xy in now.items()
                      if base.get(p) != xy and not graphcore.affects_overlap([p], ok))

    def hold(self, t, note, lines):
        rec = self.rec(t.id)
        rec["status"] = "held"
        rec.pop("baseline_affects_dirty", None)   # recomputed when the ticket is reset to open
        rec["notes_last_failure"] = note
        self.set_fm(t, "status", "held")
        rl.append_resolution(t.path, [f"- HELD by runner: {note}"] + lines)
        self.out(f"HELD {t.id} ({note})")

    def close(self, t):
        rec = self.rec(t.id)
        stray = self.stray_paths(t)
        if stray:
            rec["stray_paths"] = stray
            self.out(f"STRAY {t.id}: " + ", ".join(stray))
            self.hold(t, "wrote outside affects/assets: not committed",
                      ["- stray_paths: " + ", ".join(stray)])
            return
        sha = None
        if self.git:
            try:
                sha = rl.git_commit_ticket(t, self.state, self.root, self.slug,
                                           self.cfg.get("commit_trailer") or None)
            except Exception as e:   # a commit problem must not lose the finished work
                rec["commit_error"] = str(e)
                self.out(f"WARN {t.id}: commit failed, work left on disk uncommitted: {e}")
        self.mark_closed(t, sha)

    def mark_closed(self, t, sha):
        rec = self.rec(t.id)
        rec["status"] = "closed"
        rec.pop("baseline_affects_dirty", None)
        rec["receipt"] = f"{rl.assets_rel(self.slug, t.id)}/receipt.md"
        rec["commit"] = sha
        self.set_fm(t, "status", "closed")
        score = rec.get("reviewer_score")
        none = "none (not a git repo or nothing to commit)" if not self.git \
            else "none (no changes to commit)"
        rl.append_resolution(t.path, [
            f"- receipt: {rec['receipt']}",
            f"- score: {score if score is not None else 'n/a'}",
            f"- cost: ${float(rec.get('cost_usd') or 0):.2f}",
            f"- commit: {sha or none}"])
        self.out(f"CLOSED {t.id} commit {sha or '-'}")

    def try_adopt(self, t):
        """A recovered ticket whose work is already committed with a newer receipt: the
        runner died between commit and save. Close it instead of relaunching."""
        rec = self.rec(t.id)
        if not rec.get("recovered") or not self.git:
            return False
        sha = rl.find_ticket_commit(self.root, self.slug, t.id)
        rcpt = rl.assets_dir(self.root, self.slug, t.id) / "receipt.md"
        if not sha or not rcpt.is_file():
            return False
        try:
            started = time.mktime(time.strptime(rec.get("started") or "", "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            return False
        if rcpt.stat().st_mtime < started:
            return False
        self.out(f"ADOPT {t.id}: already committed as {sha[:10]}, closing instead of relaunching")
        self.mark_closed(t, sha)
        return True

    # stuck detection
    def stuck_report(self):
        """Tickets that can never become ready in this run because a blocker is an open or
        failed ticket OUTSIDE the go's scope. Returns (permanent_ids, waiting_on_other)."""
        g, st = self.graph, self.state
        held = graphcore.held_set(g, st)
        perm = set()
        remaining = [t for t in g.values() if t.in_scope and
                     graphcore.effective_status(t, st) in ("open",)
                     and t.id not in held and t.model != "integrator"]
        for t in remaining:
            for b in t.blocked_by:
                bt = g.get(b)
                if bt is not None and not bt.in_scope and \
                        graphcore.effective_status(bt, st) in ("open", "failed", "held"):
                    perm.add(t.id)
        changed = True
        while changed:
            changed = False
            for t in remaining:
                if t.id not in perm and any(
                        b in perm or graphcore.effective_status(g[b], st) == "failed"
                        for b in t.blocked_by if b in g):
                    perm.add(t.id)
                    changed = True
        rest = [t.id for t in remaining if t.id not in perm]
        return perm, rest

    # one tick
    def tick(self):
        for tid, rc in self.poll_workers():
            self.finish(self.graph[tid], rc)
        skip = set(holds.tick(self.graph, self.state, self.slug, self.root, self.map_dir,
                              out=self.out) or ())
        now = time.time()
        waiting = float(self.state.get("global_backoff_until") or 0) > now
        bo = self.state.get("backoff_until") or {}
        for tid in [x for x in graphcore.ready(self.graph, self.state) if x not in skip]:
            # ready() already excluded affects overlaps within this batch
            if waiting or float(bo.get(tid) or 0) > now:
                continue   # rate-limit back-off: launch nothing new
            if self.try_adopt(self.graph[tid]):
                continue
            self.launch_worker(self.graph[tid])
        self.save()
        try:
            status_mod.render(self.graph, self.state, self.map_dir)
        except Exception as e:   # a status renderer must never stop the run
            self.out(f"WARN status render failed: {type(e).__name__}: {e}")
        done, reason = graphcore.terminated(self.graph, self.state)
        if done:
            self.save()
            self.out(f"TERMINATED: {reason}")
            for tid, qf, q in holds.held_report(self.graph, self.state):
                self.out(f"ON HOLD {tid} -> {qf}: {q}")
            return self.summary(reason)
        if not self.procs and not graphcore.ready(self.graph, self.state):
            perm, rest = self.stuck_report()
            if perm and not rest:
                self.out("STUCK: no ticket can run; blocked by open/failed tickets outside "
                         "the go's scope or by failed tickets: " + ", ".join(sorted(perm)))
                return 4
            stale = self.stale_running()
            sig = tuple(sorted(rest)) + tuple("stale:" + x for x in stale)
            if sig != self.idle_sig:
                self.idle_sig = sig
                self.out("IDLE: waiting on external blockers (cross-map/hold) for "
                         + ", ".join(sorted(rest))
                         + ("; STALE-RUNNING (no live worker): " + ", ".join(stale)
                            if stale else ""))
        return None

    def summary(self, reason) -> int:
        """Final machine-readable line + assets/run-summary.json. -> exit code."""
        by = {"closed": [], "held": [], "failed": [], "open": []}
        held = graphcore.held_set(self.graph, self.state)
        for t in sorted(self.graph.values(), key=lambda x: x.id):
            if not t.in_scope:
                continue
            st = graphcore.effective_status(t, self.state)
            if st == "closed":
                by["closed"].append(t.id)
            elif st == "failed":
                by["failed"].append(t.id)
            elif st == "held" or t.id in held:
                by["held"].append(t.id)
            else:
                by["open"].append(t.id)
        unfinished = bool(by["held"] or by["failed"])
        code = 5 if (unfinished and self.strict_exit) else 0
        summ = {"result": "terminated", "reason": reason, "exit": code,
                "closed": by["closed"], "held": by["held"], "failed": by["failed"],
                "open": by["open"], "ts": rl.now_iso()}
        try:
            (self.map_dir / "assets").mkdir(parents=True, exist_ok=True)
            (self.map_dir / "assets" / "run-summary.json").write_text(
                json.dumps(summ, indent=2), encoding="utf-8")
        except OSError:
            pass
        self.out("RUN-SUMMARY " + json.dumps(summ, sort_keys=True))
        return code

    def run(self):
        while True:
            rc = self.tick()
            if rc is not None:
                return rc
            time.sleep(self.poll)


# ---- entry ---------------------------------------------------------------------

def run_slug(slug, root, *, dry_run=False, strict_exit=False, worker=None, reviewer_model=None,
             no_review=False, max_budget_usd=None, max_minutes=None, stall_minutes=None,
             max_turns=None, poll=5.0, backoff_scale=1.0, max_rate_retries=5, out=print) -> int:
    root = Path(root).resolve()
    cfg = config.load_config(root)
    md = config.map_dir(root, slug)
    rel = f".dagr/maps/{slug}"
    ids = [p.stem.split("-", 1)[0] for p in (md / "tickets").glob("T*.md")] \
        if (md / "tickets").is_dir() else []

    if dry_run:
        scope = None
    else:
        scope, err = read_go(md, ids)
        if err:
            out(f"REFUSED: no logged go with a scope in {rel}/GO.md")
            return 2
    try:
        graph = graphcore.load_graph(md, scope=scope, root=root)
    except graphcore.GraphError as e:
        out(f"ERROR: {e}")
        return 2
    errors = [e for e in graphcore.validate(graph)
              if not (e.split(":", 1)[0] in graph and not graph[e.split(":", 1)[0]].in_scope)]
    if errors:
        out("VALIDATION ERRORS:")
        for e in errors:
            out("  " + e)
        return 2

    state = graphcore.load_state(md / "state.json", slug)
    try:
        w = config.worker_cfg(cfg, worker)
        rw, rmodel = config.role_cfg(cfg, "reviewer")
    except config.ConfigError as e:
        out(f"ERROR: {e}")
        return 2
    if reviewer_model:
        rmodel = reviewer_model

    if dry_run:
        in_scope = sorted(t.id for t in graph.values() if t.in_scope)
        ready = graphcore.ready(graph, state)
        out(f"DRY-RUN map {slug}: scope = every ticket with a model ({len(in_scope)}): "
            + ", ".join(in_scope))
        out(f"READY ({len(ready)}): " + ", ".join(ready))
        mt = max_turns if max_turns is not None else cfg.get("max_turns", 150)
        mb = cfg.get("max_budget_usd", 10.0) if max_budget_usd is None else max_budget_usd
        for tid in ready:
            t = graph[tid]
            model = t.model if t.model not in ("", "default", "integrator") else None
            try:
                argv, feed = rl.build_argv(
                    w, model, f"{rl.assets_rel(slug, tid)}/brief.md",
                    str(root).replace("\\", "/"), rl.build_allowed_tools(t, root, slug),
                    rl.DISALLOWED, mt, mb)
                out(f"ARGV {tid}: " + " ".join(argv)
                    + ("   (brief piped to stdin)" if feed else ""))
            except Exception as e:
                out(f"ARGV {tid}: could not build ({type(e).__name__}: {e})")
        if ready:
            out("---- first brief: " + ready[0] + " ----")
            out(rl.build_brief(graph[ready[0]], root,
                               (state.get("tickets", {}).get(ready[0]) or {}).get("notes")))
        return 0

    from . import runner as _self
    pidfile = md / "assets" / "runner.pid"
    if not _self.acquire_pidfile(pidfile):
        out("runner already running")
        return 3
    try:
        r = Runner(
            root, slug, graph, state, worker=w, reviewer_worker=rw, cfg=cfg, poll=poll,
            max_turns=max_turns if max_turns is not None else cfg.get("max_turns", 150),
            stall_minutes=cfg.get("stall_minutes", 20.0) if stall_minutes is None
            else stall_minutes,
            max_minutes=cfg.get("max_minutes", 90.0) if max_minutes is None else max_minutes,
            max_budget_usd=cfg.get("max_budget_usd", 10.0) if max_budget_usd is None
            else max_budget_usd,
            backoff_scale=backoff_scale, strict_exit=strict_exit,
            max_rate_retries=max_rate_retries, review=not no_review,
            reviewer_model=rmodel, out=out)
        r.startup_recover()
        code = r.run()
    finally:
        try:
            pidfile.unlink()
        except OSError:
            pass
    return code
