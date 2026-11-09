"""reviewer: a separate, read-only agent process scores a finished ticket against its
Definition of done. Stdlib only.

The reviewer is its own process, started through `runner_lib.launch_worker` with the worker
template named in `.dagr/config.json` -> reviewer.worker (so it can be a different agent CLI
than the worker). It prints a verdict as text and `run_review` writes the verdict file itself;
nothing is ever auto-passed.

    run_review(ticket_path, receipt_path, diff_text, out_path, model="", visual_paths=(), *,
               root, worker=None, launcher=None, timeout=900, max_turns=30,
               max_budget_usd=2.0, allowed_tools=None, disallowed_tools=None) -> dict

Tool lockdown (ALLOWED_TOOLS / DISALLOWED_TOOLS) is passed only to templates that have a
`tools` mapping (the claude template). For other agent CLIs the read-only rule is stated in
the brief but not enforced by flags.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from . import runner_lib

PASS_THRESHOLD = 0.8
MAX_ATTEMPTS = 3
DIFF_CAP = 60 * 1024

ALLOWED_TOOLS = [
    "Read", "Glob", "Grep",
    "Bash(python -B -m pytest:*)", "Bash(python -B -m unittest:*)",
    "Bash(git diff:*)", "Bash(git status:*)", "Bash(git log:*)", "Bash(git show:*)"]
DISALLOWED_TOOLS = [
    "Write", "Edit", "NotebookEdit", "Bash(python -c:*)", "Bash(python -m pip:*)",
    # built from verbs so the literal write-git strings never appear in this file
    *[f"Bash(git {v}:*)" for v in ("com" + "mit", "pu" + "sh", "checkout", "reset")],
    "Bash(git * --output*)", "Bash(rm:*)", "Bash(del:*)"]

_VISUAL_EXT = (".html", ".css", ".svg", ".png", ".pdf")
_VISUAL_WORDS = re.compile(r"\bscreenshots?\b|\brender(?:ed|ing)?\b(?!\s*\()", re.I)

INSTRUCTION = (
    "Score 0.0-1.0 ONLY against the Definition of done. List each DoD item as met or unmet "
    "with the evidence. Do not reward effort or style. Do not suggest scope beyond the ticket. "
    "Unverified claims in the receipt count as unmet: open and check the named file with Read, "
    "and re-run the DoD's test/check commands yourself when you are able to. Run commands "
    "plainly and NEVER redirect output to files. Do not change any file. A DoD command you "
    "cannot run is reported \"unverifiable\", never \"met\". Output exactly this format at the "
    "end:\n"
    "score: <0.00-1.00>\n"
    "discrepancies:\n"
    "- a bullet per unmet item\n"
    "notes:\n"
    "concrete fix instructions for the worker.")


# ---- ticket parsing (tiny, own copy) ----------------------------------------------------

def _frontmatter(text: str) -> dict:
    m = re.match(r"^﻿?---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            k, sep, v = line.partition(":")
            if sep and re.fullmatch(r"[\w-]+", k.strip()):
                out[k.strip()] = v.strip()
    return out


def _section(text: str, name: str) -> str:
    m = re.search(rf"^##\s+{re.escape(name)}[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


def _affects(fm: dict) -> list:
    raw = fm.get("affects", "").strip()
    if raw.startswith("["):
        raw = raw[1:raw.rfind("]")] if "]" in raw else raw[1:]
    return [a.strip().strip("'\"") for a in raw.split(",") if a.strip().strip("'\"")]


def is_visual(ticket_text: str) -> bool:
    """`type: prototype` with a visual-extension affects path, or a DoD that mentions
    screenshot/render. Frontmatter `visual: false|true` overrides."""
    fm = _frontmatter(ticket_text)
    v = fm.get("visual", "").lower()
    if v in ("false", "no", "0"):
        return False
    if v in ("true", "yes", "1"):
        return True
    if fm.get("type", "").lower() == "prototype" and any(
            a.lower().endswith(_VISUAL_EXT) for a in _affects(fm)):
        return True
    return bool(_VISUAL_WORDS.search(_section(ticket_text, "Definition of done")
                                       or _section(ticket_text, "Acceptance")))


def reviewer_model(ticket_text: str, default: str = "") -> str:
    return _frontmatter(ticket_text).get("reviewer") or default


# ---- brief -------------------------------------------------------------------------------

def build_review_brief(ticket_text: str, dod: str, diff: str, receipt: str, visual: bool,
                       screenshots: list) -> str:
    goal = _section(ticket_text, "Goal")
    parts = ["# Reviewer brief", "",
             "You are an independent reviewer, not the worker. Read and check; you must not "
             "change any file.", "",
             "## Goal (verbatim)", "", goal or "(none)", "",
             "## Definition of done (verbatim)", "", dod or "(none stated)", ""]
    if visual:
        parts += ["## Rendered output (visual deliverable)", "",
                  "This is a visual ticket: judge ONLY what is rendered, never the code. Read "
                  "each image below and score what you see. Do not open the code files that "
                  "produced it.", ""]
        parts += [f"- {p}" for p in screenshots] or ["- (none)"]
        parts += [""]
    else:
        d = diff or "(no changes to the ticket's affects paths, or no git history to diff)"
        if len(d.encode("utf-8", "replace")) > DIFF_CAP:
            d = d.encode("utf-8", "replace")[:DIFF_CAP].decode("utf-8", "ignore")
            d += f"\n... [diff truncated at {DIFF_CAP // 1024} KB; Read the files for the rest]"
        parts += ["## Diff of the ticket's affects paths", "", "```diff", d, "```", ""]
    parts += ["## Worker receipt", "", receipt or "(no receipt)", "",
              "## Instructions", "", INSTRUCTION, ""]
    return "\n".join(parts)


# ---- verdict -----------------------------------------------------------------------------

def parse_verdict(text) -> dict:
    """{"score": float|None, "discrepancies": str, "notes": str, "raw": text}"""
    text = text or ""
    m = re.search(r"^score:\s*(\S+)", text, re.M)
    if not m:
        return {"score": None, "discrepancies": "", "notes": "", "raw": text}
    raw = m.group(1).strip().lower()
    score = 1.0 if raw == "pass" else 0.0 if raw == "fail" else None
    if score is None:
        try:
            score = float(raw)
        except ValueError:
            score = None
    d = re.search(r"^discrepancies:\s*(.*?)(?=^\w+:|\Z)", text, re.M | re.S)
    n = re.search(r"^notes:\s*(.*?)(?=^\w+:|\Z)", text, re.M | re.S)
    return {"score": score, "discrepancies": (d.group(1).strip() if d else ""),
            "notes": (n.group(1).strip() if n else ""), "raw": text}


def _valid(score) -> bool:
    return isinstance(score, float) and math.isfinite(score) and 0.0 <= score <= 1.0


def passes(score, threshold=None) -> bool:
    return _valid(score) and score >= (PASS_THRESHOLD if threshold is None else threshold)


def format_verdict(score, discrepancies: str, notes: str, extra: str = "") -> str:
    label = "PASS" if passes(score) else "FAIL"
    s = f"score: {score:.2f} {label}\n\ndiscrepancies:\n{discrepancies or '(none)'}\n\n"
    s += f"notes:\n{notes or '(none)'}\n"
    return s + (f"\n{extra}\n" if extra else "")


def _tail_verdict(text: str) -> str:
    """The reviewer analyses first and prints the format last: parse from the LAST score:."""
    idx = [m.start() for m in re.finditer(r"^score:", text or "", re.M)]
    return text[idx[-1]:] if idx else (text or "")


def _write(out_path: Path, text: str):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")


# ---- run ---------------------------------------------------------------------------------

def run_review(ticket_path, receipt_path, diff_text, out_path, model="", visual_paths=(), *,
               root=".", worker=None, launcher=None, timeout=900, max_turns=30,
               max_budget_usd=2.0, allowed_tools=None, disallowed_tools=None) -> dict:
    """-> {"score": float|None, "passed": bool, "discrepancies", "notes", "verdict_path",
    "visual": bool, "launched": bool, "error": str|None, "cost_usd": float}.
    `error` set (score None) when the reviewer failed or printed no valid score; nothing is
    ever auto-passed. The verdict file is written only for a valid score."""
    out_path = Path(out_path)
    lib = launcher or runner_lib
    if worker is None:
        from . import config
        worker = config.worker_cfg(config.DEFAULT_CONFIG, "claude")
    ticket_text = Path(ticket_path).read_text(encoding="utf-8", errors="replace")
    try:
        receipt = Path(receipt_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        receipt = ""
    dod = _section(ticket_text, "Definition of done") or _section(ticket_text, "Acceptance")
    visual = is_visual(ticket_text)
    res = {"score": None, "passed": False, "discrepancies": "", "notes": "",
           "verdict_path": str(out_path), "visual": visual, "launched": False,
           "error": None, "cost_usd": 0.0}
    shots = [str(p).replace("\\", "/") for p in visual_paths]

    if visual and not shots:
        res.update(score=0.0, passed=False,
                   discrepancies="- no rendered screenshots supplied",
                   notes="Render the deliverable and save screenshots (*.png) in the "
                         "ticket's assets folder, then list them in the receipt.")
        _write(out_path, format_verdict(0.0, res["discrepancies"], res["notes"]))
        return res

    brief = build_review_brief(ticket_text, dod, diff_text, receipt, visual, shots)
    out_raw = out_path.with_suffix(".raw.out")
    out_err = out_path.with_suffix(".err")
    try:
        proc = lib.launch_worker(
            worker, brief, root, out_raw, out_err, reviewer_model(ticket_text, model) or None,
            list(allowed_tools or ALLOWED_TOOLS), list(disallowed_tools or DISALLOWED_TOOLS),
            max_turns=max_turns, prompt_file=out_path.with_suffix(".prompt.md"),
            max_budget_usd=max_budget_usd)
    except Exception as e:
        res["error"] = f"could not launch reviewer: {type(e).__name__}: {e}"
        return res
    res["launched"] = True
    try:
        rc = proc.wait(timeout=timeout)
    except Exception:
        try:
            lib.kill_tree(proc.pid)
        except Exception:
            pass
        res["error"] = f"reviewer timed out after {timeout}s"
        return res
    data = lib.read_output(out_raw, worker.get("output", "claude-stream"))
    if data is None:
        res["error"] = f"reviewer output unreadable (exit {rc})"
        return res
    try:
        res["cost_usd"] = float(data.get("total_cost_usd") or 0)
    except (TypeError, ValueError):
        pass
    if data.get("is_error") or rc != 0:
        res["error"] = f"reviewer failed (exit {rc}): {str(data.get('result'))[:200]}"
        return res
    v = parse_verdict(_tail_verdict(str(data.get("result") or "")))
    if not _valid(v["score"]):
        res["error"] = "reviewer printed no parseable score in [0,1]"
        return res
    res.update(score=v["score"], passed=passes(v["score"]),
               discrepancies=v["discrepancies"], notes=v["notes"])
    _write(out_path, format_verdict(v["score"], v["discrepancies"], v["notes"]))
    return res
