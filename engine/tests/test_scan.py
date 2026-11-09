import json
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401
from dagr import scan, cli


def w(root, rel, text=""):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))
    return p


INPUTS = "## Inputs\n\n| File | Why |\n|---|---|\n| `a.md` | x |\n"


def build_fixture(root):
    w(root, "CLAUDE.md", "# Rules\nRead CONTEXT.md\n")
    w(root, "AGENTS.md", "# agents\n")
    w(root, "CONTEXT.md", "# Router\n")
    # workflow with port frontmatter, stages/ layout, CRLF + BOM
    w(root, "workflows/news/CONTEXT.md",
      "﻿---\r\nid: news\r\nconsumes: [topic]\r\nproduces: [issue]\r\nowner: me\r\n---\r\n# News\r\n")
    w(root, "workflows/news/stages/01-research/CONTEXT.md", "# R\n" + INPUTS)
    w(root, "workflows/news/stages/02-draft/CONTEXT.md", "# D\n## Process\nx\n## Outputs\ny\n")
    # workflow without frontmatter, numbered folders, README as contract
    w(root, "pipelines/video/README.md", "---\nid: video\nproduces:\n  - script\n---\n# Video\n")
    w(root, "pipelines/video/01_hook/CONTEXT.md", "# Hook\n")
    w(root, "pipelines/video/02_script/CONTEXT.md", "# Script\n## Entradas\n\n| a | b |\n|--|--|\n| 1 | 2 |\n")
    w(root, "knowledge/voice.md", "voice\n")
    w(root, "research/notes.md", "n\n")
    w(root, "output/news/issue.md", "done\n")
    w(root, "workflows/news/output/x.md", "o\n")
    # things that must be skipped
    w(root, "node_modules/pkg/CONTEXT.md", "---\nid: junk\nproduces: [x]\n---\n")
    w(root, ".git/CONTEXT.md", "---\nid: junk2\nproduces: [x]\n---\n")
    w(root, ".venv/lib/CONTEXT.md", "---\nid: junk3\nproduces: [x]\n---\n")
    w(root, "pyenv/pyvenv.cfg", "home = x\n")
    w(root, "pyenv/CONTEXT.md", "---\nid: junk4\nproduces: [x]\n---\n")
    w(root, "workflows/news/output/CONTEXT.md", "---\nid: junk5\nproduces: [x]\n---\n")


class TestScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        build_fixture(self.root)

    def test_inventory(self):
        s = scan.scan(self.root)
        self.assertEqual([f["path"] for f in s["l0_files"]], ["CLAUDE.md", "AGENTS.md"])
        self.assertEqual(s["root_context"], "CONTEXT.md")
        paths = [c["path"] for c in s["context_files"]]
        self.assertIn("workflows/news/CONTEXT.md", paths)
        self.assertNotIn("node_modules/pkg/CONTEXT.md", paths)
        self.assertFalse(any(p.startswith((".git/", ".venv/", "pyenv/")) for p in paths))
        self.assertNotIn("workflows/news/output/CONTEXT.md", paths)
        wf = {x["path"]: x for x in s["workflow_candidates"]}
        self.assertEqual(sorted(wf), ["pipelines/video", "workflows/news"])   # not stages/ itself
        self.assertTrue(wf["workflows/news"]["contract_declared"])
        self.assertTrue(wf["pipelines/video"]["contract_declared"])   # README as contract
        self.assertEqual(wf["workflows/news"]["stages_missing_inputs_table"],
                         ["workflows/news/stages/02-draft"])
        self.assertEqual(wf["pipelines/video"]["stages_missing_inputs_table"],
                         ["pipelines/video/01_hook"])   # non-English heading counts as Inputs
        self.assertEqual([c["id"] for c in s["declared_contracts"]], ["news", "video"])
        self.assertEqual([o["path"] for o in s["output_folders"]],
                         ["output", "workflows/news/output"])
        self.assertEqual([k["path"] for k in s["knowledge_folders"]], ["knowledge", "research"])
        keys = {f["path"]: f["keys"] for f in s["existing_frontmatter"]}
        self.assertEqual(keys["workflows/news/CONTEXT.md"],
                         ["consumes", "id", "owner", "produces"])

    def test_deterministic_and_written(self):
        a = json.dumps(scan.scan(self.root), sort_keys=True)
        b = json.dumps(scan.scan(self.root), sort_keys=True)
        self.assertEqual(a, b)
        scan.run_scan(self.root)
        j = json.loads((self.root / ".dagr" / "scan.json").read_text())
        self.assertEqual(j["stats"]["contracts_declared"], 2)
        md = (self.root / ".dagr" / "scan.md").read_text()
        self.assertIn("workflows/news", md)
        # a second scan (now with .dagr/ present) gives the same inventory
        self.assertEqual(json.dumps(scan.scan(self.root), sort_keys=True), a)

    def test_cli_scan_writes_files(self):
        self.assertEqual(cli.main(["scan", "--root", str(self.root)]), 0)
        self.assertTrue((self.root / ".dagr" / "scan.json").is_file())

    def test_empty_tree(self):
        with tempfile.TemporaryDirectory() as d:
            s = scan.scan(d)
            self.assertEqual(s["workflow_candidates"], [])
            self.assertIn("none found", scan.render_md(s))

    def test_inputs_table_detection(self):
        self.assertTrue(scan.has_inputs_table("## Inputs\n\n| a | b |\n|-|-|\n"))
        self.assertFalse(scan.has_inputs_table("## Inputs\n- a list\n## Outputs\n| a |\n"))
        self.assertTrue(scan.has_inputs_table("### 输入\n| a |\n"))


if __name__ == "__main__":
    unittest.main()
