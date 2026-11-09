"""runner_lib: helpers for the graph runner. Stdlib only.

launch_worker() is the ONE place a worker argv is built and started. The reviewer and the
planner reuse it, so "which agent CLI" is a config question (`.dagr/config.json` -> workers),
never a code question.
"""
from __future__ import annotations

import json
import os
import random
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from .frontmatter import set_frontmatter  # noqa: F401  (re-exported)

IS_WIN = os.name == "nt"

SKIP_DIRS = {".git", "node_modules", ".dagr", "__pycache__", ".venv", "venv", "env",
             ".tox", ".mypy_cache", ".pytest_cache", "site-packages"}

CONTRACT = (
    "You may write only these paths: {affects} and {assets}. "
    "You must not run git commit, git push, or any command that publishes, spends money or "
    "deletes outside your paths. Do not run anything in the background and then wait for it; "
    "run it in the foreground with a timeout. Do not edit anything under .dagr/ except your "
    "assets folder. Before you finish write {assets}receipt.md containing: what you did, "
    "commands run with their output tail, each Definition-of-done check and its result, a "
    "`learned:` block, and any question for the human. If a step is impossible, write that in "
    "the receipt and stop; do not improvise scope."
)


# ---- small utils -------------------------------------------------------------

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def slug_of(ticket) -> str:
    """.dagr/maps/<slug>/tickets/T##-x.md -> slug"""
    return Path(ticket.path).resolve().parent.parent.name


def assets_rel(slug, tid) -> str:
    return f".dagr/maps/{slug}/assets/{tid}"


def assets_dir(root, slug, tid) -> Path:
    return Path(root) / ".dagr" / "maps" / slug / "assets" / tid


def pid_alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if IS_WIN:
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                 capture_output=True, text=True, timeout=20).stdout
        except Exception:
            return False
        return re.search(rf"\b{pid}\b", out) is not None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def proc_ident(pid):
    """A string that identifies THIS incarnation of a pid (process creation time), or None
    when it cannot be read. Stored with the pid so a recycled pid is never killed."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if IS_WIN:
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.windll.kernel32
            k32.OpenProcess.restype = wintypes.HANDLE
            h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return None
            try:
                c, e, k, u = (wintypes.FILETIME() for _ in range(4))
                if not k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                           ctypes.byref(k), ctypes.byref(u)):
                    return None
                return f"win:{(c.dwHighDateTime << 32) | c.dwLowDateTime}"
            finally:
                k32.CloseHandle(h)
        except Exception:
            return None
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            raw = f.read().decode("utf-8", "replace")
        return "proc:" + raw[raw.rindex(")") + 2:].split()[19]
    except Exception:
        pass
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True,
                             text=True, timeout=10).stdout.strip()
        return "ps:" + out if out else None
    except Exception:
        return None


def kill_tree(pid) -> None:
    """Kill a process and its children. Never raises. Unverified: prefer kill_verified()."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return
    if IS_WIN:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True)
        return
    import signal
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def kill_verified(pid, ident) -> str:
    """kill_tree only if `pid` still has the creation-time `ident` recorded at launch.
    -> "killed" | "gone" | "mismatch" (pid reused: NOT killed) | "unverified" (NOT killed)."""
    if not pid_alive(pid):
        return "gone"
    if not ident:
        return "unverified"
    cur = proc_ident(pid)
    if cur is None:
        return "gone" if not pid_alive(pid) else "unverified"
    if cur != ident:
        return "mismatch"
    kill_tree(pid)
    return "killed"


# ---- rate-limit back-off ---------------------------------------------------------

# 429 only as a standalone number (not 4290, 1429, "$1,429.00"); the words are plain matches
RATE_RE = re.compile(r"(?<![\w$,.])429(?![\w]|,\d|\.\d)|rate.?limit|overloaded|usage limit",
                     re.I)


class Backoff:
    """delay = min(900, 15 * 2**n) seconds plus 0-25% jitter, n = consecutive rate-limit
    events so far. `scale` shrinks it for tests only."""

    def __init__(self, scale=1.0, rng=None):
        self.scale = float(scale)
        self.rng = rng or random.random

    def delay(self, n) -> float:
        base = min(900.0, 15.0 * (2 ** max(0, int(n))))
        return base * (1.0 + 0.25 * self.rng()) * self.scale

    @staticmethod
    def matches(*texts) -> bool:
        return any(t and RATE_RE.search(str(t)) for t in texts)


# ---- worker output ---------------------------------------------------------------

def read_result(path):
    """A claude-style final result object from a stdout file. Accepts one JSON object or
    stream-json lines: the LAST line with type == "result". -> dict or None."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        d = json.loads(text)
        if isinstance(d, dict):
            return d
    except ValueError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("type") == "result":
            return d
    return None


def read_output(path, fmt="claude-stream"):
    """The worker's result as a dict with `result`, `is_error`, `session_id`,
    `total_cost_usd`. fmt "text": whatever the worker printed is the result (cost unknown)."""
    if fmt != "text":
        return read_result(path)
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return {"result": text, "is_error": False, "session_id": None, "total_cost_usd": 0.0}


def newest_mtime(paths, cap=3000) -> float:
    """Latest mtime among the given files and, for dirs, the files below them (bounded)."""
    best, seen = 0.0, 0
    for p in paths:
        p = Path(p)
        try:
            if p.is_dir():
                best = max(best, p.stat().st_mtime)
                for dp, dns, fns in os.walk(p):
                    for n in fns + dns:
                        seen += 1
                        if seen > cap:
                            return best
                        try:
                            best = max(best, os.stat(os.path.join(dp, n)).st_mtime)
                        except OSError:
                            pass
            elif p.exists():
                best = max(best, p.stat().st_mtime)
        except OSError:
            pass
    return best


def set_ticket_fm(ticket, key, value) -> None:
    """Write a ticket frontmatter key (status words mapped to the on-disk vocabulary) and
    update the in-memory ticket with the internal value."""
    from .graphcore import STATUS_TO_FM
    disk = STATUS_TO_FM.get(value, value) if key == "status" else value
    set_frontmatter(ticket.path, key, disk)
    setattr(ticket, key, value)


def append_resolution(path, text_lines) -> None:
    p = Path(path)
    with open(p, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    idx = next((i for i, l in enumerate(lines) if l.strip() == "## Resolution"), None)
    if idx is None:
        while lines and lines[-1] == "":
            lines.pop()
        lines += ["", "## Resolution"] + list(text_lines) + [""]
    else:
        end = len(lines)
        for j in range(idx + 1, len(lines)):
            if lines[j].startswith("## "):
                end = j
                break
        while end > idx + 1 and lines[end - 1] == "":
            end -= 1
        lines[end:end] = list(text_lines)
        if lines[-1] != "":
            lines.append("")
    tmp = str(p) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(nl.join(lines))
    os.replace(tmp, p)


# ---- allowed tools (used by templates that have a `tools` mapping, e.g. claude) -----

BASH_ALLOWED = ["Bash(python:*)", "Bash(pytest:*)", "Bash(node:*)", "Bash(npm test:*)",
                "Bash(ls:*)", "Bash(cat:*)", "Bash(git status:*)", "Bash(git diff:*)",
                "Bash(git log:*)"]
DISALLOWED = ["Bash(git commit:*)", "Bash(git push:*)", "Bash(rm:*)", "Bash(del:*)"]


def _write_pat(p: str, root) -> str:
    p = p.replace("\\", "/").strip()
    if p.endswith("/"):
        return p + "**"
    if not any(c in p for c in "*?[") and root and (Path(root) / p).is_dir():
        return p + "/**"
    return p


def build_allowed_tools(ticket, root=None, slug=None) -> list:
    slug = slug or slug_of(ticket)
    assets = f"{assets_rel(slug, ticket.id)}/**"
    tools = ["Read", "Glob", "Grep"]
    pats = [_write_pat(a, root) for a in (ticket.affects or [])] + [assets]
    for pat in pats:
        tools += [f"Write({pat})", f"Edit({pat})"]
    return tools + BASH_ALLOWED


# ---- launching -----------------------------------------------------------------

_FLAG_CACHE: dict = {}
_PLACEHOLDER = re.compile(r"\{(model|brief_file|cwd|max_turns|max_budget_usd)\}")


def supports_flag(prefix, flag, probe_args) -> bool:
    """One help probe per command per process; every flag is checked in its output."""
    key = (tuple(prefix), tuple(probe_args))
    if key not in _FLAG_CACHE:
        try:
            r = subprocess.run(list(prefix) + list(probe_args), capture_output=True, text=True,
                               timeout=30, stdin=subprocess.DEVNULL)
            _FLAG_CACHE[key] = r.stdout + r.stderr
        except Exception:
            _FLAG_CACHE[key] = ""
    return flag in _FLAG_CACHE[key]


def _fill(tok, vals):
    return _PLACEHOLDER.sub(lambda m: str(vals.get(m.group(1)) or ""), tok)


def _resolve_exe(argv):
    """Resolve argv[0] through PATH (so Windows finds `claude.cmd`). Raise a plain error if
    it is nowhere."""
    first = argv[0]
    if Path(first).exists():
        return argv
    found = shutil.which(first)
    if not found:
        raise FileNotFoundError(
            f"worker binary `{first}` not found on PATH. Install it, set DAGR_WORKER_BIN, or "
            "edit .dagr/config.json -> workers")
    return [found] + argv[1:]


def build_argv(worker, model=None, brief_file="", cwd="", allowed_tools=None,
               disallowed_tools=None, max_turns=None, max_budget_usd=None):
    """-> (argv, feed_stdin). The only place an argv is built from a worker template."""
    if worker.get("command"):
        base = shlex.split(worker["command"], posix=True)
    else:
        base = list(worker.get("argv") or [])
    if not base:
        raise ValueError(f"worker `{worker.get('_name')}` has no argv/command in config")
    override = worker.get("_bin")
    prefix = list(override) if override else base[:1]
    base = prefix + base[1:]
    vals = {"model": model if model is not None else worker.get("model", ""),
            "brief_file": brief_file, "cwd": cwd,
            "max_turns": max_turns or "", "max_budget_usd": max_budget_usd or ""}
    argv = [_fill(t, vals) for t in base]
    probe = worker.get("probe")
    for group in worker.get("optional_flags") or []:
        flag = group[0]
        if probe and flag.startswith("--") and not supports_flag(prefix, flag, probe):
            continue
        filled = [_fill(t, vals) for t in group]
        if any(f == "" for f in filled):
            continue
        argv += filled
    tools = worker.get("tools") or {}
    if allowed_tools and tools.get("allowed"):
        argv += [tools["allowed"]] + list(allowed_tools)
    if disallowed_tools and tools.get("disallowed"):
        argv += [tools["disallowed"]] + list(disallowed_tools)
    argv += [_fill(t, vals) for t in worker.get("tail") or []]
    return _resolve_exe(argv), worker.get("stdin") == "brief"


def launch_worker(worker, prompt, cwd, out_path, err_path, model=None, allowed_tools=None,
                  disallowed_tools=None, max_turns=None, prompt_file=None, max_budget_usd=None):
    """THE one place a worker process is started. The prompt is written to a file; it goes to
    the child's stdin from that file (no pipe, so a child that dies early cannot deadlock the
    runner) or is passed by path via `{brief_file}`."""
    out_path, err_path = Path(out_path), Path(err_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pfile = Path(prompt_file) if prompt_file else out_path.with_suffix(".prompt.txt")
    pfile.parent.mkdir(parents=True, exist_ok=True)
    pfile.write_text(prompt, encoding="utf-8")
    argv, feed = build_argv(worker, model, str(pfile).replace("\\", "/"),
                            str(cwd).replace("\\", "/"), allowed_tools, disallowed_tools,
                            max_turns, max_budget_usd)
    with open(out_path, "wb") as fo, open(err_path, "wb") as fe:
        if feed:
            with open(pfile, "rb") as fin:
                return spawn_detached(argv, cwd, stdin=fin, stdout=fo, stderr=fe)
        return spawn_detached(argv, cwd, stdin=subprocess.DEVNULL, stdout=fo, stderr=fe)


def spawn_detached(cmd, cwd, stdin=None, stdout=None, stderr=None, no_console=False):
    """The ONE process-spawn site (a test pins it). New process group (POSIX: new session);
    no_console=True also detaches from the console (Windows)."""
    kw = {}
    if IS_WIN:
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | (
            subprocess.DETACHED_PROCESS if no_console else 0)
    else:
        kw["start_new_session"] = True
    return subprocess.Popen(cmd, stdin=stdin, stdout=stdout, stderr=stderr, cwd=str(cwd), **kw)


def run_blocking(worker, prompt, cwd, workdir, name="call", model=None, timeout=600,
                 allowed_tools=None, disallowed_tools=None):
    """Run one worker to completion (planner use). -> (result dict or None, error or None)."""
    workdir = Path(workdir)
    out, err = workdir / f"{name}.out", workdir / f"{name}.err"
    try:
        proc = launch_worker(worker, prompt, cwd, out, err, model, allowed_tools,
                             disallowed_tools, prompt_file=workdir / f"{name}.prompt.md")
    except Exception as e:
        return None, f"could not launch worker: {type(e).__name__}: {e}"
    try:
        rc = proc.wait(timeout=timeout)
    except Exception:
        kill_tree(proc.pid)
        return None, f"worker timed out after {timeout}s"
    data = read_output(out, worker.get("output", "claude-stream"))
    if data is None:
        return None, f"worker output unreadable (exit {rc})"
    if data.get("is_error") or rc != 0:
        return None, f"worker failed (exit {rc}): {str(data.get('result'))[:200]}"
    return data, None


# ---- brief ---------------------------------------------------------------------

_TOKEN = re.compile(r"`([^`\n]+)`")


def _input_paths(ticket, root) -> list:
    sec = ticket.sections.get("Inputs", "")
    out, prev_dir = [], None
    for tok in _TOKEN.findall(sec):
        tok = tok.strip()
        if not re.fullmatch(r"[\w./\\-]+", tok) or "." not in tok:
            continue
        cands = [tok]
        if prev_dir and "/" not in tok:
            cands.append(f"{prev_dir}/{tok}")
        for c in cands:
            fp = Path(root) / c
            if fp.is_file():
                if c not in out:
                    out.append(c)
                if "/" in c:
                    prev_dir = c.rsplit("/", 1)[0]
                break
    return out


def build_brief(ticket, root, notes=None) -> str:
    slug = slug_of(ticket)
    tid = ticket.id
    assets = assets_rel(slug, tid) + "/"
    parts = [f"# Worker brief: {tid} ({slug})", "",
             "## The ticket (full)", "",
             Path(ticket.path).read_text(encoding="utf-8", errors="replace"), "",
             "## Input files named by the ticket", ""]
    paths = _input_paths(ticket, root)
    if not paths:
        parts.append("(none resolved to a file; read what the Inputs section names)")
    for rel in paths:
        fp = Path(root) / rel
        if fp.stat().st_size < 20 * 1024:
            parts += [f"### {rel}", "", "```", fp.read_text(encoding="utf-8", errors="replace"),
                      "```", ""]
        else:
            parts += [f"- {rel} (over 20 KB; read it yourself)"]
    affects = ", ".join(ticket.affects) if ticket.affects else "(nothing; research ticket)"
    parts += ["", "## Contract", "", CONTRACT.format(affects=affects, assets=assets), ""]
    if notes:
        parts += ["## Reviewer notes from your last attempt - fix these, do not restart", "",
                  notes if isinstance(notes, str) else "\n".join(f"- {n}" for n in notes), ""]
    return "\n".join(parts)


# ---- git (only when the root is a git repo) --------------------------------------

def _git(root, *args):
    return subprocess.run(["git", "-C", str(root)] + list(args), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


_REPO_CACHE: dict = {}


def is_git_repo(root) -> bool:
    key = str(Path(root).resolve())
    if key not in _REPO_CACHE:
        try:
            r = _git(root, "rev-parse", "--is-inside-work-tree")
            _REPO_CACHE[key] = r.returncode == 0 and r.stdout.strip() == "true"
        except OSError:   # git not installed
            _REPO_CACHE[key] = False
    return _REPO_CACHE[key]


def _prefix(root) -> str:
    r = _git(root, "rev-parse", "--show-prefix")
    return r.stdout.strip().replace("\\", "/")


def snapshot(root, cap=20000) -> dict:
    """{relpath: "s:<mtime_ns>:<size>"}; the no-git stand-in for `git status`."""
    root = Path(root)
    out, n = {}, 0
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            n += 1
            if n > cap:
                return out
            fp = Path(dp) / fn
            try:
                st = fp.stat()
            except OSError:
                continue
            out[fp.relative_to(root).as_posix()] = f"s:{st.st_mtime_ns}:{st.st_size}"
    return out


def porcelain(root) -> dict:
    """{path (relative to root): status token}. `git status --porcelain -z -uall` in a git
    repo, a file snapshot otherwise. `.dagr/` is never included."""
    if not is_git_repo(root):
        return snapshot(root)
    prefix = _prefix(root)
    r = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-z", "-uall"],
                       capture_output=True)
    out, parts, i = {}, r.stdout.decode("utf-8", "replace").split("\0"), 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if len(e) < 4:
            continue
        xy, path = e[:2], e[3:]
        if xy[0] in "RC":
            i += 1
        if prefix:
            if not path.startswith(prefix):
                continue
            path = path[len(prefix):]
        if path.startswith(".dagr/"):
            continue
        out[path] = xy
    return out


def _ignored(root, path) -> bool:
    return _git(root, "check-ignore", "-q", "--", path).returncode == 0


def _add_commit(root, paths, msg_args):
    """git add -- paths; commit only those paths; 5x retry on index.lock. -> sha or None."""
    last = None
    for _ in range(5):
        r = _git(root, "add", "--", *paths)
        if r.returncode == 0:
            break
        last = r.stderr
        if "index.lock" in r.stderr:
            time.sleep(2)
            continue
        raise RuntimeError(f"git add failed: {r.stderr.strip()}")
    else:
        raise RuntimeError(f"git add failed after retries: {last}")
    if _git(root, "diff", "--cached", "--quiet", "--", *paths).returncode == 0:
        return None
    args = []
    for m in msg_args:
        if m:
            args += ["-m", m]
    for _ in range(5):
        r = _git(root, "commit", *args, "--", *paths)
        if r.returncode == 0:
            return _git(root, "rev-parse", "HEAD").stdout.strip()
        if "index.lock" in r.stderr:
            time.sleep(2)
            continue
        raise RuntimeError(f"git commit failed: {r.stderr.strip() or r.stdout.strip()}")
    raise RuntimeError("git commit failed after retries (index.lock)")


def commit_paths(ticket, root, slug=None) -> list:
    """The exact paths a ticket's commit may stage: its affects (that exist, inside the root,
    not git-ignored) plus its assets folder when that is not ignored."""
    slug = slug or slug_of(ticket)
    root = Path(root).resolve()
    paths = []
    for a in list(ticket.affects or []) + [assets_rel(slug, ticket.id)]:
        a = a.replace("\\", "/").strip().rstrip("/")
        if a.endswith("/**"):
            a = a[:-3]
        if not a or a.startswith("/") or re.match(r"^[A-Za-z]:", a) or ".." in a.split("/"):
            continue
        if any(c in a for c in "*?["):
            ok = True   # a pathspec glob: git expands it
        else:
            ok = (root / a).exists()
        if ok and not _ignored(root, a):
            paths.append(a)
    return paths


def git_commit_ticket(ticket, state, root, slug=None, trailer=None):
    """Stage exactly this ticket's affects + assets folder, commit only those paths. Returns
    the commit sha, or None when there was nothing to commit (or the root is not a git repo).
    Never stages the whole tree, never pushes."""
    if not is_git_repo(root):
        return None
    slug = slug or slug_of(ticket)
    rec = (state.get("tickets") or {}).get(ticket.id, {})
    paths = commit_paths(ticket, root, slug)
    if not paths:
        return None
    score = rec.get("reviewer_score")
    msg = (f"dagr {slug}/{ticket.id}: {ticket.title} (score "
           f"{score if score is not None else 'n/a'}, cost ${float(rec.get('cost_usd') or 0):.2f})")
    body = f"Runner-committed after review. Worker session {rec.get('worker')}."
    return _add_commit(root, paths, [msg, body, trailer or ""])


def find_ticket_commit(root, slug, tid):
    """sha of an existing `dagr <slug>/<tid>: ...` work commit, or None."""
    if not is_git_repo(root):
        return None
    r = _git(root, "log", "--format=%H%x09%s", f"--grep=^dagr {slug}/{tid}: ")
    for line in r.stdout.splitlines():
        sha, _, subj = line.partition("\t")
        if subj.startswith(f"dagr {slug}/{tid}: "):
            return sha
    return None
