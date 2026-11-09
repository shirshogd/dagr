"""Shared test helpers: a fake worker binary, throwaway trees, and a git helper."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

# One fake agent CLI for every role. Selected through DAGR_WORKER_BIN, like a real binary.
#   worker   (stdin has "# Worker brief:")   writes its affects + a receipt
#   reviewer (stdin has "# Reviewer brief")  prints `score: X` (FAKE_SCORES="0.5,0.9" is used in order)
#   planner  (stdin has "You plan work")     prints FAKE_PLAN (a JSON object)
FAKE = textwrap.dedent(r'''
    import json, os, re, sys, time
    argv = sys.argv[1:]
    if "--help" in argv:
        print("usage: fake agent -p --help"); sys.exit(0)
    brief = sys.stdin.read()
    log = os.environ.get("FAKE_LOG")
    def note(ev, tid):
        if log:
            with open(log, "a") as f:
                f.write("%s %s %.3f\n" % (ev, tid, time.time()))
    def result(text, cost=0.25, err=False):
        print(json.dumps({"type": "result", "session_id": "sess", "total_cost_usd": cost,
                          "is_error": err, "result": text}))
    if "# Reviewer brief" in brief:
        scores = [s for s in os.environ.get("FAKE_SCORES", "0.95").split(",") if s]
        sf = os.environ.get("FAKE_STATE")
        n = 0
        if sf and os.path.exists(sf):
            n = int(open(sf).read() or 0)
        if sf:
            open(sf, "w").write(str(n + 1))
        s = scores[min(n, len(scores) - 1)]
        if s == "garbage":
            result("I refuse to give a score"); sys.exit(0)
        if os.environ.get("FAKE_REVIEWER_STRAY"):
            open("reviewer_wrote.txt", "w").write("x")
        result("analysis...\nscore: %s\ndiscrepancies:\n- item unmet\nnotes:\nfix the thing" % s, 0.1)
        sys.exit(0)
    if "You plan work" in brief:
        result(os.environ.get("FAKE_PLAN", "{}")); sys.exit(0)
    m = re.search(r"# Worker brief: (T\d+[a-z]?) \((\S+)\)", brief)
    tid, slug = m.group(1), m.group(2)
    note("start", tid)
    time.sleep(float(os.environ.get("FAKE_SLEEP", "0.2")))
    mode = os.environ.get("FAKE_MODE", "")
    am = re.search(r"^affects:\s*\[(.*)\]", brief, re.M)
    for a in (am.group(1).split(",") if am else []):
        a = a.strip()
        if not a:
            continue
        if a.endswith("/"):
            a += "out.txt"
        os.makedirs(os.path.dirname(a) or ".", exist_ok=True)
        with open(a, "a") as f:
            f.write("done by %s\n" % tid)
    if mode == "stray":
        with open("new_outside.txt", "w") as f:
            f.write("x")
    if mode == "rate":
        sys.stderr.write("HTTP 429 rate limit exceeded\n")
        result("rate limit", 0.0, True); sys.exit(1)
    if mode != "noreceipt":
        d = ".dagr/maps/%s/assets/%s" % (slug, tid)
        os.makedirs(d, exist_ok=True)
        with open(d + "/receipt.md", "w") as f:
            f.write("receipt for %s\nlearned: nothing\n" % tid)
    if "retry-notes" in os.environ.get("FAKE_LOG_NOTES", "") and "Reviewer notes" in brief:
        note("saw-notes", tid)
    note("end", tid)
    result("ok")
''')

TICKET = textwrap.dedent('''\
    ---
    title: Ticket {tid}
    status: open
    blocked-by: [{blocked}]
    affects: [{affects}]
    model: default
    needs_human: {needs}
    created: 2026-11-10
    ---

    ## Goal
    Do {tid}.

    ## Inputs
    - `notes/in.txt`

    ## Definition of done
    - the file exists

    ## Resolution
    ''')


def git(root, *args):
    return subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True,
                          text=True, check=True).stdout


class TreeCase(unittest.TestCase):
    """A throwaway tree with a map `m`, a fake worker on DAGR_WORKER_BIN, no git by default."""
    slug = "m"
    use_git = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "tree"
        self.root.mkdir()
        self.fake = self.base / "fake_agent.py"
        self.fake.write_text(FAKE, encoding="utf-8")
        self.log = self.base / "fake.log"
        env = {"DAGR_WORKER_BIN": '"%s" "%s"' % (sys.executable.replace("\\", "/"),
                                                  str(self.fake).replace("\\", "/")),
               "FAKE_LOG": str(self.log), "FAKE_SLEEP": "0.3"}
        names = list(env) + ["FAKE_MODE", "FAKE_SCORES", "FAKE_STATE", "FAKE_PLAN",
                             "FAKE_REVIEWER_STRAY", "DAGR_NO_MODEL"]
        saved = {k: os.environ.get(k) for k in names}
        os.environ.update(env)
        for k in names[len(env):]:
            os.environ.pop(k, None)

        def restore():
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(restore)
        if self.use_git:
            git(self.root, "init", "-q")
            git(self.root, "config", "user.email", "t@t")
            git(self.root, "config", "user.name", "t")
        (self.root / "notes").mkdir()
        (self.root / "notes" / "in.txt").write_text("input\n")
        (self.root / "stray.txt").write_text("untracked, must never be committed\n")
        self.map = self.root / ".dagr" / "maps" / self.slug
        (self.map / "tickets").mkdir(parents=True)

    def ticket(self, tid, affects, blocked="", needs="false"):
        (self.map / "tickets" / f"{tid}-x.md").write_text(
            TICKET.format(tid=tid, affects=affects, blocked=blocked, needs=needs),
            encoding="utf-8")

    def go(self, line="go: tester 2026-11-10 scope: T01-T09"):
        (self.map / "GO.md").write_text(line + "\n", encoding="utf-8")

    def commit_base(self):
        git(self.root, "add", "--", "notes")
        git(self.root, "commit", "-q", "-m", "base")

    def run_slug(self, *, no_review=True, **kw):
        from dagr import runner
        buf = io.StringIO()
        kw.setdefault("poll", 0.05)
        with contextlib.redirect_stdout(buf):
            rc = runner.run_slug(self.slug, self.root, no_review=no_review,
                                 out=lambda s: print(s), **kw)
        return rc, buf.getvalue()

    def state(self):
        return json.loads((self.map / "state.json").read_text())

    def events(self):
        ev = {}
        for line in self.log.read_text().splitlines():
            k, tid, ts = line.split()
            ev.setdefault(tid, {})[k] = float(ts)
        return ev

    def fm(self, tid, key):
        import re
        t = (self.map / "tickets" / f"{tid}-x.md").read_text()
        return re.search(rf"^{key}:\s*(.*)$", t, re.M).group(1).strip()
