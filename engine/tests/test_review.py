import json
import os
import unittest

import helpers
from helpers import TreeCase
from dagr import reviewer, runner_lib as rl, config


class TestVerdictParsing(unittest.TestCase):
    def test_parse_and_threshold(self):
        v = reviewer.parse_verdict("blah\nscore: 0.85\ndiscrepancies:\n- a\nnotes:\nfix")
        self.assertEqual(v["score"], 0.85)
        self.assertEqual(v["discrepancies"], "- a")
        self.assertEqual(v["notes"], "fix")
        self.assertTrue(reviewer.passes(0.8))
        self.assertFalse(reviewer.passes(0.79))
        self.assertFalse(reviewer.passes(None))
        self.assertFalse(reviewer.passes(float("nan")))
        self.assertEqual(reviewer.parse_verdict("score: pass")["score"], 1.0)
        self.assertIsNone(reviewer.parse_verdict("no score here")["score"])

    def test_tail_verdict_uses_last_score(self):
        t = "score: 0.2\nlater thoughts\nscore: 0.9\nnotes:\nok"
        self.assertEqual(reviewer.parse_verdict(reviewer._tail_verdict(t))["score"], 0.9)

    def test_visual_detection_and_acceptance_section(self):
        self.assertTrue(reviewer.is_visual("---\ntype: prototype\naffects: [a.html]\n---\n"))
        self.assertFalse(reviewer.is_visual("---\nvisual: false\n---\n## Definition of done\nscreenshot\n"))
        self.assertTrue(reviewer.is_visual("---\n---\n## Acceptance\nrender it\n"))

    def test_brief_has_no_write_permission_text_and_caps_diff(self):
        b = reviewer.build_review_brief("## Goal\ng\n", "dod", "x" * 70000, "rcpt", False, [])
        self.assertIn("diff truncated", b)
        self.assertIn("you must not change any file", b)


class TestReviewLoop(TreeCase):
    def run_reviewed(self, scores, **kw):
        os.environ["FAKE_SCORES"] = scores
        os.environ["FAKE_STATE"] = str(self.base / "review_count")
        self.ticket("T01", "out/a.txt")
        self.go()
        return self.run_slug(no_review=False, **kw)

    def test_pass_first_time(self):
        rc, out = self.run_reviewed("0.95")
        self.assertEqual(rc, 0, out)
        rec = self.state()["tickets"]["T01"]
        self.assertEqual(rec["status"], "closed")
        self.assertEqual(rec["reviewer_score"], 0.95)
        self.assertEqual(rec["attempts"], 1)
        self.assertTrue((self.map / "assets" / "T01" / "verdict-1.md").is_file())
        self.assertAlmostEqual(rec["cost_usd"], 0.35)   # worker 0.25 + reviewer 0.10

    def test_review_status_is_on_disk_while_reviewer_runs(self):
        from unittest import mock
        from dagr import review_step
        seen = []
        orig = review_step.review_and_decide

        def spy(t, *a, **k):
            seen.append(self.fm("T01", "status"))
            return orig(t, *a, **k)
        with mock.patch.object(review_step, "review_and_decide", spy):
            rc, out = self.run_reviewed("0.95")
        self.assertEqual(seen, ["review"])
        self.assertEqual(self.fm("T01", "status"), "closed")

    def test_retry_with_notes_then_pass(self):
        rc, out = self.run_reviewed("0.5,0.9")
        self.assertEqual(rc, 0, out)
        rec = self.state()["tickets"]["T01"]
        self.assertEqual((rec["status"], rec["attempts"]), ("closed", 2))
        self.assertEqual(rec["scores"], [0.5, 0.9])
        self.assertIn("RETRY T01", out)
        brief = (self.map / "assets" / "T01" / "brief.md").read_text()
        self.assertIn("Reviewer notes from your last attempt", brief)
        self.assertIn("fix the thing", brief)

    def test_three_failures_fail_the_node(self):
        rc, out = self.run_reviewed("0.1,0.2,0.3")
        rec = self.state()["tickets"]["T01"]
        self.assertEqual((rec["status"], rec["attempts"]), ("failed", 3))
        self.assertTrue(rec["replan_needed"])
        self.assertTrue((self.map / "assets" / "T01" / "FAILED.md").is_file())

    def test_unparseable_reviewer_never_auto_passes(self):
        rc, out = self.run_reviewed("garbage")
        rec = self.state()["tickets"]["T01"]
        self.assertEqual(rec["status"], "failed")
        self.assertTrue(rec["reviewer_unavailable"])
        self.assertIsNone(rec["reviewer_score"])

    def test_reviewer_writing_outside_assets_fails(self):
        os.environ["FAKE_REVIEWER_STRAY"] = "1"
        rc, out = self.run_reviewed("0.95")
        rec = self.state()["tickets"]["T01"]
        self.assertEqual(rec["status"], "failed")
        self.assertIn("reviewer_wrote.txt", rec["reviewer_stray_paths"])

    def test_pass_threshold_comes_from_config(self):
        (self.root / ".dagr" / "config.json").write_text(json.dumps({"pass_threshold": 0.95}))
        rc, out = self.run_reviewed("0.9,0.96")
        rec = self.state()["tickets"]["T01"]
        self.assertEqual((rec["status"], rec["attempts"]), ("closed", 2))


class TestPluggableWorkers(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in ("DAGR_WORKER_BIN", "CLAUDE_BIN")}
        os.environ["DAGR_WORKER_BIN"] = helpers.sys.executable
        os.environ.pop("CLAUDE_BIN", None)
        self.addCleanup(self.restore)

    def restore(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def argv(self, name, **kw):
        cfg = config.load_config(".")
        w = config.worker_cfg(cfg, name)
        return rl.build_argv(w, brief_file="/b/brief.md", cwd="/c", **kw)

    def test_claude_template(self):
        argv, feed = self.argv("claude", model="sonnet", allowed_tools=["Read"],
                               disallowed_tools=["Write"])
        self.assertTrue(feed)
        self.assertEqual(argv[1:3], ["-p", "--output-format"])
        self.assertIn("--allowedTools", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "Read")
        self.assertIn("--disallowedTools", argv)

    def test_codex_template(self):
        argv, feed = self.argv("codex", model="")
        self.assertEqual(argv[1:4], ["exec", "--sandbox", "workspace-write"])
        self.assertEqual(argv[-1], "-")
        self.assertNotIn("--model", argv)
        self.assertTrue(feed)
        argv, _ = self.argv("codex", model="gpt-x")
        self.assertEqual(argv[argv.index("--model") + 1], "gpt-x")

    def test_opencode_template_passes_brief_by_path(self):
        argv, feed = self.argv("opencode")
        self.assertEqual(argv[1], "run")
        self.assertIn("/b/brief.md", argv)
        self.assertFalse(feed)

    def test_custom_template_placeholders(self):
        cfg = config.load_config(".")
        cfg["workers"]["custom"]["command"] = "myagent --brief {brief_file} --dir {cwd}"
        w = config.worker_cfg(cfg, "custom")
        argv, feed = rl.build_argv(w, brief_file="/b/x y.md", cwd="/c")
        self.assertEqual(argv[1:], ["--brief", "/b/x y.md", "--dir", "/c"])
        self.assertFalse(feed)

    def test_missing_binary_is_a_plain_error(self):
        del os.environ["DAGR_WORKER_BIN"]
        cfg = config.load_config(".")
        cfg["workers"]["custom"]["command"] = "definitely-not-installed-xyz {brief_file}"
        with self.assertRaises(FileNotFoundError):
            rl.build_argv(config.worker_cfg(cfg, "custom"), brief_file="b")

    def test_kit_config_notes_do_not_break_templates(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".dagr").mkdir()
            (Path(d) / ".dagr" / "config.json").write_text(json.dumps({
                "root": ".", "workers": {"claude": "(engine default, unchanged)", "custom": ""}}))
            cfg = config.load_config(d)
            self.assertIsInstance(cfg["workers"]["claude"], dict)
            self.assertEqual(config.worker_cfg(cfg)["_name"], "claude")


class TestPluggableReviewer(TreeCase):
    def test_reviewer_can_be_a_different_worker_with_text_output(self):
        # the reviewer uses a `custom` template whose stdout is plain text (no JSON)
        fake = str(self.fake).replace("\\", "/")
        py = helpers.sys.executable.replace("\\", "/")
        scorer = self.base / "scorer.py"
        scorer.write_text("import sys\nsys.stdin.read()\nprint('score: 0.91\\nnotes:\\nfine')\n")
        cfg = {"reviewer": {"worker": "custom"},
               "workers": {"custom": {"command": f'"{py}" "{str(scorer).replace(chr(92), "/")}"',
                                      "stdin": "brief", "output": "text"}}}
        (self.root / ".dagr" / "config.json").write_text(json.dumps(cfg))
        os.environ["DAGR_CUSTOM_BIN"] = ""   # no override for custom
        os.environ.pop("DAGR_CUSTOM_BIN")
        self.ticket("T01", "out/a.txt")
        self.go()
        # DAGR_WORKER_BIN would also override the custom template; scope it to claude only
        worker_bin = os.environ.pop("DAGR_WORKER_BIN")
        os.environ["DAGR_CLAUDE_BIN"] = worker_bin
        self.addCleanup(os.environ.pop, "DAGR_CLAUDE_BIN", None)
        rc, out = self.run_slug(no_review=False)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.state()["tickets"]["T01"]["reviewer_score"], 0.91)


if __name__ == "__main__":
    unittest.main()
