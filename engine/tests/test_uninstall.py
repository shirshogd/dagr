import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401
from dagr import cli, scaffold, status as status_mod, graphcore, config


def w(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))
    return p


class TestUninstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # the tree after an apply: two edited originals, one added file, one added file in a new folder
        w(self.root, "CLAUDE.md", "original\n<!-- dagr:begin -->block<!-- dagr:end -->\n")
        w(self.root, "workflows/a/CONTEXT.md", "---\nid: a\n---\nEDITED\n")
        w(self.root, "workflows/graph-loop/CONTEXT.md", "added by dagr\n")
        w(self.root, "keep.md", "user file\n")
        b = ".dagr/backup/20260101-104300/"
        w(self.root, b + "CLAUDE.md", "original\n")
        w(self.root, b + "workflows/a/CONTEXT.md", "# A original\r\n")
        w(self.root, b + "MANIFEST.md",
          "# Manifest\n\napproved: 1,2,3\n\n"
          "item 1  .dagr/config.json  new\n"
          "item 2  workflows/a/CONTEXT.md  existing\n"
          "item 3  workflows/graph-loop/CONTEXT.md  new\n"
          "item 9  CLAUDE.md  existing\n")
        # a later backup of the same file must NOT win over the oldest
        w(self.root, ".dagr/backup/20260202-090000/CLAUDE.md", "second generation\n")
        w(self.root, ".dagr/config.json", "{}")

    def test_restores_oldest_deletes_new_and_removes_dagr(self):
        out = []
        self.assertEqual(scaffold.uninstall(self.root, yes=True, out=out.append), 0)
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), b"original\n")
        self.assertEqual((self.root / "workflows/a/CONTEXT.md").read_bytes(), b"# A original\r\n")
        self.assertFalse((self.root / "workflows/graph-loop").exists())   # file + emptied folder
        self.assertTrue((self.root / "workflows/a").is_dir())
        self.assertEqual((self.root / "keep.md").read_text(), "user file\n")
        self.assertFalse((self.root / ".dagr").exists())

    def test_asks_first_and_aborts_on_no(self):
        out = []
        rc = scaffold.uninstall(self.root, yes=False, out=out.append, confirm=lambda: "n")
        self.assertEqual(rc, 1)
        self.assertTrue((self.root / ".dagr").is_dir())
        self.assertEqual((self.root / "CLAUDE.md").read_text().count("EDITED"), 0)
        self.assertIn("workflows/a/CONTEXT.md", (self.root / "workflows/a/CONTEXT.md").as_posix()
                      and "\n".join(out))

    def test_proceeds_on_yes_answer(self):
        self.assertEqual(scaffold.uninstall(self.root, out=lambda s: None, confirm=lambda: "y"), 0)
        self.assertFalse((self.root / ".dagr").exists())

    def test_manifest_cannot_delete_outside_root(self):
        w(self.root, ".dagr/backup/20260101-104300/MANIFEST.md",
          "item 1  ../outside.txt  new\n")
        outside = self.root.parent / "outside.txt"
        outside.write_text("x")
        self.addCleanup(lambda: outside.exists() and outside.unlink())
        scaffold.uninstall(self.root, yes=True, out=lambda s: None)
        self.assertTrue(outside.exists())

    def test_nothing_to_do_without_dagr(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(scaffold.uninstall(d, yes=True, out=lambda s: None), 0)

    def test_cli_uninstall_yes(self):
        self.assertEqual(cli.main(["uninstall", "--root", str(self.root), "--yes"]), 0)
        self.assertFalse((self.root / ".dagr").exists())


class TestStatusAndVendor(unittest.TestCase):
    def test_status_renders_and_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            md = root / ".dagr" / "maps" / "s"
            (md / "tickets").mkdir(parents=True)
            (md / "tickets" / "T01-a.md").write_text(
                "---\ntitle: Alpha\nstatus: open\nmodel: default\n---\n## Inputs\nx\n")
            (md / "tickets" / "T02-b.md").write_text(
                "---\ntitle: Beta\nstatus: open\nmodel: default\nneeds_human: which?\n---\n## Inputs\nx\n")
            s = graphcore.new_state("s")
            graphcore.ensure_ticket_record(s, "T01").update(status="closed", reviewer_score=0.9,
                                                            cost_usd=1.5, attempts=1)
            graphcore.save_state(md / "state.json", s)
            self.assertEqual(cli.main(["status", "s", "--root", str(root)]), 0)
            text = (md / "STATUS.md").read_text()
            self.assertIn("| T01 | Alpha | closed | 1 |", text)
            self.assertIn("closed 1/2", text)
            self.assertEqual(cli.main(["status", "nope", "--root", str(root)]), 2)

    def test_vendor_engine_copies_package_without_pycache(self):
        with tempfile.TemporaryDirectory() as d:
            dst = scaffold.vendor_engine(d)
            self.assertTrue((dst / "cli.py").is_file())
            self.assertFalse((dst / "__pycache__").exists())
            import subprocess, sys
            r = subprocess.run([sys.executable, "-B", str(dst / "cli.py"), "doctor", "--root", d],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("0 contract(s) found", r.stdout)

    def test_runs_as_script_from_repo_checkout(self):
        import subprocess, sys
        cli_py = Path(helpers.ENGINE) / "dagr" / "cli.py"
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, "-B", str(cli_py), "scan", "--root", d],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(d) / ".dagr" / "scan.json").is_file())


class TestManifestAndSafetyNet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_manifest_exactly_as_05_apply_shows(self):
        # written the way setup/05-apply/CONTEXT.md step 3 tells an agent to write it
        w(self.root, ".dagr/backup/20260101-104300/MANIFEST.md",
          "approved items: 1,2,3,4\n\n"
          "item 1  .dagr/config.json  new\n"
          "item 2  workflows/newsletter/CONTEXT.md  existing\n"
          "item 3  workflows/graph-loop/CONTEXT.md  new\n"
          "- item 4  `workflows/graph-loop/stages/01/CONTEXT.md`  new\n")
        w(self.root, "workflows/graph-loop/CONTEXT.md", "x")
        w(self.root, "workflows/graph-loop/stages/01/CONTEXT.md", "x")
        self.assertEqual(scaffold.read_manifests(self.root), [
            ".dagr/config.json", "workflows/graph-loop/CONTEXT.md",
            "workflows/graph-loop/stages/01/CONTEXT.md"])
        self.assertEqual(scaffold.uninstall(self.root, yes=True, out=lambda s: None), 0)
        self.assertFalse((self.root / "workflows").exists())

    def test_manifest_table_form(self):
        w(self.root, ".dagr/backup/x/MANIFEST.md",
          "| item | file | action |\n|---|---|---|\n| 1 | a/new.md | new |\n"
          "| 2 | b/old.md | existing |\n| item 3 | `c.md` | new |\n")
        self.assertEqual(scaffold.read_manifests(self.root), ["a/new.md", "c.md"])

    def test_strips_unbacked_block_and_nothing_else(self):
        w(self.root, ".dagr/config.json", '{"l0_files": ["CLAUDE.md"]}')
        w(self.root, "CLAUDE.md",
          "mine 1\n\n<!-- dagr:begin -->\nptr\n<!-- dagr:end -->\nmine 2\n")
        w(self.root, "AGENTS.md", "no block here\n")
        out = []
        self.assertEqual(scaffold.uninstall(self.root, yes=True, out=out.append), 0)
        self.assertEqual((self.root / "CLAUDE.md").read_text(), "mine 1\n\nmine 2\n")
        self.assertEqual((self.root / "AGENTS.md").read_text(), "no block here\n")
        self.assertTrue(any("stripped the dagr block from CLAUDE.md" in o for o in out))


if __name__ == "__main__":
    unittest.main()
