"""apply: make the approved items of `.dagr/PROPOSAL.md`, safely. Stdlib only.

    dagr apply --items 1,2,5-7|all [--dry-run]

Reads `.dagr/PROPOSAL.md` (items shaped as setup/03-propose describes: `### N. action: path`,
`- file:`, `- action:`, a fenced unified diff) and, when `--items` is not given,
`.dagr/approval.md`. Nothing is written unless EVERY selected diff applies cleanly; otherwise
exit 2 naming the item. Existing files are copied to `.dagr/backup/<timestamp>/` first and a
`MANIFEST.md` lists each touched file as `item N  <path>  existing|new`, the shape `uninstall`
reads. Running it again changes nothing (items report `already applied`).
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

from . import config

ITEM_HEAD = re.compile(r"^###\s+(\d+)\.\s*([A-Za-z\-]+)\s*:\s*(.*?)\s*$")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
ACTIONS = ("add-frontmatter", "add-file", "append-block")


class ApplyError(Exception):
    pass


# ---- reading the proposal -------------------------------------------------------

def parse_proposal(text: str) -> list:
    """-> [{n, action, file, diff: [lines]}] in file order."""
    lines = text.replace("\r\n", "\n").split("\n")
    heads = [i for i, l in enumerate(lines) if ITEM_HEAD.match(l)]
    items = []
    for k, i in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        m = ITEM_HEAD.match(lines[i])
        it = {"n": int(m.group(1)), "action": m.group(2).lower(), "file": m.group(3).strip(
        ).strip("`"), "diff": None}
        body = lines[i + 1:end]
        for l in body:
            fm = re.match(r"^-\s*file:\s*(.+?)\s*$", l)
            am = re.match(r"^-\s*action:\s*(.+?)\s*$", l)
            if fm:
                it["file"] = fm.group(1).strip("`")
            if am:
                it["action"] = am.group(1).strip("`").lower()
        j = next((x for x, l in enumerate(body) if re.match(r"^\s*(`{3,}|~{3,})\s*diff\s*$", l)),
                 None)
        if j is not None:
            fence = re.match(r"^\s*(`{3,}|~{3,})", body[j]).group(1)
            diff = []
            for l in body[j + 1:]:
                if l.strip().startswith(fence[0] * len(fence)) and l.strip(fence[0]) == "":
                    break
                diff.append(l)
            it["diff"] = diff
        items.append(it)
    return items


def parse_numbers(spec: str, valid) -> list:
    spec = (spec or "").strip().lower()
    if spec in ("all", "*"):
        return sorted(valid)
    out = set()
    for part in re.split(r"[,\s]+", spec):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if m:
            out.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.isdigit():
            out.add(int(part))
        else:
            raise ApplyError(f"cannot read item list `{spec}`")
    unknown = sorted(out - set(valid))
    if unknown:
        raise ApplyError("no such item(s) in PROPOSAL.md: " + ", ".join(map(str, unknown)))
    return sorted(out)


def read_approval(path: Path, valid):
    """-> (status, [numbers]) from approval.md."""
    text = path.read_text(encoding="utf-8", errors="replace")
    st = re.search(r"^-\s*status:\s*([A-Za-z]+)", text, re.M)
    ap = re.search(r"^-\s*approved:[ \t]*([0-9, \t\-]*)", text, re.M)
    status = st.group(1).lower() if st else "pending"
    nums = parse_numbers(ap.group(1), valid) if ap and ap.group(1).strip() else []
    return status, nums


# ---- unified diff ----------------------------------------------------------------

def parse_hunks(diff: list) -> list:
    """-> [{old_start, ops: [(kind, text, noeol)]}] with kind in ' ', '-', '+'."""
    hunks, cur = [], None
    for l in diff:
        m = HUNK.match(l)
        if m:
            cur = {"old_start": int(m.group(1)), "ops": []}
            hunks.append(cur)
            continue
        if cur is None:
            continue   # --- / +++ headers
        if l.startswith("\\"):
            if cur["ops"]:
                k, t, _ = cur["ops"][-1]
                cur["ops"][-1] = (k, t, True)
            continue
        if l[:1] in (" ", "-", "+"):
            cur["ops"].append((l[0], l[1:], False))
        elif l == "":
            cur["ops"].append((" ", "", False))   # a blank context line stripped by an editor
    return hunks


def _split(data: bytes):
    """-> (bom, [content], [eol]) ; eol is '\\r\\n', '\\n' or '' (last line only)."""
    text = data.decode("utf-8")
    bom = text.startswith("﻿")
    if bom:
        text = text[1:]
    contents, eols = [], []
    for raw in text.split("\n"):
        contents.append(raw)
    if contents and contents[-1] == "":
        contents.pop()
        last_has_nl = True
    else:
        last_has_nl = False
    out_c, out_e = [], []
    for i, c in enumerate(contents):
        if c.endswith("\r"):
            out_c.append(c[:-1])
            out_e.append("\r\n")
        else:
            out_c.append(c)
            out_e.append("\n")
    if out_e and not last_has_nl:
        out_e[-1] = ""
    return bom, out_c, out_e


def _join(bom, contents, eols) -> bytes:
    parts = []
    for i, (c, e) in enumerate(zip(contents, eols)):
        if i < len(contents) - 1 and e == "":
            e = "\n"
        parts.append(c + e)
    return (("﻿" if bom else "") + "".join(parts)).encode("utf-8")


def _dominant_eol(eols):
    crlf = sum(1 for e in eols if e == "\r\n")
    return "\r\n" if crlf and crlf >= sum(1 for e in eols if e == "\n") else "\n"


def apply_hunks(data: bytes, hunks: list, reverse=False) -> bytes:
    """Apply hunks to `data`; ApplyError when a context/removed line does not match."""
    bom, cont, eols = _split(data)
    nl = _dominant_eol(eols)
    cursor = 0
    for h in hunks:
        ops = h["ops"]
        if reverse:
            ops = [({"+": "-", "-": "+"}.get(k, k), t, ne) for k, t, ne in ops]
        old = [t.rstrip("\r") for k, t, _ in ops if k in " -"]
        want = max(0, h["old_start"] - 1)
        if reverse:
            want = 0
        at = None
        if not old:
            at = min(max(cursor, want), len(cont))
        else:
            cands = [want] + list(range(cursor, len(cont) - len(old) + 1))
            for c in cands:
                if c >= cursor and c + len(old) <= len(cont) and \
                        [x.lstrip("﻿") if c == 0 else x
                         for x in cont[c:c + len(old)]] == old:
                    at = c
                    break
        if at is None:
            first = old[0] if old else ""
            raise ApplyError(f"hunk at line {h['old_start']} does not match the file "
                             f"(expected `{first[:60]}`)")
        new_c, new_e = [], []
        idx = at
        for k, t, noeol in ops:
            t = t.rstrip("\r")
            if k in " -":
                if k == " ":
                    new_c.append(cont[idx])
                    new_e.append(eols[idx])
                idx += 1
            else:
                new_c.append(t)
                new_e.append("" if noeol else nl)
        cont[at:idx] = new_c
        eols[at:idx] = new_e
        cursor = at + len(new_c)
    return _join(bom, cont, eols)


def _plus_text(diff: list) -> bytes:
    """add-file: the new file's bytes are the `+` lines."""
    hunks = parse_hunks(diff)
    out = []
    for h in hunks:
        for k, t, noeol in h["ops"]:
            if k == "+":
                out.append((t, noeol))
    if not out:
        return b""
    body = "".join(t + ("" if ne else "\n") for t, ne in out)
    return body.encode("utf-8")


def _plus_lines(diff: list) -> list:
    return [t.rstrip("\r") for h in parse_hunks(diff) for k, t, _ in h["ops"] if k == "+"]


def _marker_span(lines: list):
    b = next((i for i, l in enumerate(lines) if "dagr:begin" in l), None)
    if b is None:
        return None
    e = next((i for i in range(b, len(lines)) if "dagr:end" in lines[i]), None)
    return (b, e) if e is not None else None


# ---- one item against current bytes -----------------------------------------------

def compute(item, current):
    """-> ("applied", new_bytes) | ("already", None). Raises ApplyError."""
    act, diff = item["action"], item["diff"]
    if act not in ACTIONS:
        raise ApplyError(f"action `{act}` is not one of {', '.join(ACTIONS)}")
    if diff is None:
        raise ApplyError("the item has no ```diff block")
    if act == "add-file":
        want = _plus_text(diff)
        if current is None:
            return "applied", want
        if current == want:
            return "already", None
        raise ApplyError("conflict: the file exists with different content (not overwritten)")
    if current is None:
        raise ApplyError(f"{act} needs the file to exist, and it does not")
    if act == "append-block":
        _b, cont, eols = _split(current)
        prop = _plus_lines(diff)
        pspan = _marker_span(prop)
        cspan = _marker_span(cont)
        if pspan and cspan:   # dagr's own block: replace only what is between the markers
            if cont[cspan[0]:cspan[1] + 1] == prop[pspan[0]:pspan[1] + 1]:
                return "already", None
            nl = _dominant_eol(eols)
            cont[cspan[0]:cspan[1] + 1] = prop[pspan[0]:pspan[1] + 1]
            eols[cspan[0]:cspan[1] + 1] = [nl] * (pspan[1] - pspan[0] + 1)
            return "applied", _join(_b, cont, eols)
    hunks = parse_hunks(diff)
    if not hunks:
        raise ApplyError("the diff has no @@ hunk")
    if True:
        try:   # same lines already there? then it is applied
            apply_hunks(current, hunks, reverse=True)
            return "already", None
        except ApplyError:
            pass
    try:
        return "applied", apply_hunks(current, hunks)
    except ApplyError as e:
        raise ApplyError(f"the diff does not apply cleanly: {e}")


# ---- the command ------------------------------------------------------------------

def _safe(root: Path, rel: str, n):
    rel = rel.replace("\\", "/")
    p = (root / rel).resolve()
    try:
        r = p.relative_to(root.resolve()).as_posix()
    except ValueError:
        raise ApplyError(f"item {n}: `{rel}` is outside the root")
    if r.startswith(".dagr/") and r != ".dagr/config.json":
        raise ApplyError(f"item {n}: `{rel}` is inside .dagr/ (only .dagr/config.json is allowed)")
    return p, r


def run_apply(root, items_arg=None, dry_run=False, out=print) -> int:
    root = Path(root).resolve()
    d = config.dagr_dir(root)
    pp = d / "PROPOSAL.md"
    if not pp.is_file():
        out("ERROR: .dagr/PROPOSAL.md not found")
        return 2
    items = parse_proposal(pp.read_bytes().decode("utf-8", errors="replace"))
    by_n = {it["n"]: it for it in items}
    if not by_n:
        out("ERROR: PROPOSAL.md holds no `### N. action: path` items")
        return 2
    try:
        if items_arg:
            chosen = parse_numbers(items_arg, by_n)
        else:
            ap = d / "approval.md"
            if not ap.is_file():
                out("ERROR: no --items given and no .dagr/approval.md. Use --items all or "
                    "--items 1,2,5")
                return 2
            status, chosen = read_approval(ap, by_n)
            if status != "approved":
                out(f"ERROR: approval.md status is `{status}`, not approved: nothing applied")
                return 2
    except ApplyError as e:
        out(f"ERROR: {e}")
        return 2
    if not chosen:
        out("ERROR: no approved items")
        return 2

    overlay = {}     # rel -> bytes after earlier items in this run
    before = {}      # rel -> original bytes (None when absent)
    plan, errors = [], []
    for n in chosen:
        it = by_n[n]
        try:
            p, rel = _safe(root, it["file"], n)
            if rel not in overlay:
                cur = p.read_bytes() if p.is_file() else None
                before[rel] = cur
                overlay[rel] = cur
            res, new = compute(it, overlay[rel])
            if res == "applied":
                overlay[rel] = new
            plan.append((n, it, rel, res))
        except (ApplyError, UnicodeDecodeError, OSError) as e:
            errors.append(f"item {n} ({it['action']}: {it['file']}): {e}")
            plan.append((n, it, it["file"], "conflict" if "conflict" in str(e) else "failed"))
    if errors:
        out("REFUSED: nothing was changed.")
        for e in errors:
            out("  " + e)
        return 2
    todo = [x for x in plan if x[3] == "applied"]
    for n, it, rel, res in plan:
        word = "already applied" if res == "already" else (
            "would apply" if dry_run else "applied")
        out(f"  item {n}  {it['action']}  {rel}  {word}")
    if dry_run:
        out(f"dry-run: {len(todo)} item(s) would change files, {len(plan) - len(todo)} already "
            "applied. Nothing written.")
        return 0

    stamp = ""
    if todo:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        bdir = d / "backup" / stamp
        k = 2
        while bdir.exists():
            bdir = d / "backup" / f"{stamp}-{k}"
            k += 1
        stamp = bdir.name
        man = ["# Manifest", "", "approved: " + ",".join(str(n) for n in chosen), ""]
        backed = set()
        for n, it, rel, res in todo:
            existed = before[rel] is not None
            if existed and rel not in backed:
                dst = bdir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(before[rel])
                backed.add(rel)
            man.append(f"item {n}  {rel}  {'existing' if existed else 'new'}")
        bdir.mkdir(parents=True, exist_ok=True)
        (bdir / "MANIFEST.md").write_text("\n".join(man) + "\n", encoding="utf-8", newline="\n")
        for rel in {x[2] for x in todo}:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(overlay[rel])
    log = ["# Apply log", "", f"- run: {stamp or '(nothing applied)'}",
           f"- backup: .dagr/backup/{stamp}/" if stamp else "- backup: none",
           "- approved: " + ",".join(str(n) for n in chosen), "",
           "| item | file | action | result |", "|---|---|---|---|"]
    for n, it, rel, res in plan:
        log.append(f"| {n} | {rel} | {it['action']} | "
                   f"{'applied' if res == 'applied' else 'already applied'} |")
    (d / "APPLY-LOG.md").write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    out(f"applied {len(todo)} item(s), {len(plan) - len(todo)} already applied"
        + (f"; backup .dagr/backup/{stamp}/" if stamp else "") + "; log .dagr/APPLY-LOG.md")
    return 0
