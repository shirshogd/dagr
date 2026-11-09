"""scaffold: creating and removing dagr's own folder. Stdlib only.

    ensure_dagr(root)      make `.dagr/` and `.dagr/maps/`, write config.json if missing
    vendor_engine(root)    copy this package to `.dagr/engine/dagr/` (so it runs with no install)
    uninstall(root, yes)   restore files from `.dagr/backup/<ts>/`, delete files that the
                           backup MANIFEST.md lists as `new`, then remove `.dagr/`
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
from pathlib import Path

from . import config

MANIFEST_LINE = re.compile(r"\bitem\s+\d+\s+(.+?)\s+(existing|new)\s*$", re.I)


def ensure_dagr(root) -> Path:
    d = config.dagr_dir(root)
    (d / "maps").mkdir(parents=True, exist_ok=True)
    config.write_default_config(root)
    return d


def vendor_engine(root) -> Path:
    """Copy this package into `<root>/.dagr/engine/dagr/` (no __pycache__)."""
    src = Path(__file__).resolve().parent
    dst = config.dagr_dir(root) / "engine" / "dagr"
    if dst.resolve() == src:
        return dst
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dst


def _inside(root: Path, rel: str):
    """root/rel, or None when it would leave the root."""
    p = (root / rel).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        return None
    return p


def backup_dirs(root) -> list:
    b = config.dagr_dir(root) / "backup"
    return sorted(p for p in b.iterdir() if p.is_dir()) if b.is_dir() else []


def parse_manifest_line(line):
    """-> (path, "existing"|"new") or None. Accepts the line form `item 3  <path>  new` (also
    after a bullet or in backticks) and a markdown table row: `| 3 | <path> | new |`."""
    raw = line.strip()
    if "|" in raw:
        cells = [c.strip().strip("`").strip() for c in raw.strip("|").split("|")]
        for i, c in enumerate(cells):
            if c.lower() in ("existing", "new") and i >= 1:
                path = cells[i - 1]
                if path and not re.fullmatch(r"(item\s*)?\d+", path, re.I) and path.lower() not in ("file", "path", "---", ":---"):
                    return path.replace("\\", "/"), c.lower()
    mm = MANIFEST_LINE.search(raw.strip("|").strip())
    if mm:
        return mm.group(1).strip().strip("`").replace("\\", "/"), mm.group(2).lower()
    return None


def read_manifests(root) -> list:
    """Paths (relative, posix) that manifests list as `new`."""
    new = []
    for bd in backup_dirs(root):
        m = bd / "MANIFEST.md"
        if not m.is_file():
            continue
        for line in m.read_text(encoding="utf-8", errors="replace").splitlines():
            got = parse_manifest_line(line)
            if got and got[1] == "new" and got[0] not in new:
                new.append(got[0])
    return new


def restore_plan(root) -> dict:
    """{relpath: backup file} using the OLDEST backup of each file (the true original)."""
    out = {}
    for bd in backup_dirs(root):
        for dp, _dns, fns in os.walk(bd):
            for fn in fns:
                f = Path(dp) / fn
                rel = f.relative_to(bd).as_posix()
                if rel == "MANIFEST.md":
                    continue
                out.setdefault(rel, f)
    return out


BEGIN, END = "<!-- dagr:begin -->", "<!-- dagr:end -->"


def strip_block(text: str):
    """Remove the first `<!-- dagr:begin -->` .. `<!-- dagr:end -->` span, markers included,
    from the first line holding the begin marker through the end of the line holding the end
    marker. -> new text, or None when there is no complete block."""
    i = text.find(BEGIN)
    if i < 0:
        return None
    j = text.find(END, i)
    if j < 0:
        return None
    start = text.rfind("\n", 0, i) + 1
    if text[start:i].strip():      # something else precedes the marker on its line: keep it
        start = i
    end = j + len(END)
    nl = text.find("\n", end)
    tail_ok = not text[end:(nl if nl >= 0 else len(text))].strip()
    end = (nl + 1 if nl >= 0 else len(text)) if tail_ok else end
    return text[:start] + text[end:]


def _force_remove(func, path, _exc):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def uninstall(root, yes=False, out=print, confirm=None) -> int:
    root = Path(root).resolve()
    d = config.dagr_dir(root)
    if not d.is_dir():
        out("nothing to uninstall: no .dagr/ folder here")
        return 0
    restore = restore_plan(root)
    l0 = []
    try:
        cfg = json.loads((d / "config.json").read_text(encoding="utf-8-sig"))
        l0 += [f for f in cfg.get("l0_files") or [] if isinstance(f, str)]
    except (OSError, ValueError, AttributeError):
        pass
    l0 += [f for f in ("CLAUDE.md", "AGENTS.md", "GEMINI.md") if f not in l0]
    delete = [r for r in read_manifests(root) if not r.startswith(".dagr/")]
    out("uninstall will:")
    for rel in sorted(restore):
        out(f"  restore  {rel}  (from the oldest backup)")
    for rel in delete:
        out(f"  delete   {rel}  (added by dagr)")
    for rel in l0:   # safety net: a dagr block that no backup covers
        p = _inside(root, rel)
        if rel not in restore and p is not None and p.is_file():
            try:
                if strip_block(p.read_bytes().decode("utf-8")) is not None:
                    out(f"  strip    the dagr block in {rel}  (no backup covers it)")
            except UnicodeDecodeError:
                pass
    out("  remove   .dagr/")
    if not yes:
        ask = confirm or (lambda: input("Go ahead? [y/N] "))
        try:
            ans = ask()
        except EOFError:
            ans = ""
        if str(ans).strip().lower() not in ("y", "yes"):
            out("aborted: nothing changed (use --yes to skip this question)")
            return 1
    for rel, src in sorted(restore.items()):
        dst = _inside(root, rel)
        if dst is None:
            out(f"  skipped {rel}: outside the root")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    stripped = []
    for rel in l0:
        p = _inside(root, rel)
        if rel in restore or p is None or not p.is_file():
            continue
        try:
            raw = p.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        new = strip_block(raw)
        if new is not None:
            p.write_bytes(new.encode("utf-8"))
            stripped.append(rel)
            out(f"  stripped the dagr block from {rel} (it was not covered by a backup)")
    for rel in delete:
        p = _inside(root, rel)
        if p is None or not p.is_file():
            continue
        try:
            p.unlink()
        except OSError as e:
            out(f"  could not delete {rel}: {e}")
            continue
        q = p.parent
        while q != root and q.is_dir() and not any(q.iterdir()):   # prune emptied folders
            q.rmdir()
            q = q.parent
    shutil.rmtree(d, onerror=_force_remove)
    out(f"done: restored {len(restore)} file(s), deleted {len(delete)} added file(s), "
        "removed .dagr/"
        + (f", stripped the dagr block from {len(stripped)} L0 file(s)" if stripped else ""))
    return 0
