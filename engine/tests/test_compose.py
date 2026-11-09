import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import TreeCase
from dagr import cli, compose, config, contracts, planner

REPO = Path(__file__).resolve().parents[2]
AFTER = REPO / "examples" / "after"


def w(root, rel, text=""):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


def contract(root, rel, id_, consumes, produces, extra="", body="# T\n\nDoes a thing.\n"):
    w(root, rel, f"---\nid: {id_}\nconsumes: [{', '.join(consumes)}]\n"
                 f"produces: [{', '.join(produces)}]\n{extra}---\n{body}")


def run_cli(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(list(argv))
    return rc, buf.getvalue()


class Tree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        contract(self.root, "workflows/video-script/CONTEXT.md", "video-script", ["topic-brief"],
                 ["script-draft"], body="# Video script\n\nTurns a topic into a spoken script.\n")
        w(self.root, "workflows/video-script/stages/01-hook/CONTEXT.md", "# hook\n")
        w(self.root, "workflows/video-script/stages/02-script/CONTEXT.md", "# script\n")
        contract(self.root, "workflows/newsletter/CONTEXT.md", "newsletter", ["script-draft"],
                 ["newsletter-draft"], body="# Newsletter\n\nWeekly email after the video.\n")
        w(self.root, "workflows/newsletter/stages/01-draft/CONTEXT.md", "# draft\n")
        self.cfg = config.load_config(self.root)


class TestDiscovery(Tree):
    def test_finds_contracts_anywhere_and_skips_junk(self):
        contract(self.root, "deep/er/area/CONTEXT.md", "deep-one", [], ["x"])
        contract(self.root, "node_modules/p/CONTEXT.md", "junk", [], ["y"])
        contract(self.root, "workflows/newsletter/output/CONTEXT.md", "junk2", [], ["y"])
        u, issues = contracts.discover(self.root)
        self.assertEqual(sorted(u), ["deep-one", "newsletter", "video-script"])
        self.assertEqual(issues, [])

    def test_readme_only_counts_with_stage_folders(self):
        w(self.root, "ops/README.md", "---\nid: ops\nproduces: [a]\n---\n")
        self.assertNotIn("ops", contracts.discover(self.root)[0])
        w(self.root, "ops/01-first/CONTEXT.md", "x")
        self.assertIn("ops", contracts.discover(self.root)[0])

    def test_frontmatter_shapes_bom_crlf_extra_keys(self):
        w(self.root, "a/CONTEXT.md",
          "﻿---\r\nid: a\r\nconsumes:\r\n  - one\r\n  - two?\r\nproduces: [three, 'four']\r\n"
          "color: red\r\n# a comment\r\ntags: [x,\r\n  y]\r\n---\r\n# A\r\n")
        u = contracts.discover(self.root)[0]["a"]
        self.assertEqual(u.consumes, ["one", "two?"])
        self.assertEqual(u.produces, ["three", "four"])
        self.assertEqual(u.required_ports(), ["one"])

    def test_config_workflow_glob_and_contract_name(self):
        w(self.root, "flows/x/PLAYBOOK.md", "---\nid: playbook-x\nproduces: [p]\n---\n")
        u, _ = contracts.discover(self.root, {"workflow_glob": "flows/*/",
                                              "contract_name": "PLAYBOOK.md"})
        self.assertIn("playbook-x", u)
        self.assertIn("newsletter", u)   # auto-discovery still runs

    def test_description_first_paragraph(self):
        u = contracts.discover(self.root)[0]["video-script"]
        self.assertEqual(u.description(), "Turns a topic into a spoken script.")


class TestPortsDoctor(Tree):
    def test_ports_report(self):
        contract(self.root, "workflows/c/CONTEXT.md", "c", ["script-draftt", "nothing-like-it"], [])
        u, _ = contracts.discover(self.root)
        rep = compose.ports_report(u, {})
        self.assertIn({"from": "video-script", "port": "script-draft", "to": "newsletter"},
                      rep["wiring"])
        ub = {x["port"] for x in rep["unbound_inputs"]}
        self.assertEqual(ub, {"topic-brief", "script-draftt", "nothing-like-it"})
        self.assertEqual([m["nearest_produced"] for m in rep["mismatches"]], ["script-draft"])
        self.assertIn("newsletter-draft", [d["port"] for d in rep["dangling_outputs"]])

    def test_doctor_clean_then_problems(self):
        self.assertEqual(compose.doctor_report(self.root, self.cfg), [])
        w(self.root, "bad/CONTEXT.md", "---\nid: bad\nconsumes: [a\nproduces: [b]\n---\n")
        contract(self.root, "dup/CONTEXT.md", "newsletter", [], ["z"])
        w(self.root, "half/CONTEXT.md", "---\nid: half\n---\n")
        msgs = [m for _l, m in compose.doctor_report(self.root, self.cfg)]
        self.assertTrue(any("bad/CONTEXT.md" in m and "frontmatter-error" in m for m in msgs))
        self.assertTrue(any("duplicate-id" in m for m in msgs))
        self.assertTrue(any("half-declared" in m for m in msgs))

    def test_doctor_cycle_and_exit_code(self):
        contract(self.root, "workflows/a/CONTEXT.md", "a", ["pb"], ["pa"])
        contract(self.root, "workflows/b/CONTEXT.md", "b", ["pa"], ["pb"])
        rep = compose.doctor_report(self.root, self.cfg)
        self.assertTrue(any("dependency cycle" in m for _l, m in rep))
        rc, out = run_cli("doctor", "--root", str(self.root))
        self.assertEqual(rc, 1)
        self.assertIn("dependency cycle", out)

    def test_doctor_config_drift(self):
        cfg = dict(self.cfg, workflows_root="nope", knowledge_dirs=["missing"])
        msgs = [m for _l, m in compose.doctor_report(self.root, cfg)]
        self.assertTrue(any("workflows_root" in m for m in msgs))
        self.assertTrue(any("knowledge_dirs" in m for m in msgs))


class TestPlanner(unittest.TestCase):
    def test_extract_and_parse_reply(self):
        self.assertEqual(planner.extract_json_object('sure!\n```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(planner.PlannerError):
            planner.extract_json_object("no json")

    def test_keyword_plan_stems_and_gaps(self):
        t = Tree()
        t.setUp()
        u = contracts.discover(t.root)[0]
        p = planner.keyword_plan("write the scripts for episode one and a newsletter", u)
        self.assertEqual(p["workflows"], ["newsletter", "video-script"])
        none = planner.keyword_plan("zzz qqq", u)
        self.assertEqual(none["workflows"], [])
        self.assertTrue(none["gaps"])
        t.tmp.cleanup()

    def test_non_english_tokens(self):
        self.assertEqual(planner.tokens("Écrire le boletín"), {"écrire", "le", "boletín"})


class TestPlan(Tree):
    def plan(self, request, **kw):
        out = []
        rc = compose.plan_request(self.root, self.cfg, request, out=out.append, **kw)
        return rc, "\n".join(out)

    def tickets(self, slug):
        d = self.root / ".dagr" / "maps" / slug / "tickets"
        return sorted(p.name for p in d.glob("T*.md"))

    def test_bare_workflow_id_pulls_in_producer_via_ports(self):
        rc, out = self.plan("newsletter", slug="a")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.tickets("a"), ["T01-video-script.md", "T02-newsletter.md"])
        t2 = (self.root / ".dagr/maps/a/tickets/T02-newsletter.md").read_text()
        self.assertIn("blocked-by: [T01]", t2)
        self.assertIn("model: default", t2)
        self.assertIn("needs_human: false", t2)
        self.assertIn("## Inputs", t2)
        self.assertIn("workflows/newsletter/CONTEXT.md", t2)
        self.assertIn("affects: [workflows/newsletter/output/]", t2)
        self.assertIn("workflow id `newsletter`", (self.root / ".dagr/maps/a/map.md").read_text())

    def test_ledger_satisfies_producers(self):
        compose.append_ledger(self.root, [{"port": "script-draft", "path": "x", "by": "me",
                                           "map": "-", "date": "2026-01-01"}])
        rc, out = self.plan("newsletter", slug="b")
        self.assertEqual(self.tickets("b"), ["T01-newsletter.md"])

    def test_free_text_keyword_fallback_is_stated_in_map(self):
        os.environ["DAGR_NO_MODEL"] = "1"
        self.addCleanup(os.environ.pop, "DAGR_NO_MODEL", None)
        rc, out = self.plan("make the video script and then the newsletter", slug="c")
        self.assertEqual(rc, 0, out)
        m = (self.root / ".dagr/maps/c/map.md").read_text()
        self.assertIn("planner: keyword fallback", m)
        self.assertIn("No model was used", m)
        self.assertEqual(len(self.tickets("c")), 2)

    def test_no_binary_falls_back_too(self):
        saved = {k: os.environ.pop(k, None) for k in ("DAGR_WORKER_BIN", "CLAUDE_BIN")}
        self.addCleanup(lambda: [os.environ.__setitem__(k, v) for k, v in saved.items() if v])
        cfg = config.load_config(self.root)
        cfg["workers"]["claude"]["argv"][0] = "no-such-agent-binary-xyz"
        out = []
        rc = compose.plan_request(self.root, cfg, "newsletter please", slug="d", out=out.append)
        self.assertEqual(rc, 0)
        self.assertIn("not found", (self.root / ".dagr/maps/d/map.md").read_text())

    def test_model_planner_used_when_available(self):
        plan = {"goal": "Ship it", "target_ports": ["newsletter-draft"], "workflows": [],
                "gaps": []}
        rc, out = self.plan("ship the thing", slug="e", model_fn=lambda text: json.dumps(plan))
        self.assertEqual(rc, 0, out)
        m = (self.root / ".dagr/maps/e/map.md").read_text()
        self.assertIn("planner: model planner", m)
        self.assertEqual(len(self.tickets("e")), 2)   # target port -> producer + its producer

    def test_model_planner_via_fake_worker_binary(self):
        # reuse the fake agent as the planner worker
        fake = self.root.parent / "fake_plan_agent.py"
        fake.write_text(helpers.FAKE, encoding="utf-8")
        os.environ["DAGR_WORKER_BIN"] = '"%s" "%s"' % (helpers.sys.executable.replace("\\", "/"),
                                                        str(fake).replace("\\", "/"))
        os.environ["FAKE_PLAN"] = json.dumps({"goal": "g", "target_ports": [],
                                              "workflows": ["video-script"], "gaps": []})
        self.addCleanup(os.environ.pop, "DAGR_WORKER_BIN", None)
        self.addCleanup(os.environ.pop, "FAKE_PLAN", None)
        rc, out = self.plan("anything at all", slug="f")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.tickets("f"), ["T01-video-script.md"])
        self.assertIn("model planner (worker `claude`)", (self.root / ".dagr/maps/f/map.md").read_text())
        self.assertIn("plan: calling claude as planner (may cost money); use --no-model to avoid", out)

    def test_unmatched_request_names_the_workflows(self):
        rc, out = self.plan("zzz qqq", slug="g", use_model=False)
        self.assertEqual(rc, 2)
        self.assertIn("newsletter", out)

    def test_expand_stages_chains_tickets(self):
        rc, out = self.plan("video-script", slug="h", expand_stages=True)
        self.assertEqual(self.tickets("h"), ["T01-video-script-01-hook.md",
                                             "T02-video-script-02-script.md"])
        self.assertIn("blocked-by: [T01]",
                      (self.root / ".dagr/maps/h/tickets/T02-video-script-02-script.md").read_text())

    def test_prerequisite_condition_becomes_human_question_ticket(self):
        contract(self.root, "workflows/pub/CONTEXT.md", "pub", [], ["published"],
                 extra="prerequisites: [condition:legal-signoff]\n")
        rc, out = self.plan("pub", slug="i")
        self.assertEqual(rc, 0, out)
        t = (self.root / ".dagr/maps/i/tickets/T01-legal-signoff.md").read_text()
        self.assertIn("needs_human: `legal-signoff` is not something", t)

    def test_cycle_is_reported(self):
        contract(self.root, "workflows/a/CONTEXT.md", "a", ["pb"], ["pa"])
        contract(self.root, "workflows/b/CONTEXT.md", "b", ["pa"], ["pb"])
        rc, out = self.plan("a", slug="j")
        self.assertEqual(rc, 3)
        self.assertIn("cycle", out)

    def test_also_repeats_a_workflow_as_instances(self):
        rc, out = self.plan("video-script", slug="inst", use_model=False,
                            also=["video-script", "video-script"])
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.tickets("inst"), ["T01-video-script.md", "T02-video-script-2.md",
                                                "T03-video-script-3.md"])
        t2 = (self.root / ".dagr/maps/inst/tickets/T02-video-script-2.md").read_text()
        self.assertIn("blocked-by: [T01]", t2)
        self.assertIn("run-2/", t2)   # its own output folder, not the first instance's
        self.assertIn("(instance 2)", t2)

    def test_also_adds_another_workflow_and_rejects_unknown(self):
        rc, out = self.plan("video-script", slug="alsoone", use_model=False, also=["newsletter"])
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.tickets("alsoone")), 2)
        rc, out = self.plan("video-script", slug="alsobad", use_model=False, also=["nope"])
        self.assertEqual(rc, 2)

    def test_model_call_is_announced_and_no_model_is_silent(self):
        rc, out = self.plan("video-script", slug="q1", use_model=False)
        self.assertNotIn("may cost money", out)
        self.assertIn("planner: workflow id", (self.root / ".dagr/maps/q1/map.md").read_text())

    def test_existing_map_is_not_overwritten(self):
        self.plan("newsletter", slug="k")
        rc, out = self.plan("newsletter", slug="k")
        self.assertEqual(rc, 2)

    def test_go_writes_gate_and_validates_scope(self):
        self.plan("newsletter", slug="l")
        out = []
        self.assertEqual(compose.cmd_go(self.root, self.cfg, "l", "T09", "ann", out.append), 2)
        self.assertEqual(compose.cmd_go(self.root, self.cfg, "l", "T01", "ann smith", out.append), 0)
        go = (self.root / ".dagr/maps/l/GO.md").read_text()
        self.assertIn("approved-by: ann-smith", go)
        self.assertIn("scope: T01", go)
        from dagr import runner
        scope, err = runner.read_go(self.root / ".dagr/maps/l", ["T01", "T02"])
        self.assertEqual((scope, err), ({"T01"}, None))
        self.assertEqual(compose.cmd_go(self.root, self.cfg, "nope", None, None, out.append), 2)


class TestEndToEnd(Tree):
    def test_plan_go_run_with_fake_worker(self):
        fake = self.root.parent / "fake_e2e.py"
        fake.write_text(helpers.FAKE, encoding="utf-8")
        os.environ["DAGR_WORKER_BIN"] = '"%s" "%s"' % (helpers.sys.executable.replace("\\", "/"),
                                                        str(fake).replace("\\", "/"))
        os.environ["FAKE_SLEEP"] = "0.1"
        self.addCleanup(os.environ.pop, "DAGR_WORKER_BIN", None)
        self.addCleanup(os.environ.pop, "FAKE_SLEEP", None)
        self.assertEqual(run_cli("plan", "newsletter", "--root", str(self.root), "--map", "e2e")[0], 0)
        rc, out = run_cli("run", "e2e", "--root", str(self.root), "--no-review", "--poll", "0.05")
        self.assertEqual(rc, 2)   # refused: no go yet
        self.assertIn("REFUSED", out)
        self.assertEqual(run_cli("go", "e2e", "--root", str(self.root), "--who", "tester")[0], 0)
        rc, out = run_cli("run", "e2e", "--root", str(self.root), "--no-review", "--poll", "0.05")
        self.assertEqual(rc, 0, out)
        self.assertIn("CLOSED T01", out)
        self.assertTrue((self.root / "workflows/newsletter/output/out.txt").is_file())
        rc, out = run_cli("status", "e2e", "--root", str(self.root))
        self.assertIn("closed 2/2", out)

    def test_root_found_by_walking_up_from_cwd(self):
        (self.root / ".dagr").mkdir()
        sub = self.root / "workflows" / "newsletter"
        old = os.getcwd()
        os.chdir(sub)
        self.addCleanup(os.chdir, old)
        self.assertEqual(config.find_root().resolve(), self.root.resolve())
        rc, out = run_cli("doctor")
        self.assertIn("2 contract(s) found", out)


@unittest.skipUnless((AFTER / ".dagr").is_dir(), "examples/after not present")
class TestDoctorEmpty(unittest.TestCase):
    def test_zero_contracts_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = run_cli("doctor", "--root", d)
            self.assertEqual(rc, 0)
            self.assertIn("no contracts yet (expected before setup apply)", out)


@unittest.skipUnless((AFTER / ".dagr").is_dir(), "examples/after not present")
class TestKitExample(unittest.TestCase):
    def test_doctor_and_ports_run_clean(self):
        rc, out = run_cli("doctor", "--root", str(AFTER))
        self.assertEqual(rc, 0, out)
        self.assertIn("0 error(s)", out)
        rc, out = run_cli("ports", "--root", str(AFTER))
        self.assertEqual(rc, 0)
        self.assertIn("video-script --script-draft--> newsletter", out)

    def test_launch_week_request_resolves(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / "after"
            shutil.copytree(AFTER, dst)
            shutil.rmtree(dst / ".dagr" / "maps")
            rc, out = run_cli("plan", "Prepare launch week: scripts for episodes 1 and 2, a teaser "
                              "newsletter after episode 1, and a recap newsletter after both.",
                              "--root", str(dst), "--map", "launch-week", "--no-model")
            self.assertEqual(rc, 0, out)
            names = sorted(p.name for p in (dst / ".dagr/maps/launch-week/tickets").glob("T*.md"))
            self.assertEqual(names, ["T01-video-script.md", "T02-newsletter.md"])

    def test_example_ticket_files_parse_and_dry_run(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / "after"
            shutil.copytree(AFTER, dst)
            rc, out = run_cli("run", "launch-week", "--root", str(dst), "--dry-run")
            self.assertEqual(rc, 0, out)
            self.assertIn("READY (2): T01, T02", out)


if __name__ == "__main__":
    unittest.main()
