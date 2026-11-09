import json
import os
import unittest
from pathlib import Path

import helpers
from helpers import TreeCase, git
from dagr import graphcore, runner, runner_lib as rl


class TestGate(TreeCase):
    def test_refuses_without_go(self):
        self.ticket("T01", "out/a.txt")
        rc, out = self.run_slug()
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED: no logged go with a scope in .dagr/maps/m/GO.md", out)
        self.go("go: tester 2026-11-10")   # no scope
        self.assertEqual(self.run_slug()[0], 2)
        self.go("go: tester 2026-11-10 scope: T40-T50")   # matches nothing
        self.assertEqual(self.run_slug()[0], 2)
        self.assertFalse(self.log.exists())
        self.go()
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertIn("TERMINATED", out)

    def test_unknown_map_refused(self):
        out = []
        self.assertEqual(runner.run_slug("nope", self.root, out=out.append), 2)
        self.assertIn("REFUSED", out[0])

    def test_kit_go_format(self):
        self.ticket("T01", "out/a.txt")
        self.go("# GO: m\n\n- approved-by: tester\n- approved-at: x\n- scope: all\n")
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.fm("T01", "status"), "closed")

    def test_dry_run_needs_no_go(self):
        self.ticket("T01", "out/a.txt")
        rc, out = self.run_slug(dry_run=True)
        self.assertEqual(rc, 0)
        self.assertIn("READY (1): T01", out)
        self.assertIn("# Worker brief: T01 (m)", out)
        self.assertFalse(self.log.exists())

    def test_scope_expansion(self):
        ids = ["T08", "T09", "T17", "T22", "T23", "T32a", "T32b", "T55", "T56"]
        self.assertEqual(runner.expand_scope("T08,T09,T17-T22,T25-T55", ids),
                         {"T08", "T09", "T17", "T22", "T32a", "T32b", "T55"})
        self.assertEqual(runner.expand_scope("T32a", ids), {"T32a", "T32b"})

    def test_set_frontmatter_touches_one_line_and_maps_status_words(self):
        self.ticket("T01", "out/a.txt")
        p = self.map / "tickets" / "T01-x.md"
        before = p.read_text().splitlines()
        rl.set_frontmatter(p, "status", "closed")
        after = p.read_text().splitlines()
        self.assertEqual([(a, b) for a, b in zip(before, after) if a != b],
                         [("status: open", "status: closed")])
        t = graphcore.parse_ticket(p)
        rl.set_ticket_fm(t, "status", "running")
        self.assertEqual(self.fm("T01", "status"), "in-progress")
        self.assertEqual(t.status, "running")


class TestRun(TreeCase):
    def test_out_of_scope_never_launches(self):
        self.ticket("T01", "out/a.txt")
        self.ticket("T02", "out/b.txt")
        self.go("go: tester 2026-11-10 scope: T01")
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertEqual(set(self.events()), {"T01"})

    def test_independent_run_in_parallel(self):
        self.ticket("T01", "out/a.txt")
        self.ticket("T02", "out/b.txt")
        self.go()
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.state()["max_concurrency_reached"], 2)
        ev = self.events()
        self.assertLess(ev["T01"]["start"], ev["T02"]["end"])
        self.assertLess(ev["T02"]["start"], ev["T01"]["end"])

    def test_overlapping_affects_serialise(self):
        self.ticket("T01", "out/a.txt")
        self.ticket("T02", "out/a.txt")
        self.go()
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.state()["max_concurrency_reached"], 1)
        ev = self.events()
        self.assertLess(ev["T01"]["end"], ev["T02"]["start"])

    def test_dependency_order_and_artifacts(self):
        self.ticket("T01", "out/a.txt")
        self.ticket("T02", "out/b.txt", blocked="T01")
        self.go()
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        ev = self.events()
        self.assertLess(ev["T01"]["end"], ev["T02"]["start"])
        self.assertEqual(self.fm("T02", "status"), "closed")
        self.assertTrue((self.map / "assets" / "T01" / "receipt.md").is_file())
        self.assertTrue((self.map / "STATUS.md").is_file())
        summ = json.loads((self.map / "assets" / "run-summary.json").read_text())
        self.assertEqual(summ["closed"], ["T01", "T02"])
        self.assertTrue(out.splitlines()[-1].startswith("RUN-SUMMARY "))
        self.assertAlmostEqual(self.state()["tickets"]["T01"]["cost_usd"], 0.25)

    def test_no_receipt_fails_branch(self):
        self.ticket("T01", "out/a.txt")
        self.ticket("T02", "out/b.txt", blocked="T01")
        self.go()
        os.environ["FAKE_MODE"] = "noreceipt"
        rc, out = self.run_slug(strict_exit=True)
        self.assertEqual(rc, 5, out)
        self.assertEqual(self.state()["tickets"]["T01"]["status"], "failed")
        self.assertIn("no receipt written", out)
        self.assertNotIn("T02", self.events())

    def test_stray_write_holds_and_is_not_closed(self):
        self.ticket("T01", "out/a.txt")
        self.go()
        os.environ["FAKE_MODE"] = "stray"
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertIn("STRAY T01: new_outside.txt", out)
        self.assertEqual(self.state()["tickets"]["T01"]["status"], "held")
        self.assertEqual(self.fm("T01", "status"), "blocked")

    def test_rate_limit_backs_off_and_does_not_count_attempt(self):
        self.ticket("T01", "out/a.txt")
        self.go()
        os.environ["FAKE_MODE"] = "rate"
        rc, out = self.run_slug(backoff_scale=0.001, max_rate_retries=1)
        self.assertIn("RATE-LIMIT T01: backing off", out)
        self.assertIn("counting this attempt as a normal failure", out)
        self.assertEqual(self.state()["tickets"]["T01"]["status"], "failed")
        self.assertEqual(len(self.state()["rate_limit_events"]), 1)

    def test_pidfile_refuses_second_runner(self):
        self.ticket("T01", "out/a.txt")
        self.go()
        pf = self.map / "assets" / "runner.pid"
        pf.parent.mkdir(parents=True, exist_ok=True)
        pf.write_text(str(os.getpid()))
        rc, out = self.run_slug()
        self.assertEqual(rc, 3)
        self.assertIn("runner already running", out)

    def test_restart_recovers_running_ticket(self):
        self.ticket("T01", "out/a.txt")
        self.go()
        (self.map / "assets").mkdir()
        (self.map / "state.json").write_text(json.dumps(
            {"version": 1, "map": "m", "tickets": {"T01": {"status": "running", "attempts": 1}}}))
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.fm("T01", "status"), "closed")

    def test_only_one_spawn_site(self):
        src = Path(helpers.ENGINE / "dagr")
        hits = [p.name for p in src.glob("*.py") if "subprocess.Popen(" in p.read_text("utf-8")]
        self.assertEqual(hits, ["runner_lib.py"])

    def test_no_git_means_no_commits_and_files_still_written(self):
        self.ticket("T01", "out/a.txt")
        self.go()
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertTrue((self.root / "out" / "a.txt").is_file())
        self.assertIsNone(self.state()["tickets"]["T01"]["commit"])
        self.assertIn("not a git repo", (self.map / "tickets" / "T01-x.md").read_text())


class TestGit(TreeCase):
    use_git = True

    def test_path_limited_commit(self):
        self.ticket("T01", "out/a.txt")
        self.go()
        self.commit_base()
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        sha = self.state()["tickets"]["T01"]["commit"]
        self.assertTrue(sha)
        files = git(self.root, "show", "--name-only", "--format=", sha).split()
        self.assertIn("out/a.txt", files)
        for f in files:   # only the affects path and this ticket's assets folder
            self.assertTrue(f == "out/a.txt" or f.startswith(".dagr/maps/m/assets/T01/"), f)
        self.assertNotIn("stray.txt", files)
        self.assertIn("stray.txt", git(self.root, "status", "--porcelain"))
        subj = git(self.root, "log", "-1", "--format=%s", sha)
        self.assertTrue(subj.startswith("dagr m/T01:"))

    def test_predirty_affects_hold_without_spending_worker(self):
        (self.root / "out").mkdir()
        (self.root / "out" / "a.txt").write_text("mine, uncommitted\n")
        self.ticket("T01", "out/a.txt")
        self.go()
        self.commit_base()
        rc, out = self.run_slug()
        self.assertIn("HELD T01", out)
        self.assertFalse(self.log.exists())
        self.assertEqual(self.state()["tickets"]["T01"]["status"], "held")
        q = self.map / "questions" / "Q-T01.md"
        self.assertTrue(q.is_file())
        text = q.read_text()
        self.assertIn("out/a.txt", text)          # names the dirty path
        self.assertIn("status: answered", text)   # says how to release
        # commit the file, answer the question: the hold releases and the ticket runs
        git(self.root, "add", "--", "out")
        git(self.root, "commit", "-q", "-m", "mine")
        q.write_text(text.replace("status: open", "status: answered", 1)
                     .replace("(write your answer here)", "committed it"), encoding="utf-8")
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertIn("RELEASE T01", out)
        self.assertEqual(self.fm("T01", "status"), "closed")

    def test_dry_run_prints_worker_argv(self):
        self.ticket("T01", "out/a.txt")
        rc, out = self.run_slug(dry_run=True)
        self.assertIn("ARGV T01:", out)

    def test_never_stages_everything(self):
        src = (helpers.ENGINE / "dagr" / "runner_lib.py").read_text("utf-8")
        self.assertNotIn("add -A", src)
        self.assertNotIn('"-A"', src)
        self.assertNotIn('"--all"', src)

    def test_commit_paths_skip_ignored_and_escaping(self):
        (self.root / ".gitignore").write_text("secret/\n.dagr/\n")
        (self.root / "secret").mkdir()
        (self.root / "secret" / "x").write_text("x")
        (self.root / "ok.txt").write_text("x")
        self.ticket("T01", "secret/x, ok.txt, ../escape.txt, /abs.txt")
        t = graphcore.parse_ticket(self.map / "tickets" / "T01-x.md")
        self.assertEqual(rl.commit_paths(t, self.root, "m"), ["ok.txt"])


if __name__ == "__main__":
    unittest.main()
