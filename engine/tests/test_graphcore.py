import shutil
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401
from dagr import graphcore as gc


def tk(tid, status="open", blocked="", affects="", model="default", needs="none",
       assignee="", extra="", inputs=True):
    fm = (f"---\ntitle: {tid} title\nstatus: {status}\nassignee: {assignee}\n"
          f"blocked-by: [{blocked}]\naffects: [{affects}]\nmodel: {model}\n"
          f"needs_human: {needs}\n{extra}---\n\n## Goal\ng\n")
    return fm + ("\n## Inputs\n- x\n" if inputs else "")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def mk(self, tickets, scope=None, slug="m"):
        d = self.tmp / ".dagr" / "maps" / slug / "tickets"
        d.mkdir(parents=True, exist_ok=True)
        for tid, text in tickets.items():
            (d / f"{tid}-name.md").write_text(text, encoding="utf-8")
        return gc.load_graph(d.parent, scope=scope, root=self.tmp)

    def st(self, **statuses):
        s = gc.new_state("m")
        for tid, v in statuses.items():
            gc.ensure_ticket_record(s, tid)["status"] = v
        return s


class T(Base):
    def test_parse(self):
        p = self.tmp / "T07-x.md"
        p.write_bytes(('﻿---\r\ntitle: "Quoted: title"\r\nblocked-by: [T01, a/T2]\r\n'
                       "affects: [a/**, 'b c']\r\nassignee:\r\nkind: gate\r\n---\r\n"
                       "intro\r\n## Inputs\r\nfile1\r\n## Steps\r\n1. go\r\n").encode("utf-8"))
        t = gc.parse_ticket(p)
        self.assertEqual(t.id, "T07")
        self.assertEqual(t.title, "Quoted: title")
        self.assertEqual(t.blocked_by, ["T01", "a/T2"])
        self.assertEqual(t.affects, ["a/**", "b c"])
        self.assertEqual((t.status, t.needs_human, t.model), ("open", "none", "default"))
        self.assertEqual(t.extra, {"kind": "gate"})
        self.assertEqual(t.sections["Inputs"], "file1")

    def test_status_and_needs_human_vocabulary(self):
        g = self.mk({"T01": tk("T01", status="in-progress"), "T02": tk("T02", status="blocked"),
                     "T03": tk("T03", needs="false"), "T04": tk("T04", needs="true"),
                     "T05": tk("T05", needs="which brand?")})
        self.assertEqual(g["T01"].status, "running")
        self.assertEqual(g["T02"].status, "held")
        self.assertEqual(g["T03"].needs_human, "none")
        self.assertNotEqual(g["T04"].needs_human, "none")
        self.assertEqual(g["T05"].needs_human, "which brand?")

    def test_chain(self):
        g = self.mk({"T01": tk("T01"), "T02": tk("T02", blocked="T01")})
        self.assertEqual(gc.ready(g, self.st()), ["T01"])
        self.assertEqual(gc.ready(g, self.st(T01="closed")), ["T02"])
        self.assertEqual(gc.ready(g, self.st(T01="running")), [])

    def test_needs_human_holds_until_answered(self):
        g = self.mk({"T01": tk("T01", needs="which brand?"), "T02": tk("T02", blocked="T01"),
                     "T03": tk("T03")})
        self.assertEqual(gc.ready(g, self.st()), ["T03"])
        self.assertEqual(gc.held_set(g, self.st()), {"T01", "T02"})
        qd = self.tmp / ".dagr" / "maps" / "m" / "questions"
        qd.mkdir()
        (qd / "Q-T01.md").write_text("---\nstatus: answered\n---\n## Answer\nacme\n")
        self.assertEqual(gc.ready(g, self.st()), ["T01", "T03"])

    def test_affects(self):
        self.assertTrue(gc.affects_overlap(["a/**"], ["a/b.py"]))
        self.assertTrue(gc.affects_overlap(["a\\x.py"], ["a/**"]))
        self.assertTrue(gc.affects_overlap(["a/*.py"], ["a/b.py"]))
        self.assertFalse(gc.affects_overlap(["a/x"], ["b/x"]))
        g = self.mk({"T01": tk("T01", affects="out/a"), "T02": tk("T02", affects="out/a"),
                     "T03": tk("T03", affects="out/b")})
        self.assertEqual(gc.ready(g, self.st()), ["T01", "T03"])

    def test_scope_and_assignee_and_integrator(self):
        g = self.mk({"T01": tk("T01"), "T02": tk("T02"), "T03": tk("T03", model="integrator"),
                     "T04": tk("T04", assignee="runner-1-T04")}, scope={"T01", "T03", "T04"})
        self.assertEqual(gc.ready(g, self.st()), ["T01"])

    def test_cross_map_blocker(self):
        other = self.tmp / ".dagr" / "maps" / "o" / "tickets"
        other.mkdir(parents=True)
        (other / "T01-x.md").write_text(tk("T01", status="closed"))
        g = self.mk({"T01": tk("T01", blocked="o/T01"), "T02": tk("T02", blocked="o/T09")})
        self.assertEqual(gc.ready(g, self.st()), ["T01"])
        self.assertIn("T02: unknown blocker o/T09", gc.validate(g))

    def test_validate_cycle_and_inputs(self):
        g = self.mk({"T01": tk("T01", blocked="T02"), "T02": tk("T02", blocked="T01"),
                     "T03": tk("T03", inputs=False)})
        msgs = gc.validate(g)
        self.assertTrue(any(m.startswith("dependency cycle") for m in msgs))
        self.assertIn("T03: no ## Inputs section", msgs)

    def test_terminated(self):
        g = self.mk({"T01": tk("T01"), "T02": tk("T02", blocked="T01")})
        self.assertEqual(gc.terminated(g, self.st(T01="closed", T02="closed")),
                         (True, "all-closed"))
        self.assertEqual(gc.terminated(g, self.st(T01="running")), (False, "work-remains"))
        self.assertEqual(gc.terminated(g, self.st(T01="failed"))[0], True)
        g2 = self.mk({"T09": tk("T09", needs="q")}, slug="n")
        self.assertEqual(gc.terminated(g2, gc.new_state("n"))[0], True)

    def test_state_io_atomic_and_reconcile(self):
        p = self.tmp / "s.json"
        s = gc.new_state("m")
        gc.ensure_ticket_record(s, "T01")["status"] = "running"
        gc.save_state(p, s)
        self.assertFalse(Path(str(p) + ".tmp").exists())
        s2 = gc.load_state(p)
        self.assertEqual(gc.reconcile_on_start(None, s2), ["T01"])
        self.assertEqual(s2["tickets"]["T01"]["status"], "open")


if __name__ == "__main__":
    unittest.main()
