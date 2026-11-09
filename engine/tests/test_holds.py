import os
import unittest

import helpers
from helpers import TreeCase
from dagr import graphcore, holds


class TestQuestionsHolds(TreeCase):
    def qfile(self):
        return self.map / "questions" / "Q-T01.md"

    def test_needs_human_writes_question_file_and_holds_branch_only(self):
        self.ticket("T01", "out/a.txt", needs="Which brand name should the copy use?")
        self.ticket("T02", "out/b.txt", blocked="T01")
        self.ticket("T03", "out/c.txt")
        self.go()
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertIn("HOLD T01: question filed at .dagr/maps/m/questions/Q-T01.md", out)
        self.assertEqual(set(self.events()), {"T03"})   # the independent ticket still ran
        st = self.state()["tickets"]
        self.assertEqual(st["T01"]["status"], "held")
        self.assertEqual(st["T02"]["status"], "held")
        self.assertEqual(st["T03"]["status"], "closed")
        q = self.qfile().read_text()
        self.assertIn("status: open", q)
        self.assertIn("Which brand name should the copy use?", q)
        self.assertIn("Blocks: T01, T02", q)
        self.assertIn("ON HOLD T01 -> questions/Q-T01.md", out)
        self.assertIn("ON HOLD (waiting on you)", (self.map / "STATUS.md").read_text())

    def test_answering_releases_and_records_the_answer(self):
        self.ticket("T01", "out/a.txt", needs="Which brand name?")
        self.ticket("T02", "out/b.txt", blocked="T01")
        self.go()
        self.run_slug()
        self.assertEqual(self.state()["tickets"]["T02"]["status"], "held")
        text = self.qfile().read_text().replace("status: open", "status: answered")
        text = text.replace(holds.PLACEHOLDER, "Use Acme Corp.")
        self.qfile().write_text(text)
        os.environ.pop("FAKE_LOG", None)
        rc, out = self.run_slug()
        self.assertEqual(rc, 0, out)
        self.assertIn("RELEASE T01: question answered", out)
        st = self.state()["tickets"]
        self.assertEqual((st["T01"]["status"], st["T02"]["status"]), ("closed", "closed"))
        self.assertEqual(self.fm("T01", "needs_human"), "none")
        t = (self.map / "tickets" / "T01-x.md").read_text()
        self.assertIn("## Human answer", t)
        self.assertIn("Use Acme Corp.", t)
        self.assertIn("Use Acme Corp.", (self.map / "assets" / "T01" / "brief.md").read_text())

    def test_unedited_placeholder_does_not_release(self):
        self.ticket("T01", "out/a.txt", needs="q?")
        self.go()
        self.run_slug()
        rc, out = self.run_slug()
        self.assertNotIn("RELEASE", out)
        self.assertEqual(self.state()["tickets"]["T01"]["status"], "held")

    def test_dropped_question_fails_ticket_for_replan(self):
        self.ticket("T01", "out/a.txt", needs="q?")
        self.ticket("T02", "out/b.txt", blocked="T01")
        self.go()
        self.run_slug()
        self.qfile().write_text(self.qfile().read_text().replace("status: open", "status: dropped"))
        rc, out = self.run_slug()
        rec = self.state()["tickets"]["T01"]
        self.assertEqual(rec["status"], "failed")
        self.assertTrue(rec["replan_needed"])
        self.assertIn("replan_needed", (self.map / "tickets" / "T01-x.md").read_text())

    def test_needs_human_true_uses_question_section(self):
        self.ticket("T01", "out/a.txt", needs="true")
        p = self.map / "tickets" / "T01-x.md"
        p.write_text(p.read_text().replace("## Resolution", "## Question\n\nPick a colour.\n\n## Resolution"))
        self.go()
        self.run_slug()
        self.assertIn("Pick a colour.", self.qfile().read_text())

    def test_question_file_is_idempotent(self):
        self.ticket("T01", "out/a.txt", needs="q?")
        g = graphcore.load_graph(self.map, root=self.root)
        p1 = holds.write_question(g["T01"], "m", self.map, g)
        p1.write_text(p1.read_text() + "\nhuman notes\n")
        holds.write_question(g["T01"], "m", self.map, g)
        self.assertIn("human notes", p1.read_text())

    def test_parse_question_strips_comment_placeholder(self):
        self.ticket("T01", "out/a.txt", needs="q?")
        g = graphcore.load_graph(self.map, root=self.root)
        p = holds.write_question(g["T01"], "m", self.map, g)
        st, ans = holds.parse_question(p)
        self.assertEqual(st, "open")
        self.assertEqual(ans, "(answered with no text)")


if __name__ == "__main__":
    unittest.main()
