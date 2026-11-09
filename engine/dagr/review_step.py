"""review_step: the graph runner's reviewer hook.

`review_and_decide(ticket, state, slug, root, ...)` runs reviewer.run_review over the worker's
diff + receipt and returns "pass" | "retry" | "fail" (or None when there is no receipt to
review, so the runner applies its own worker-failure handling). It only reads the tree
(git diff/status when the root is a git repo) and writes under
`.dagr/maps/<slug>/assets/<T##>/`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import graphcore, reviewer, runner_lib

UNTRACKED_CAP = 20 * 1024
MAX_REVIEW_ERRORS = 3   # consecutive reviewer-failure rounds before the ticket is failed


def _git(root, *args) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=120)
    return r.stdout.decode("utf-8", "replace")


def build_diff(ticket, root) -> str:
    """`git diff HEAD` over the ticket's affects, plus the contents (<= 20 KB each) of new
    untracked files there. Empty when the root is not a git repo (the reviewer is told to
    read the files instead)."""
    affects = [a for a in (ticket.affects or []) if a]
    if not affects or not runner_lib.is_git_repo(root):
        return ""
    parts = []
    d = _git(root, "diff", "HEAD", "--", *affects).strip()
    if d:
        parts.append(d)
    st = _git(root, "status", "--porcelain", "--untracked-files=all", "--", *affects)
    for line in st.splitlines():
        if not line.startswith("??"):
            continue
        rel = line[3:].strip().strip('"')
        fp = Path(root) / rel
        try:
            data = fp.read_bytes()
        except OSError:
            continue
        txt = data[:UNTRACKED_CAP].decode("utf-8", "replace")
        more = "\n... [file truncated at 20 KB]" if len(data) > UNTRACKED_CAP else ""
        parts.append(f"--- new untracked file: {rel}\n{txt}{more}")
    return "\n\n".join(parts)


def _screenshots(adir: Path, root) -> list:
    return sorted(p.relative_to(root).as_posix() for p in adir.glob("*.png"))


def reviewer_stray(before: dict, after: dict, adir_rel: str) -> list:
    """Paths whose status changed during the review, outside the ticket's assets folder."""
    pre = adir_rel.rstrip("/") + "/"
    return sorted(p for p in set(before) | set(after)
                  if before.get(p) != after.get(p) and not p.startswith(pre))


def _write_failed(adir: Path, ticket, rec, slug, reason="review-failed"):
    if reason == "review-failed":
        head = (f"Reviewer attempts used: {rec.get('attempts')} of {reviewer.MAX_ATTEMPTS}. "
                "Flagged for re-plan (`replan_needed`).")
    elif reason == "reviewer-unavailable":
        head = ("reason: reviewer-unavailable. The reviewer process failed repeatedly "
                f"({rec.get('review_error')}). This is infrastructure, NOT a ticket defect: "
                "do not re-plan; re-run the review when the reviewer works "
                "(`reviewer_unavailable`).")
    else:
        head = ("reason: reviewer-stray-paths. The reviewer changed files outside the assets "
                "folder (`reviewer_stray_paths`): "
                + ", ".join(rec.get("reviewer_stray_paths") or []))
    lines = [f"# {ticket.id} FAILED review ({slug})", "", head, "", "## Attempts", ""]
    scores, verdicts = rec.get("scores") or [], rec.get("verdicts") or []
    for i, s in enumerate(scores):
        v = verdicts[i] if i < len(verdicts) else "?"
        lines.append(f"- attempt {i + 1}: score {s} ({v})")
    lines += ["", "## Last notes", "", rec.get("notes") or "(none)", ""]
    (adir / "FAILED.md").write_text("\n".join(lines), encoding="utf-8")


def review_and_decide(ticket, state, slug, root, reviewer_model="", worker=None,
                      launcher=None, threshold=None, max_attempts=None,
                      ignore=()) -> "str | None":
    root = Path(root)
    threshold = reviewer.PASS_THRESHOLD if threshold is None else float(threshold)
    max_attempts = int(max_attempts or reviewer.MAX_ATTEMPTS)
    rec = graphcore.ensure_ticket_record(state, ticket.id)
    adir = runner_lib.assets_dir(root, slug, ticket.id)
    receipt = adir / "receipt.md"
    if not receipt.is_file():
        return None   # nothing to review: the runner records the worker failure
    attempt = max(1, int(rec.get("attempts") or 1))
    vpath = adir / f"verdict-{attempt}.md"
    diff = build_diff(ticket, root)
    shots = _screenshots(adir, root)

    before = runner_lib.porcelain(root)
    res = None
    for _ in range(2):   # one re-try of the review itself
        res = reviewer.run_review(
            ticket.path, receipt, diff, vpath, model=reviewer_model, visual_paths=shots,
            root=root, worker=worker, launcher=launcher)
        if res["score"] is not None:
            break

    stray = reviewer_stray(before, runner_lib.porcelain(root), runner_lib.assets_rel(slug, ""))
    if ignore:   # other workers running at the same time legitimately change their own paths
        stray = [p for p in stray if not graphcore.affects_overlap([p], list(ignore))]
    if stray:
        # a read-only reviewer must not change the tree: record it, never auto-revert, never pass
        rec["reviewer_stray_paths"] = stray
        rec["notes_last_failure"] = "reviewer wrote outside assets: " + ", ".join(stray)
        if vpath.is_file():
            with open(vpath, "a", encoding="utf-8") as f:
                f.write("\nreviewer_stray_paths:\n" + "\n".join(f"- {p}" for p in stray) + "\n")
        _write_failed(adir, ticket, rec, slug, "reviewer-stray-paths")
        return "fail"

    if res["score"] is None:
        # reviewer broke twice: never auto-pass. Give the worker attempt back, unless the
        # reviewer keeps failing (bounded so a dead reviewer cannot loop workers forever).
        rec["review_error"] = res["error"]
        n = int(rec.get("review_errors") or 0) + 1
        rec["review_errors"] = n
        if n >= MAX_REVIEW_ERRORS:
            rec["notes_last_failure"] = f"reviewer failed {n} times: {res['error']}"
            rec["reviewer_unavailable"] = True
            _write_failed(adir, ticket, rec, slug, "reviewer-unavailable")
            return "fail"
        rec["attempts"] = max(0, int(rec.get("attempts") or 1) - 1)
        return "retry"

    rec.pop("review_error", None)
    rec["review_errors"] = 0
    rec["reviewer_score"] = res["score"]
    rec["cost_usd"] = float(rec.get("cost_usd") or 0) + float(res.get("cost_usd") or 0)
    rec.setdefault("verdicts", []).append(vpath.relative_to(root).as_posix())
    rec.setdefault("scores", []).append(res["score"])
    if reviewer.passes(res["score"], threshold):
        rec.pop("notes", None)
        return "pass"
    notes = "\n".join(x for x in (
        "Unmet items:\n" + res["discrepancies"] if res["discrepancies"] else "",
        "Reviewer notes:\n" + res["notes"] if res["notes"] else "") if x)
    rec["notes"] = notes or f"Reviewer scored {res['score']:.2f} (< {threshold})."
    if attempt < max_attempts:
        return "retry"
    rec["replan_needed"] = True
    _write_failed(adir, ticket, rec, slug)
    return "fail"
