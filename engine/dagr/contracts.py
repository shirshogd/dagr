"""contracts: find workflow contracts anywhere in the user's tree. Stdlib only.

A contract is a `CONTEXT.md` (or a `README.md` in a folder that has stage subfolders) whose
YAML frontmatter has an `id` and at least one of `consumes` / `produces`. Discovery skips
.git, node_modules, .dagr, virtualenvs and `output/` folders. When `.dagr/config.json` names
`workflow_glob` / `contract_name` (the integration step writes them), those folders are read
first; everything else is auto-discovered.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from . import frontmatter as fmt

SKIP_DIRS = {".git", "node_modules", ".dagr", "__pycache__", ".venv", "venv", "env", ".tox",
             ".mypy_cache", ".pytest_cache", "site-packages", ".idea", ".vscode"}
OUTPUT_DIRS = {"output", "outputs"}
STAGE_CONTAINERS = {"stages", "steps", "stage", "step"}
NUMBERED = re.compile(r"^\d{1,3}[-_. ]\S")
MAX_DIRS = 50000


def read(p) -> str:
    return Path(p).read_text(encoding="utf-8", errors="replace")


def iter_dirs(root, skip_output=True, outputs=None):
    """Yield (dirpath, dirnames, filenames) top-down, sorted, pruned. Pruned `output/`
    folders are appended to `outputs` (a list) when given."""
    n = 0
    for dp, dns, fns in os.walk(root):
        keep = []
        for d in sorted(dns):
            full = Path(dp) / d
            if d in SKIP_DIRS or (full / "pyvenv.cfg").is_file():
                continue
            if d.lower() in OUTPUT_DIRS:
                if outputs is not None:
                    outputs.append(full)
                if skip_output:
                    continue
            keep.append(d)
        dns[:] = keep
        n += 1
        if n > MAX_DIRS:
            dns[:] = []
        yield dp, dns, sorted(fns)


def stage_dirs(d) -> list:
    """Stage folders of a workflow folder: numbered subfolders, or the folders inside a
    stages/steps subfolder."""
    d = Path(d)
    out = []
    try:
        subs = sorted(p for p in d.iterdir() if p.is_dir() and p.name not in SKIP_DIRS)
    except OSError:
        return []
    for p in subs:
        if p.name.lower() in STAGE_CONTAINERS:
            try:
                out += sorted(q for q in p.iterdir() if q.is_dir())
            except OSError:
                pass
        elif NUMBERED.match(p.name) and p.name.lower() not in OUTPUT_DIRS:
            out.append(p)
    return out


def context_file(d, names=("CONTEXT.md", "README.md")):
    """The CONTEXT.md (any case) in a folder, else None."""
    try:
        for f in Path(d).iterdir():
            if f.is_file() and f.name.lower() == names[0].lower():
                return f
    except OSError:
        pass
    return None


class Unit:
    """A workflow, as declared by its own contract file."""

    def __init__(self, path: Path, fm: dict, root: Path):
        self.path = Path(path)
        self.dir = self.path.parent
        self.root = Path(root)
        self.fm = fm
        self.id = str(fm.get("id") or "").strip()
        self.consumes = fmt.as_list(fm.get("consumes"))
        self.produces = fmt.as_list(fm.get("produces"))
        self.prerequisites = fmt.as_list(fm.get("prerequisites"))
        self.composable_with = fmt.as_list(fm.get("composable_with"))
        self.kind = "workflow"
        self.line = ""
        self.review_gates = []
        self.model_policy = {}

    @property
    def rel(self) -> str:
        return rel(self.dir, self.root)

    @property
    def file_rel(self) -> str:
        return rel(self.path, self.root)

    @property
    def stages(self):
        return [p for p in stage_dirs(self.dir)]

    def required_ports(self):
        return [p for p in self.consumes if not p.endswith("?")]

    def description(self) -> str:
        for k in ("purpose", "description"):
            if isinstance(self.fm.get(k), str) and self.fm[k].strip():
                return self.fm[k].strip()
        try:
            _l, body, _s = fmt.split_frontmatter(read(self.path))
        except OSError:
            return ""
        para, started = [], False
        for line in body.splitlines():
            if line.startswith("#"):
                if started:
                    break
                continue
            if line.strip():
                started = True
                para.append(line.strip())
            elif started:
                break
        return " ".join(para)


def rel(p, root) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(p).as_posix()


def is_contract_fm(fm: dict) -> bool:
    return bool(str(fm.get("id") or "").strip()) and ("consumes" in fm or "produces" in fm)


def candidate_files(root):
    """Every CONTEXT.md, plus README.md inside a folder with stage subfolders."""
    for dp, _dns, fns in iter_dirs(root):
        for fn in fns:
            low = fn.lower()
            if low == "context.md":
                yield Path(dp) / fn
            elif low == "readme.md" and stage_dirs(dp):
                yield Path(dp) / fn


def _configured(root, cfg):
    """Contract files named by the kit's config (workflow_glob + contract_name)."""
    glob = (cfg or {}).get("workflow_glob")
    name = (cfg or {}).get("contract_name") or "CONTEXT.md"
    out = []
    if glob:
        for d in sorted(Path(root).glob(str(glob).rstrip("/\\"))):
            if d.is_dir():
                f = d / name
                if f.is_file():
                    out.append(f)
    return out


def discover(root, cfg=None):
    """-> (units dict id -> Unit, issues list of dicts {path, kind, message}).
    Issues: frontmatter-error, duplicate-id, half-declared (id without ports)."""
    root = Path(root)
    units, issues, seen = {}, [], set()
    files = _configured(root, cfg) + list(candidate_files(root))
    for f in files:
        key = str(f.resolve())
        if key in seen:
            continue
        seen.add(key)
        try:
            text = read(f)
        except OSError as e:
            issues.append({"path": rel(f, root), "kind": "unreadable", "message": str(e)})
            continue
        fm, errs, state = fmt.parse_text(text)
        for e in errs:
            issues.append({"path": rel(f, root), "kind": "frontmatter-error", "message": e})
        if state == "none":
            continue
        if not is_contract_fm(fm):
            if fm.get("id") and not ("consumes" in fm or "produces" in fm):
                issues.append({"path": rel(f, root), "kind": "half-declared",
                               "message": "has `id` but neither `consumes` nor `produces`"})
            continue
        u = Unit(f, fm, root)
        if u.id in units:
            issues.append({"path": rel(f, root), "kind": "duplicate-id",
                           "message": f"id `{u.id}` is also declared by {units[u.id].file_rel}"})
            continue
        units[u.id] = u
    return units, issues
