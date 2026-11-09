import shutil
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401
from dagr import apply as ap, cli, scaffold

REPO = Path(__file__).resolve().parents[2]
BEFORE, AFTER = REPO / "examples" / "before", REPO / "examples" / "after"


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


def proposal(*items):
    return "# dagr proposal\n\n## Items\n\n" + "\n".join(items)


def item(n, action, path, diff):
    return (f"### {n}. {action}: {path}\n\n- file: {path}\n- action: {action}\n- confidence: high\n"
            f"- risk: low\n\nWhy: test\n\n```diff\n{diff}```\n")


class TestApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "t"
        self.root.mkdir()
        (self.root / ".dagr").mkdir()

    def w(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def prop(self, *items):
        (self.root / ".dagr" / "PROPOSAL.md").write_text(proposal(*items), encoding="utf-8")

    def apply(self, items="all", dry=False):
        out = []
        rc = ap.run_apply(self.root, items, dry, out=out.append)
        return rc, "\n".join(out)

    def test_round_trip_example_is_byte_identical(self):
        shutil.copytree(BEFORE, self.root, dirs_exist_ok=True)
        before = tree_bytes(self.root)
        self.assertEqual(cli.main(["scan", "--root", str(self.root)]), 0)
        shutil.copy(AFTER / ".dagr" / "PROPOSAL.md", self.root / ".dagr" / "PROPOSAL.md")
        rc, out = self.apply(dry=True)
        self.assertEqual(rc, 0, out)
        self.assertFalse((self.root / ".dagr" / "backup").exists())
        rc, out = self.apply()
        self.assertEqual(rc, 0, out)
        self.assertIn("id: video-script",
                      (self.root / "workflows/video-script/CONTEXT.md").read_text("utf-8"))
        man = next((self.root / ".dagr" / "backup").iterdir()) / "MANIFEST.md"
        self.assertIn("item 1  .dagr/config.json  new", man.read_text())
        self.assertIn("item 14  CLAUDE.md  existing", man.read_text())
        # second run: nothing changes, no new backup folder
        n_backups = len(list((self.root / ".dagr" / "backup").iterdir()))
        rc, out = self.apply()
        self.assertEqual(rc, 0, out)
        self.assertIn("16 already applied", out)
        self.assertEqual(len(list((self.root / ".dagr" / "backup").iterdir())), n_backups)
        self.assertEqual(scaffold.uninstall(self.root, yes=True, out=lambda s: None), 0)
        self.assertEqual(tree_bytes(self.root), before)

    def test_refuses_whole_run_when_a_diff_does_not_apply(self):
        self.w("a.md", b"# A\n\nbody\n")
        self.w("b.md", b"# B\n\nbody\n")
        good = "--- a/a.md\n+++ b/a.md\n@@ -1,3 +1,4 @@\n+x: 1\n # A\n \n body\n"
        bad = "--- a/b.md\n+++ b/b.md\n@@ -1,3 +1,4 @@\n+x: 1\n # NOT B\n \n body\n"
        self.prop(item(1, "add-frontmatter", "a.md", good),
                  item(2, "add-frontmatter", "b.md", bad))
        rc, out = self.apply()
        self.assertEqual(rc, 2)
        self.assertIn("item 2", out)
        self.assertEqual((self.root / "a.md").read_bytes(), b"# A\n\nbody\n")   # nothing written
        self.assertFalse((self.root / ".dagr" / "backup").exists())

    def test_crlf_and_bom_preserved(self):
        self.w("c.md", b"\xef\xbb\xbf# C\r\n\r\ntext\r\n")
        diff = "--- a/c.md\n+++ b/c.md\n@@ -1,3 +1,6 @@\n+---\n+id: c\n+---\n # C\n \n text\n"
        self.prop(item(1, "add-frontmatter", "c.md", diff))
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual((self.root / "c.md").read_bytes(),
                         b"\xef\xbb\xbf---\r\nid: c\r\n---\r\n# C\r\n\r\ntext\r\n")

    def test_append_block_idempotent_and_replaces_only_between_markers(self):
        self.w("CLAUDE.md", b"mine\n")
        blk = ("--- a/CLAUDE.md\n+++ b/CLAUDE.md\n@@ -1 +1,4 @@\n mine\n+<!-- dagr:begin -->\n"
               "+V1\n+<!-- dagr:end -->\n")
        self.prop(item(1, "append-block", "CLAUDE.md", blk))
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual((self.root / "CLAUDE.md").read_text(),
                         "mine\n<!-- dagr:begin -->\nV1\n<!-- dagr:end -->\n")
        self.assertIn("already applied", self.apply()[1])
        self.prop(item(1, "append-block", "CLAUDE.md", blk.replace("V1", "V2")))
        self.assertEqual(self.apply()[0], 0)
        self.assertEqual((self.root / "CLAUDE.md").read_text(),
                         "mine\n<!-- dagr:begin -->\nV2\n<!-- dagr:end -->\n")

    def test_add_file_conflict_not_overwritten(self):
        self.w("n.md", b"theirs\n")
        self.prop(item(1, "add-file", "n.md",
                       "--- /dev/null\n+++ b/n.md\n@@ -0,0 +1 @@\n+ours\n"))
        rc, out = self.apply()
        self.assertEqual(rc, 2)
        self.assertIn("item 1", out)
        self.assertEqual((self.root / "n.md").read_bytes(), b"theirs\n")

    def test_uses_approval_md_and_refuses_unapproved(self):
        self.prop(item(1, "add-file", "n.md", "--- /dev/null\n+++ b/n.md\n@@ -0,0 +1 @@\n+ours\n"),
                  item(2, "add-file", "m.md", "--- /dev/null\n+++ b/m.md\n@@ -0,0 +1 @@\n+ours\n"))
        ap_ = self.root / ".dagr" / "approval.md"
        ap_.write_text("# Approval\n\n- status: pending\n- approved: 1\n")
        self.assertEqual(self.apply(None)[0], 2)
        ap_.write_text("# Approval\n\n- status: approved\n- approved: 1\n- excluded: 2\n")
        self.assertEqual(self.apply(None)[0], 0)
        self.assertTrue((self.root / "n.md").exists())
        self.assertFalse((self.root / "m.md").exists())

    def test_refuses_paths_outside_root_and_inside_dagr(self):
        self.prop(item(1, "add-file", "../x.md", "--- /dev/null\n+++ b/x\n@@ -0,0 +1 @@\n+x\n"))
        self.assertEqual(self.apply()[0], 2)
        self.prop(item(1, "add-file", ".dagr/other.md",
                       "--- /dev/null\n+++ b/x\n@@ -0,0 +1 @@\n+x\n"))
        self.assertEqual(self.apply()[0], 2)


if __name__ == "__main__":
    unittest.main()
